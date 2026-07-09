import os
import time
import yaml
import asyncio
from elasticsearch_async import AsyncElasticsearch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from multiprocessing import Pool, Manager, Process, Queue
from datetime import datetime
import csv
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
ES_HOST = os.getenv('ES_HOST', 'http://localhost:9200')
ES_INDEX = os.getenv('ES_INDEX', 'csv-logs')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
BUFFER_TIMEOUT = float(os.getenv('BUFFER_TIMEOUT', 2.0))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', os.cpu_count() or 4))
DELIMITER = os.getenv('CSV_DELIMITER', ',')

class CSVElasticsearchHandler(FileSystemEventHandler):
    def __init__(self, es_index, task_queue, file_positions, schemas):
        self.es_index = es_index
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

    def transform_to_ecs(self, event, schema):
        ecs_template = {
            '@timestamp': event.get(schema['mappings']['ecs']['timestamp'], datetime.utcnow().isoformat()),
            'event': {
                'category': [schema['mappings']['ecs'].get('event_category', 'unknown')],
                'kind': 'event',
                'dataset': f'csv.{schema["name"]}',
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
            'csv': {
                'schema': schema['name'],
                'raw': event
            }
        }
        for key, value in schema['mappings']['ecs'].items():
            if key not in ['timestamp', 'event_id', 'event_category', 'source_ip', 'source_port', 'dest_ip', 'dest_port', 'protocol']:
                nested_ecs_keys = key.split('/')
                target = ecs_template
                for i, k in enumerate(nested_ecs_keys[:-1]):
                    target = target.setdefault(k, {})
                target[nested_ecs_keys[-1]] = event.get(value, '')
        return ecs_template

    def process_csv_chunk(self, file_path, position):
        ecs_batch = []
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
                        ecs_batch.append(self.transform_to_ecs(row, schema))
                        event_count += 1
                    except Exception as e:
                        print(f"Error parsing row in {file_path}: {e}")
                    if event_count >= BATCH_SIZE or f.tell() - position >= 1024 * 1024:
                        break
                new_position = f.tell()
                return ecs_batch, file_path, new_position
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
    handler = CSVElasticsearchHandler(es_index, task_queue, file_positions, schemas)
    while True:
        try:
            file_path, position = task_queue.get(timeout=1)
            ecs_batch, file_path, new_position = handler.process_csv_chunk(file_path, position)
            task_queue.put((ecs_batch, file_path, new_position))
        except Queue.Empty:
            time.sleep(0.1)

def main():
    manager = Manager()
    file_positions = manager.dict()
    task_queue = Queue()
    stop_event = manager.Event()
    schemas = CSVElasticsearchHandler(None, None, None, None).load_schemas()

    sender = Process(target=asyncio.run, args=(sender_process(task_queue, ES_INDEX, stop_event, file_positions),))
    sender.start()

    pool = Pool(processes=WORKER_COUNT, initializer=worker_process,
                initargs=(task_queue, ES_INDEX, file_positions, schemas))

    observer = Observer()
    handler = CSVElasticsearchHandler(ES_INDEX, task_queue, file_positions, schemas)
    observer.schedule(handler, path=CSV_LOG_DIR, recursive=False)
    observer.start()

    print(f"Monitoring CSV logs in {CSV_LOG_DIR} with {WORKER_COUNT} workers for Elasticsearch")

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