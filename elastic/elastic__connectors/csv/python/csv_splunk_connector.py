import os
import time
import yaml
import asyncio
import aiohttp
import csv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from multiprocessing import Pool, Manager, Process, Queue
from datetime import datetime
try:
    import orjson
    JSON_DUMPS = orjson.dumps
except ImportError:
    import json
    JSON_DUMPS = json.dumps
import magic

# Configuration from environment variables
CSV_LOG_DIR = os.getenv('CSV_LOG_DIR', '/var/log/csv_data')
SCHEMAS_FILE = os.getenv('SCHEMAS_FILE', '/app/schemas.yaml')
SPLUNK_HEC_URL = os.getenv('SPLUNK_HEC_URL', 'https://your-splunk-host:8088/services/collector/event')
SPLUNK_TOKEN = os.getenv('SPLUNK_TOKEN', 'your-splunk-hec-token')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
BUFFER_TIMEOUT = float(os.getenv('BUFFER_TIMEOUT', 2.0))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', os.cpu_count() or 4))
DELIMITER = os.getenv('CSV_DELIMITER', ',')

class CSVSplunkHandler(FileSystemEventHandler):
    def __init__(self, splunk_url, splunk_token, task_queue, file_positions, schemas):
        self.splunk_url = splunk_url
        self.splunk_token = splunk_token
        self.task_queue = task_queue
        self.file_positions = file_positions
        self.schemas = schemas

    def load_schemas(self):
        with open(SCHEMAS_FILE, 'r') as f:
            return yaml.safe_load(f)['schemas']

    def get_schema(self, event):
        for schema in self.schemas:
            if event.get(schema['schema_key'], '') == schema['schema_value']:
                return schema
        return None

    def detect_delimiter(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(1024).decode('utf-8', errors='ignore')
                for delim in [',', ';', '\t', '|']:
                    if delim in sample and len(sample.split(delim)) > 1:
                        return delim
        except Exception:
            pass
        return DELIMITER

    def transform_to_cim(self, event, schema):
        cim_template = {
            'time': event.get(schema['mappings']['cim']['time'], str(time.time())),
            'source': event.get(schema['mappings']['cim'].get('source', ''), ''),
            'src_port': int(event.get(schema['mappings']['cim'].get('src_port', '0'), 0)),
            'dest': event.get(schema['mappings']['cim'].get('dest', ''), ''),
            'dest_port': int(event.get(schema['mappings']['cim'].get('dest_port', '0'), 0)),
            'protocol': event.get(schema['mappings']['cim'].get('protocol', ''), '').lower(),
            'event_id': event.get(schema['mappings']['cim'].get('event_id', 'id'), ''),
            'vendor_product': 'CSV_Connector',
            'schema': schema['name']
        }
        for key, value in schema['mappings']['cim'].items():
            if key not in ['time', 'event_id', 'source', 'src_port', 'dest', 'dest_port', 'protocol']:
                cim_template[key] = event.get(value, '')
        return {'event': cim_template, 'sourcetype': f'csv:{schema["name"]}'}

    def process_csv_chunk(self, file_path, position):
        cim_batch = []
        try:
            delimiter = self.detect_delimiter(file_path)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(position)
                reader = csv.DictReader(f, delimiter=delimiter)
                event_count = 0
                for row in reader:
                    try:
                        schema = self.get_schema(row)
                        if not schema:
                            print(f"No schema found for event in {file_path}")
                            continue
                        cim_batch.append(self.transform_to_cim(row, schema))
                        event_count += 1
                    except Exception as e:
                        print(f"Error parsing row in {file_path}: {e}")
                    if event_count >= BATCH_SIZE or f.tell() - position >= 1024 * 1024:
                        break
                new_position = f.tell()
                return cim_batch, file_path, new_position
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return [], file_path, position

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.csv'):
            return
        file_path = event.src_path
        with self.file_positions.get_lock():
            position = self.file_positions.get(file_path, 0)
        self.task_queue.put((file_path, position))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.csv'):
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
    handler = CSVSplunkHandler(splunk_url, splunk_token, task_queue, file_positions, schemas)
    while True:
        try:
            file_path, position = task_queue.get(timeout=1)
            cim_batch, file_path, new_position = handler.process_csv_chunk(file_path, position)
            task_queue.put((cim_batch, file_path, new_position))
        except Queue.Empty:
            time.sleep(0.1)

def main():
    manager = Manager()
    file_positions = manager.dict()
    task_queue = Queue()
    stop_event = manager.Event()
    schemas = CSVSplunkHandler(None, None, None, None, None).load_schemas()

    sender = Process(target=asyncio.run, args=(sender_process(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, stop_event, file_positions),))
    sender.start()

    pool = Pool(processes=WORKER_COUNT, initializer=worker_process,
                initargs=(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, file_positions, schemas))

    observer = Observer()
    handler = CSVSplunkHandler(SPLUNK_HEC_URL, SPLUNK_TOKEN, task_queue, file_positions, schemas)
    observer.schedule(handler, path=CSV_LOG_DIR, recursive=False)
    observer.start()

    print(f"Monitoring CSV logs in {CSV_LOG_DIR} with {WORKER_COUNT} workers for Splunk")

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