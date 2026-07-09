import argparse

from schedule_scans import main as schedule_main
from process_scans import main as process_main
from csv_scan_export import main as export_main
from nessus_report_downloader import main as download_main
from nessus_api_query_scan import query_vulnerabilities
from utils import logger

def main():
    parser = argparse.ArgumentParser(description="Unified Nessus CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Schedule
    schedule_parser = subparsers.add_parser("schedule", help="Schedule scans")
    schedule_parser.set_defaults(func=schedule_main)

    # Process
    process_parser = subparsers.add_parser("process", help="Process scans")
    process_parser.set_defaults(func=process_main)

    # Export CSV
    export_parser = subparsers.add_parser("export_csv", help="Export to CSV")
    export_parser.add_argument("--folder-id", type=int, default=3)
    export_parser.add_argument("--days-ago", type=int)
    export_parser.set_defaults(func=export_main)

    # Download Reports
    download_parser = subparsers.add_parser("download", help="Download reports")
    download_parser.add_argument("-s", "--scan-id")
    download_parser.add_argument("-d", "--folder-id")
    download_parser.add_argument("-f", "--format", default="0")
    download_parser.add_argument("-c", "--chapter", default="1")
    download_parser.add_argument("--db-pass", default="nessus")
    download_parser.set_defaults(func=download_main)

    # Query Vulns
    query_parser = subparsers.add_parser("query", help="Query vulnerabilities")
    query_parser.add_argument("--scan-id", type=int)
    query_parser.set_defaults(func=query_vulnerabilities)

    args = parser.parse_args()
    if args.command:
        args.func(args) if "func" in args else logger.error("Invalid command")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()