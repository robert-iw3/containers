import http.server
import socketserver
import os
from pathlib import Path
from prometheus_client import Gauge, generate_latest
from datetime import datetime
import json
import time

PORT = 9911
LOG_DIR = "/usr/local/zeek/logs"

# Prometheus metrics
METRICS = {
    "packets_received": Gauge("zeek_packets_received", "Total packets received by Zeek"),
    "packets_dropped": Gauge("zeek_packets_dropped", "Total packets dropped by Zeek"),
    "capture_loss_percent": Gauge("zeek_capture_loss_percent", "Percentage of packet capture loss"),
    "memory_used_mb": Gauge("zeek_memory_used_mb", "Memory used by Zeek in MB")
}

class MetricsHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(generate_latest())
        else:
            self.send_response(404)
            self.end_headers()

def parse_stats_log():
    """Parse stats.log for packet and memory metrics."""
    stats_file = Path(LOG_DIR) / "stats.log"
    stats = {"packets_received": 0, "packets_dropped": 0, "memory_used_mb": 0}

    if not stats_file.exists():
        return stats

    try:
        with open(stats_file, 'r') as f:
            lines = f.readlines()
            if not lines:
                return stats
            # Parse the last line of stats.log (JSON format due to enable_json_logs)
            last_line = lines[-1].strip()
            data = json.loads(last_line)
            stats["packets_received"] = float(data.get("pkts_recv", 0))
            stats["packets_dropped"] = float(data.get("pkts_dropped", 0))
            stats["memory_used_mb"] = float(data.get("mem", 0))
    except Exception as e:
        print(f"Error parsing stats.log: {e}")
    return stats

def parse_capture_loss_log():
    """Parse capture-loss.log for capture loss percentage."""
    loss_file = Path(LOG_DIR) / "capture-loss.log"
    capture_loss_percent = 0.0

    if not loss_file.exists():
        return capture_loss_percent

    try:
        with open(loss_file, 'r') as f:
            lines = f.readlines()
            if not lines:
                return capture_loss_percent
            # Parse the last line (JSON format)
            last_line = lines[-1].strip()
            data = json.loads(last_line)
            capture_loss_percent = float(data.get("percent_lost", 0.0))
    except Exception as e:
        print(f"Error parsing capture-loss.log: {e}")
    return capture_loss_percent

def update_metrics():
    """Update Prometheus metrics from log files."""
    stats = parse_stats_log()
    capture_loss_percent = parse_capture_loss_log()

    METRICS["packets_received"].set(stats["packets_received"])
    METRICS["packets_dropped"].set(stats["packets_dropped"])
    METRICS["memory_used_mb"].set(stats["memory_used_mb"])
    METRICS["capture_loss_percent"].set(capture_loss_percent)

def main():
    # Update metrics initially and periodically
    update_metrics()
    while True:
        try:
            with socketserver.TCPServer(("", PORT), MetricsHandler) as httpd:
                print(f"Serving Zeek metrics at port {PORT}")
                httpd.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
            time.sleep(10)  # Retry after delay

if __name__ == "__main__":
    main()