import os
import time
import yaml
import asyncio
import aiohttp
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from multiprocessing import Pool, Manager, Process, Queue
from datetime import datetime
from lxml import etree
try:
    import orjson
    JSON_DUMPS = orjson.dumps
except ImportError:
    import json
    JSON_DUMPS = json.dumps

# Configuration from environment variables
XML_LOG_DIR = os.getenv('XML_LOG_DIR', '/var/log/xml_data')
SCHEMAS_FILE = os.getenv('SCHEMAS_FILE', '/app/schemas.yaml')
SPLUNK_HEC_URL = os.getenv('SPLUNK_HEC_URL', 'https://your-splunk-host:8088/services/collector/event')
SPLUNK_TOKEN = os.getenv('SPLUNK_TOKEN', 'your-splunk-hec-token')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
BUFFER_TIMEOUT = float(os.getenv('BUFFER_TIMEOUT', 2.0))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', os.cpu_count() or 4))

class XMLSplunkHandler(FileSystemEventHandler):
    def __init__(self, splunk_url, splunk_token, task_queue, file_positions, schemas):
        self.splunk_url = splunk_url
        self.splunk_token = splunk_token
        self.task_queue = task_queue
        self.file_positions = file_positions
        self.schemas = schemas

    def load_schemas(self):
        with open(SCHEMAS_FILE, 'r') as f:
            return yaml.safe_load(f)['schemas']

    def get_schema(self, root_element, namespace):
        for schema in self.schemas:
            if schema['root_element'] == root_element and schema.get('namespace', '') == namespace:
                return schema
        return None

    def transform_to_cim(self, event, schema):
        cim_template = {
            'time': event.get(schema['mappings']['cim']['time'], time.time()),
            'source': event.get(schema['mappings']['cim'].get('source', ''), ''),
            'src_port': int(event.get(schema['mappings']['cim'].get('src_port', '0'), 0)),
            'dest': event.get(schema['mappings']['cim'].get('dest', ''), ''),
            'dest_port': int(event.get(schema['mappings']['cim'].get('dest_port', '0'), 0)),
            'protocol': event.get(schema['mappings']['cim'].get('protocol', ''), '').lower(),
            'event_id': event.get(schema['mappings']['cim'].get('event_id', 'id'), ''),
            'vendor_product': 'XML_Connector',
            'schema': schema['name']
        }
        for key, value in schema['mappings']['cim'].items():
            if key not in ['time', 'event_id', 'source', 'src_port', 'dest', 'dest_port', 'protocol']:
                cim_template[key] = event.get(value, '')
        return {'event': cim_template, 'sourcetype': f'xml:{schema["name"]}'}

    def process_xml_chunk(self, file_path, position):
        cim_batch = []
        try:
            with open(file_path, 'rb') as f:
                f.seek(position)
                context = etree.iterparse(f, events=('end',), tag=None, huge_tree=True)
                event = {}
                current_schema = None
                root_element = None
                namespace = None
                event_count = 0

                for action, elem in context:
                    if elem.tag.startswith('{'):
                        namespace = elem.tag.split('}')[0][1:]
                        tag = elem.tag.split('}')[1]
                    else:
                        tag = elem.tag

                    if not root_element:
                        root_element = tag
                        current_schema = self.get_schema(root_element, namespace or '')
                        if not current_schema:
                            print(f"No schema found for {root_element} in {namespace}")
                            break

                    if action == 'end' and tag == current_schema['root_element']:
                        event = {child.tag.split('}')[-1]: child.text or '' for child in elem.iter() if child.text}
                        cim_batch.append(self.transform_to_cim(event, current_schema))
                        event_count += 1
                        event = {}
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        if event_count >= BATCH_SIZE or f.tell() - position >= 1024 * 1024:
                            break

                new_position = f.tell()
                del context
                return cim_batch, file_path, new_position
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return [], file_path, position

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.xml'):
            return
        file_path = event.src_path
        with self.file_positions.get_lock():
            position = self.file_positions.get(file_path, 0)
        self.task_queue.put((file_path, position))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.xml'):
            with self.file_positions.get_lock():
                self.file_positions[event.src_path] = 0
            self.on_modified(event)

async def sender_process(task_queue, splunk_url, splunk_token, stop_event, file_positions):
    async with aiohttp.ClientSession() as session:
        cim_batch = []
        last_flush = time.time()

        while not stop_event.is_set():
            try:
                while not task_queue.empty():
                    cim, file_path, new_position = task_queue.get()
                    cim_batch.extend(cim)
                    with file_positions.get_lock():
                        file_positions[file_path] = new_position

                if len(cim_batch) >= BATCH_SIZE or time.time() - last_flush > BUFFER_TIMEOUT:
                    if cim_batch:
                        headers = {
                            'Authorization': f'Splunk {splunk_token}',
                            'Content-Type': 'application/json'
                        }
                        async with session.post(splunk_url, headers=headers, data=JSON_DUMPS(cim_batch), timeout=10) as response:
                            if response.status != 200:
                                print(f"Splunk error: {await response.text()}")
                        cim_batch = []
                    last_flush = time.time()

                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Sender error: {e}")

def worker_process(task_queue, splunk_url, splunk_token, file_positions, schemas):
    handler = XMLSplunkHandler(splunk_url, splunk_token, task_queue, file_positions, schemas)
    while True:
        try:
            file_path, position = task_queue.get(timeout=1)
            cim_batch, file_path, new_position = handler.process_xml_chunk(file_path, position)
            task_queue.put((cim_batch, file_path, new_position))
        except Queue.Empty:
            time.sleep(0.1)

def main():
    manager = Manager()
    file_positions = manager.dict()
    task_queue = Queue()
    stop_event = manager.Event()
    schemas = XMLSplunkHandler(None, None, None, None, None).load_schemas()

    sender = Process(target=asyncio.run, args=(sender_process(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, stop_event, file_positions),))
    sender.start()

    pool = Pool(processes=WORKER_COUNT, initializer=worker_process,
                initargs=(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, file_positions, schemas))

    observer = Observer()
    handler = XMLSplunkHandler(SPLUNK_HEC_URL, SPLUNK_TOKEN, task_queue, file_positions, schemas)
    observer.schedule(handler, path=XML_LOG_DIR, recursive=False)
    observer.start()

    print(f"Monitoring XML logs in {XML_LOG_DIR} with {WORKER_COUNT} workers for Splunk")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        observer.stop()
        pool.terminate()
        pool.join()
        sender.terminate()
        sender.join()
    observer.join()

if __name__ == "__main__":
    main()