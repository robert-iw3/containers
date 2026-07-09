#!/bin/python
import os
import argparse
import json
from datetime import datetime
from core.config import EMBEDDINGS_FILE
from core.ttp_mapper import TTPMapper
from core.report_parser import ReportParser

def main():
    print("""
 _______________  __  ___
/_  __/_  __/ _ \\/  |/  /__ ____  ___  ___ ____
 / /   / / / ___/ /|_/ / _ `/ _ \\/ _ \\/ -_) __/
/_/   /_/ /_/  /_/  /_/\\_,_/ .__/ .__/\\__/_/
      By @infosecn1nja    /_/  /_/
        """)

    parser = argparse.ArgumentParser(
        description="MITRE ATT&CK Threat Report Mapper with IOC Extraction and Summary"
    )
    parser.add_argument("--url", help="URL of the HTML-based threat report")
    parser.add_argument("--pdf", help="Path to the local PDF report")
    parser.add_argument("--output", choices=["json", "stix21"], help="Output format: json or stix21")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    mapper = TTPMapper()
    parser_util = ReportParser()

    # Load or generate MITRE mappings
    try:
        if not os.path.exists(EMBEDDINGS_FILE):
            if args.verbose:
                print("[*] MITRE mapping not found. Generating...")
            mapper.save_mappings()
        else:
            mapper.load_mappings()
    except Exception as e:
        print(f"[!] Failed to load/generate MITRE mappings: {str(e)}")
        exit(1)

    # Parse report
    report_content = ""
    source_info = {}

    try:
        if args.url:
            if args.verbose:
                print(f"[*] Fetching and converting report from URL: {args.url}")
            report_content = parser_util.fetch_and_convert_report(args.url)
            source_info = {"source_type": "url", "value": args.url}
        elif args.pdf:
            if args.verbose:
                print(f"[*] Extracting text from PDF: {args.pdf}")
            report_content = parser_util.convert_pdf_to_markdown(args.pdf)
            source_info = {"source_type": "pdf", "value": args.pdf}
        else:
            print("[!] Error: Please provide either --url or --pdf argument.")
            exit(1)
    except Exception as e:
        print(f"[!] Failed to parse report: {str(e)}")
        exit(1)

    # Analyze report
    try:
        result = mapper.map_threat_report(report_content, verbose=args.verbose)
        result["source_info"] = source_info
        result["summary"] = mapper.summarize_report(report_content, verbose=args.verbose)
    except Exception as e:
        print(str(e))
        exit(1)

    # Output result
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if args.output == "stix21":
            stix_bundle = mapper.generate_stix_bundle(result)
            output_file = f"output/bundle_{timestamp}.json"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(stix_bundle, f, indent=2 if args.verbose else None)
            print(f"\n[+] STIX 2.1 bundle written to: {output_file}")
        else:
            output_file = f"output/result_{timestamp}.json"
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2 if args.verbose else None)
            print(f"\n[+] JSON result written to: {output_file}")

    except Exception as e:
        print(f"[!] Failed to write output file: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
