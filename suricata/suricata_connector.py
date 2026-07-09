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
LOG_DIR = os.getenv('LOG_DIR', '/var/log/suricata')
SPLUNK_ENABLED = os.getenv('SPLUNK_ENABLED', 'false').lower() == 'true'
SPLUNK_HEC_URL = os.getenv('SPLUNK_HEC_URL', 'https://your-splunk-host:8088/services/collector/event')
SPLUNK_TOKEN = os.getenv('SPLUNK_TOKEN', 'your-splunk-hec-token')
ES_ENABLED = os.getenv('ES_ENABLED', 'false').lower() == 'true'
ES_HOST = os.getenv('ES_HOST', 'http://localhost:9200')
ES_INDEX = os.getenv('ES_INDEX', 'suricata-logs')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))
BUFFER_TIMEOUT = float(os.getenv('BUFFER_TIMEOUT', 5.0))
WORKER_COUNT = int(os.getenv('WORKER_COUNT', os.cpu_count() or 4))

class LogHandler(FileSystemEventHandler):
    def __init__(self, splunk_url, splunk_token, es_index, task_queue, file_positions):
        self.splunk_url = splunk_url
        self.splunk_token = splunk_token
        self.es_index = es_index
        self.task_queue = task_queue
        self.file_positions = file_positions

    def transform_to_ecs(self, event):
        """Transform Suricata event to Elastic Common Schema (ECS)."""
        event_type = event.get('event_type', 'unknown')
        ecs_template = {
            '@timestamp': event.get('timestamp', datetime.utcnow().isoformat()),
            'event': {
                'category': ['network'],
                'kind': 'event',
                'dataset': f'suricata.{event_type}',
                'id': event.get('flow_id', ''),
            },
            'source': {
                'ip': event.get('src_ip', ''),
                'port': event.get('src_port', 0),
            },
            'destination': {
                'ip': event.get('dest_ip', ''),
                'port': event.get('dest_port', 0),
            },
            'network': {
                'type': 'ipv4' if ':' not in event.get('src_ip', '') else 'ipv6',
                'protocol': event.get('proto', '').lower(),
            },
            'suricata': {
                'event_type': event_type,
                'raw': event
            }
        }

        if event_type == 'flow':
            ecs_template['event']['category'].append('session')
            ecs_template['event']['type'] = ['connection']
            ecs_template['source']['bytes'] = event.get('bytes_toclient', 0)
            ecs_template['destination']['bytes'] = event.get('bytes_toserver', 0)
            ecs_template['source']['packets'] = event.get('pkts_toclient', 0)
            ecs_template['destination']['packets'] = event.get('pkts_toserver', 0)
            ecs_template['network']['application'] = event.get('app_proto', '')
            ecs_template['event']['duration'] = event.get('flow', {}).get('duration', 0) * 1_000_000_000
            ecs_template['network']['status'] = event.get('state', '')
        elif event_type == 'http':
            ecs_template['event']['category'].append('web')
            ecs_template['event']['type'] = ['access']
            ecs_template['http'] = {
                'request': {
                    'method': event.get('http_method', '').lower(),
                    'referrer': event.get('http_referer', ''),
                    'user_agent': event.get('http_user_agent', ''),
                    'body': {'bytes': event.get('request_body_len', 0)}
                },
                'response': {
                    'status_code': event.get('status', 0),
                    'body': {'bytes': event.get('response_body_len', 0)}
                }
            }
            ecs_template['url'] = {
                'domain': event.get('hostname', ''),
                'path': event.get('url', '')
            }
        elif event_type == 'alert':
            ecs_template['event']['category'].append('intrusion_detection')
            ecs_template['event']['type'] = ['alert']
            ecs_template['event']['severity'] = event.get('severity', 0)
            ecs_template['rule'] = {
                'name': event.get('signature', ''),
                'id': event.get('signature_id', '')
            }
            ecs_template['suricata']['alert'] = {
                'category': event.get('category', ''),
                'action': event.get('action', '')
            }

        return ecs_template

    def transform_to_cim(self, event):
        """Transform Suricata event to Splunk CIM (Network Traffic, Web, or IDS/IPS)."""
        event_type = event.get('event_type', 'unknown')
        cim_template = {
            'time': event.get('timestamp', time.time()),
            'source': event.get('src_ip', ''),
            'src_port': event.get('src_port', 0),
            'dest': event.get('dest_ip', ''),
            'dest_port': event.get('dest_port', 0),
            'protocol': event.get('proto', '').lower(),
            'event_id': event.get('flow_id', ''),
            'vendor_product': 'Suricata',
            'event_type': event_type
        }

        if event_type == 'flow':
            cim_template['action'] = 'allowed' if event.get('state') in ['established', 'closed'] else 'blocked'
            cim_template['bytes_in'] = event.get('bytes_toserver', 0)
            cim_template['bytes_out'] = event.get('bytes_toclient', 0)
            cim_template['packets_in'] = event.get('pkts_toserver', 0)
            cim_template['packets_out'] = event.get('pkts_toclient', 0)
            cim_template['app'] = event.get('app_proto', '')
            cim_template['duration'] = event.get('flow', {}).get('duration', 0) * 1000
            cim_template['connection_state'] = event.get('state', '')
        elif event_type == 'http':
            cim_template['http_method'] = event.get('http_method', '').lower()
            cim_template['status'] = event.get('status', 0)
            cim_template['url'] = event.get('hostname', '') + event.get('url', '')
            cim_template['dest'] = event.get('hostname', cim_template['dest'])
            cim_template['http_user_agent'] = event.get('http_user_agent', '')
            cim_template['http_referer'] = event.get('http_referer', '')
            cim_template['bytes_in'] = event.get('request_body_len', 0)
            cim_template['bytes_out'] = event.get('response_body_len', 0)
        elif event_type == 'alert':
            cim_template['signature'] = event.get('signature', '')
            cim_template['signature_id'] = event.get('signature_id', '')
            cim_template['category'] = event.get('category', '')
            cim_template['severity'] = event.get('severity', 0)
            cim_template['action'] = event.get('action', '')

        return {'event': cim_template, 'sourcetype': f'suricata:{event_type}'}

    def process_log_lines(self, file_path, position):
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
                        event_type = event.get('event_type')
                        if event_type not in ['flow', 'http', 'alert']:
                            continue
                        if ES_ENABLED:
                            ecs_batch.append(self.transform_to_ecs(event))
                        if SPLUNK_ENABLED:
                            cim_batch.append(self.transform_to_cim(event))
                    except (ValueError, KeyError) as e:
                        print(f"Error processing line in {file_path}: {e}")
                return ecs_batch, cim_batch, file_path, new_position
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return [], [], file_path, position

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('eve.json'):
            return

        file_path = event.src_path
        with self.file_positions.get_lock():
            position = self.file_positions.get(file_path, 0)
        self.task_queue.put((file_path, position))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('eve.json'):
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
                while not task_queue.empty():
                    ecs, cim, file_path, new_position = task_queue.get()
                    ecs_batch.extend(ecs)
                    cim_batch.extend(cim)
                    with file_positions.get_lock():
                        file_positions[file_path] = new_position

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

                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Sender error: {e}")

        if es:
            await es.close()

