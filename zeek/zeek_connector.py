import os
import time
import json
import asyncio
import aiohttp
from elasticsearch_async import AsyncElasticsearch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from multiprocessing import Pool, Manager, Process, Queue
from datetime import datetime
try:
    import orjson
    JSON_LOADS = orjson.loads
except ImportError:
    JSON_LOADS = json.loads

# Configuration from environment variables or deploy_config.yaml
ZEEK_LOG_DIR = os.getenv('ZEEK_LOG_DIR', '/var/log/zeek')
SPLUNK_ENABLED = os.getenv('SPLUNK_ENABLED', 'false').lower() == 'true'
SPLUNK_HEC_URL = os.getenv('SPLUNK_HEC_URL', 'https://your-splunk-host:8088/services/collector/event')
SPLUNK_TOKEN = os.getenv('SPLUNK_TOKEN', 'your-splunk-hec-token')
ES_ENABLED = os.getenv('ES_ENABLED', 'false').lower() == 'true'
ES_HOST = os.getenv('ES_HOST', 'http://localhost:9200')
ES_INDEX = os.getenv('ES_INDEX', 'zeek-logs')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
BUFFER_TIMEOUT = float(os.getenv('BUFFER_TIMEOUT', 5.0))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', os.cpu_count() or 4))

class LogHandler(FileSystemEventHandler):
    def __init__(self, splunk_url, splunk_token, es_index, task_queue, file_positions):
        self.splunk_url = splunk_url
        self.splunk_token = splunk_token
        self.es_index = es_index
        self.task_queue = task_queue
        self.file_positions = file_positions  # Shared dictionary for file positions

    def transform_to_ecs(self, event, log_type):
        """Transform Zeek log event to Elastic Common Schema (ECS)."""
        ecs_template = {
            '@timestamp': datetime.utcfromtimestamp(event['ts']).isoformat(),
            'event': {
                'category': ['network'],
                'type': ['connection'] if log_type == 'conn' else ['access'],
                'kind': 'event',
                'dataset': f'zeek.{log_type}',
                'id': event.get('uid', ''),
                'duration': event.get('duration', 0) * 1_000_000_000
            },
            'source': {
                'ip': event.get('id.orig_h', ''),
                'port': event.get('id.orig_p', 0),
                'bytes': event.get('orig_bytes', 0),
                'packets': event.get('orig_pkts', 0),
                'local': event.get('local_orig', False)
            },
            'destination': {
                'ip': event.get('id.resp_h', ''),
                'port': event.get('id.resp_p', 0),
                'bytes': event.get('resp_bytes', 0),
                'packets': event.get('resp_pkts', 0),
                'local': event.get('local_resp', False)
            },
            'network': {
                'type': 'ipv4' if ':' not in event.get('id.orig_h', '') else 'ipv6',
                'protocol': event.get('proto', 'unknown').lower(),
                'application': event.get('service', ''),
                'status': event.get('conn_state', ''),
                'bytes_dropped': event.get('missed_bytes', 0)
            },
            'zeek': {
                'log_type': log_type,
                'raw': event,
                'history': event.get('history', '')
            }
        }

        if log_type == 'http':
            ecs_template['event']['category'].append('web')
            ecs_template['http'] = {
                'request': {
                    'method': event.get('method', '').lower(),
                    'referrer': event.get('referrer', ''),
                    'user_agent': event.get('user_agent', ''),
                    'body': {'bytes': event.get('request_body_len', 0)}
                },
                'response': {
                    'status_code': event.get('status_code', 0),
                    'status_reason': event.get('status_msg', ''),
                    'body': {'bytes': event.get('response_body_len', 0)}
                },
                'version': event.get('version', '')
            }
            ecs_template['url'] = {
                'domain': event.get('host', ''),
                'path': event.get('uri', '')
            }
            if 'username' in event:
                ecs_template['user'] = {'name': event['username']}
            if 'tags' in event:
                ecs_template['labels'] = list(event['tags'])

        return ecs_template

    def transform_to_cim(self, event, log_type):
        """Transform Zeek log event to Splunk CIM (Network Traffic or Web)."""
        cim_template = {
            'time': event['ts'],
            'source': event.get('id.orig_h', ''),
            'src_port': event.get('id.orig_p', 0),
            'dest': event.get('id.resp_h', ''),
            'dest_port': event.get('id.resp_p', 0),
            'protocol': event.get('proto', 'unknown').lower(),
            'event_id': event.get('uid', ''),
            'vendor_product': 'Zeek',
            'log_type': log_type,
            'app': event.get('service', ''),
            'bytes_in': event.get('orig_bytes', 0),
            'bytes_out': event.get('resp_bytes', 0),
            'packets_in': event.get('orig_pkts', 0),
            'packets_out': event.get('resp_pkts', 0),
            'bytes_dropped': event.get('missed_bytes', 0),
            'history': event.get('history', '')
        }

        if log_type == 'conn':
            cim_template['action'] = 'allowed' if event.get('conn_state') in ['SF', 'S0'] else 'blocked'
            cim_template['connection_state'] = event.get('conn_state', '')
            cim_template['duration'] = event.get('duration', 0) * 1000
        elif log_type == 'http':
            cim_template['http_method'] = event.get('method', '').lower()
            cim_template['status'] = event.get('status_code', 0)
            cim_template['url'] = event.get('host', '') + event.get('uri', '')
            cim_template['dest'] = event.get('host', cim_template['dest'])
            cim_template['http_user_agent'] = event.get('user_agent', '')
            cim_template['http_referer'] = event.get('referrer', '')
            cim_template['bytes_in'] = event.get('request_body_len', 0)
            cim_template['bytes_out'] = event.get('response_body_len', 0)
            cim_template['http_version'] = event.get('version', '')
            cim_template['http_status_msg'] = event.get('status_msg', '')
            if 'username' in event:
                cim_template['user'] = event['username']

        return {'event': cim_template, 'sourcetype': f'zeek:{log_type}'}

    def process_log_lines(self, file_path, log_type, position):
        """Process a chunk of log lines in a worker process."""
        ecs_batch = []
        cim_batch = []
        try:
            with open(file_path, 'r') as f:
                f.seek(position)
                lines = f.readlines(1024 * 1024)  # Read 1MB chunks
                new_position = f.tell()
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        event = JSON_LOADS(line)
                        if log_type not in ['conn', 'http']:
                            continue
                        if ES_ENABLED:
                            ecs_batch.append(self.transform_to_ecs(event, log_type))
                        if SPLUNK_ENABLED:
                            cim_batch.append(self.transform_to_cim(event, log_type))
                    except (ValueError, KeyError) as e:
                        print(f"Error processing line in {file_path}: {e}")
                return ecs_batch, cim_batch, file_path, new_position
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return [], [], file_path, position

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.log'):
            return

        file_path = event.src_path
        log_type = os.path.basename(file_path).split('.')[0]
        with self.file_positions.get_lock():
            position = self.file_positions.get(file_path, 0)
        self.task_queue.put((file_path, log_type, position))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            with self.file_positions.get_lock():
                self.file_positions[event.src_path] = 0
            self.on_modified(event)

