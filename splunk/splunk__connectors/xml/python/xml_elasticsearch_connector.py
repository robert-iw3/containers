import os
import time
import yaml
import asyncio
from elasticsearch_async import AsyncElasticsearch
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
ES_HOST = os.getenv('ES_HOST', 'http://localhost:9200')
ES_INDEX = os.getenv('ES_INDEX', 'xml-logs')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
BUFFER_TIMEOUT = float(os.getenv('BUFFER_TIMEOUT', 2.0))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', os.cpu_count() or 4))

class XMLElasticsearchHandler(FileSystemEventHandler):
    def __init__(self, es_index, task_queue, file_positions, schemas):
        self.es_index = es_index
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

    def transform_to_ecs(self, event, schema):
        ecs_template = {
            '@timestamp': event.get(schema['mappings']['ecs']['timestamp'], datetime.utcnow().isoformat()),
            'event': {
                'category': [schema['mappings']['ecs'].get('event_category', 'unknown')],
                'kind': 'event',
                'dataset': f'xml.{schema["name"]}',
                'id': event.get(schema['mappings']['ecs'].get('event_id', 'id'), '')
            },
            'source': {
                'ip': event.get(schema['mappings']['ecs'].get('source_ip', ''), ''),
                'port': int(event.get(schema['mappings']['ecs'].get('source_port', '0'), 0))
            },
            'destination': {
                'ip': event.get(schema['mappings']['ecs'].get('dest_ip', ''), ''),
                'port': int(event.get(schema['mappings']['ecs'].get('dest_port', '0'), 0))
            },
            'network': {
                'protocol': event.get(schema['mappings']['ecs'].get('protocol', ''), '').lower()
            },
            'xml': {
                'schema': schema['name'],
                'raw': event
            }
        }
        for key, value in schema['mappings']['ecs'].items():
            if key not in ['timestamp', 'event_id', 'event_category', 'source_ip', 'source_port', 'dest_ip', 'dest_port', 'protocol']:
                nested_keys = key.split('/')
                target = ecs_template
                for i, k in enumerate(nested_keys[:-1]):
                    target = target.setdefault(k, {})
                target[nested_keys[-1]] = event.get(value, '')
        return ecs_template

    def process_xml_chunk(self, file_path, position):
        ecs_batch = []
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
                        ecs_batch.append(self.transform_to_ecs(event, current_schema))
                        event_count += 1
                        event = {}
                        elem.clear()
                        while elem.getprevious() is not None:
                            del elem.getparent()[0]
                        if event_count >= BATCH_SIZE or f.tell() - position >= 1024 * 1024:
                            break

                new_position = f.tell()
                del context
                return ecs_batch, file_path, new_position
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

async def sender_process(task_queue, es_index, stop_event, file_positions):
    es = AsyncElasticsearch([ES_HOST])
    ecs_batch = []
    last_flush = time.time()

    while not stop_event.is_set():
        try:
            while not task_queue.empty():
                ecs, file_path, new_position = task_queue.get()
                ecs_batch.extend(ecs)
                with file_positions.get_lock():
                    file_positions[file_path] = new_position

            if len(ecs_batch) >= BATCH_SIZE or time.time() - last_flush > BUFFER_TIMEOUT:
                if ecs_batch:
                    actions = [{'_index': es_index, '_source': event} for event in ecs_batch]
                    await es.bulk(actions)
                    ecs_batch = []
                last_flush = time.time()

            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Sender error: {e}")

    await es.close()

def worker_process(task_queue, es_index, file_positions, schemas):
    handler = XMLElasticsearchHandler(es_index, task_queue, file_positions, schemas)
    while True:
        try:
            file_path, position = task_queue.get(timeout=1)
            ecs_batch, file_path, new_position = handler.process_xml_chunk(file_path, position)
            task_queue.put((ecs_batch, file_path, new_position))
        except Queue.Empty:
            time.sleep(0.1)

def main():
    manager = Manager()
    file_positions = manager.dict()
    task_queue = Queue()
    stop_event = manager.Event()
    schemas = XMLElasticsearchHandler(None, None, None, None).load_schemas()

    sender = Process(target=asyncio.run, args=(sender_process(task_queue, ES_INDEX, stop_event, file_positions),))
    sender.start()

    pool = Pool(processes=WORKER_COUNT, initializer=worker_process,
                initargs=(task_queue, ES_INDEX, file_positions, schemas))

    observer = Observer()
    handler = XMLElasticsearchHandler(ES_INDEX, task_queue, file_positions, schemas)
    observer.schedule(handler, path=XML_LOG_DIR, recursive=False)
    observer.start()

    print(f"Monitoring XML logs in {XML_LOG_DIR} with {WORKER_COUNT} workers for Elasticsearch")

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