def worker_process(task_queue, splunk_url, splunk_token, es_index, file_positions):
    """Worker process for parsing and transforming log lines."""
    handler = LogHandler(splunk_url, splunk_token, es_index, task_queue, file_positions)
    while True:
        try:
            file_path, position = task_queue.get(timeout=1)
            ecs_batch, cim_batch, file_path, new_position = handler.process_log_lines(file_path, position)
            task_queue.put((ecs_batch, cim_batch, file_path, new_position))
        except Queue.Empty:
            time.sleep(0.1)

def main():
    manager = Manager()
    file_positions = manager.dict()
    task_queue = Queue()
    stop_event = manager.Event()

    sender = Process(target=asyncio.run, args=(sender_process(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, ES_INDEX, stop_event, file_positions),))
    sender.start()

    pool = Pool(processes=WORKER_COUNT, initializer=worker_process,
                initargs=(task_queue, SPLUNK_HEC_URL, SPLUNK_TOKEN, ES_INDEX, file_positions))

    observer = Observer()
    handler = LogHandler(SPLUNK_HEC_URL, SPLUNK_TOKEN, ES_INDEX, task_queue, file_positions)
    observer.schedule(handler, path=LOG_DIR, recursive=False)
    observer.start()

    print(f"Monitoring Suricata logs in {LOG_DIR} with {WORKER_COUNT} workers for Splunk: {SPLUNK_ENABLED}, Elasticsearch: {ES_ENABLED}")

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