async def sender_process(task_queue, splunk_url, splunk_token, es_index, stop_event, file_positions):
    """Dedicated process for sending batches to Splunk and Elasticsearch."""
    es = AsyncElasticsearch([ES_HOST]) if ES_ENABLED else None
    async with aiohttp.ClientSession() as session:
        ecs_batch = []
        cim_batch = []
        last_flush = time.time()

        while not stop_event.is_set():
            try:
                # Get processed batches from workers
                while not task_queue.empty():
                    ecs, cim, file_path, new_position = task_queue.get()
                    ecs_batch.extend(ecs)
                    cim_batch.extend(cim)
                    with file_positions.get_lock():
                        file_positions[file_path] = new_position

                # Send batches when full or timed out
                if (len(ecs_batch) >= BATCH_SIZE or len(cim_batch) >= BATCH_SIZE or
                    time.time() - last_flush > BUFFER_TIMEOUT):
                    if cim_batch and SPLUNK_ENABLED:
                        headers = {
                            'Authorization': f'Splunk {splunk_token}',
                            'Content-Type': 'application/json'
                        }
                        async with session.post(splunk_url, headers=headers, json=cim_batch, timeout=10) as response:
                            if response.status != 200:
                                print(f"Splunk error: {await response.text()}")
                        cim_batch = []

                    if ecs_batch and ES_ENABLED:
                        actions = [{'_index': es_index, '_source': event} for event in ecs_batch]
                        await es.bulk(actions)
                        ecs_batch = []

                    last_flush = time.time()

                await asyncio.sleep(0.1)  # Yield control
            except Exception as e:
                print(f"Sender error: {e}")

        if es:
            await es.close()

def worker_process(task_queue, splunk_url, splunk_token, es_index, file_positions):
    """Worker process for parsing and transforming log lines."""
    handler = LogHandler(splunk_url, splunk_token, es_index, task_queue, file_positions)
    while True:
        try:
            file_path, log_type, position = task_queue.get(timeout=1)
            ecs_batch, cim_batch, file_path, new_position = handler.process_log_lines(file_path, log_type, position)
            task_queue.put((ecs_batch, cim_batch, file_path, new_position))
        except Queue.Empty:
            time.sleep(0.1)  # Avoid busy looping

def main():
    manager = Manager()
    file_positions = manager.dict()  # Shared file positions
    task_queue = Queue()  # Queue for tasks and processed batches
    stop_event = manager.Event()

    # Start sender process
    sender = Process(target=asyncio.run, args=(sender_process(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, ES_INDEX, stop_event, file_positions),))
    sender.start()

    # Start worker pool
    pool = Pool(processes=WORKER_COUNT, initializer=worker_process,
                initargs=(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, ES_INDEX, file_positions))

    # Start watchdog observer
    observer = Observer()
    handler = LogHandler(SPLUNK_HEC_URL, SPLUNK_TOKEN, ES_INDEX, task_queue, file_positions)
    observer.schedule(handler, path=ZEEK_LOG_DIR, recursive=False)
    observer.start()

    print(f"Monitoring Zeek logs in {ZEEK_LOG_DIR} with {WORKER_COUNT} workers for Splunk: {SPLUNK_ENABLED}, Elasticsearch: {ES_ENABLED}")

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