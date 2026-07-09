#!/usr/bin/python3
"""
Nessus File Parser
Parses Nessus scan results (.nessus XML) into spreadsheet formats (XLSX/CSV).
Integrates with Nessus API to fetch scans.

Requirements: Python 3.9+, xml.etree.ElementTree, xlsxwriter, csv, argparse, os, datetime, dateparser, ipaddress, re, requests
License: GNU General Public License v3.0 (https://www.gnu.org/licenses/)

Usage:

podman run --rm -v $(pwd)/exports:/exports:z -v $(pwd)/output:/output:z python:3.12 \
  bash -c "pip install xlsxwriter dateparser ipaddress requests && \
  python /app/nessus-parser.py --api-url https://api-fw.testing.io:8088 \
  --api-keys '$(cat /run/secrets/nessus_api_keys)' --export-dir /exports --output /output/nessus_report.xlsx"

pip install xlsxwriter dateparser ipaddress requests

python3 nessus-parser.py --api-url https://api-fw.testing.io:8088 \
  --api-keys "accessKey=your_access_key;secretKey=your_secret_key" \
  --export-dir ./exports --output ./output/nessus_report.xlsx
"""

import xml.etree.ElementTree as ET
import xlsxwriter
import csv
import argparse
import os
import datetime
import dateparser
import ipaddress
import re
import sys
import traceback
import requests
from html import escape

# Global variables for error detection and output columns
error_pluginId_list = ['10428', '21745', '24786', '26917', '35705', '104410', '110385', '117885']
scan_error_list = []
scan_time_list = []
audit_error_description_list = ["This audit check is not running as"]
audit_error_list = []

# CVSS3 and CVSS2 key-value dictionaries
cvss3_keyvalue_dict = {
    'CVSSv3 Base Score': 'cvss3_base_score',
    'CVSSv3 Temporal Score': 'cvss3_temporal_score',
    'CVSSv3 Vector': 'cvss3_vector',
    'CVSSv3 Exploitability Score': 'cvss3_exploitability_score',
    'CVSSv3 Impact Score': 'cvss3_impact_score'
}

cvss2_keyvalue_dict = {
    'CVSSv2 Base Score': 'cvss_base_score',
    'CVSSv2 Temporal Score': 'cvss_temporal_score',
    'CVSSv2 Vector': 'cvss_vector',
    'CVSSv2 Exploitability Score': 'cvss_exploitability_score',
    'CVSSv2 Impact Score': 'cvss_impact_score'
}

# Output column definitions
out_column_num_dict = {
    'Plugin Name': 0,
    'Product Name': 1,
    'Description': 2,
    'Synopsis': 3,
    'Plugin Output': 4,
    'Solution': 5,
    'Patch Publication Date': 6,
    'Plugin Publication Date': 7,
    'Plugin Modification Date': 8,
    'Target Name': 9,
    'FQDN': 10,
    'Hostname': 11,
    'IP': 12,
    'Port': 13,
    'Protocol': 14,
    'Nessus Plugin ID': 15,
    'Associated CVEs': 16,
    'Reference Links': 17,
    'Exploit Available': 18,
    'Operating Systems': 19,
    'Nessus Severity Rating': 20,
    'CVSSv3 Base Score': 21,
    'CVSSv3 Temporal Score': 22,
    'CVSSv3 Vector': 23,
    'CVSSv3 Exploitability Score': 24,
    'CVSSv3 Impact Score': 25,
    'CVSSv2 Base Score': 26,
    'CVSSv2 Temporal Score': 27,
    'CVSSv2 Vector': 28,
    'CVSSv2 Exploitability Score': 29,
    'CVSSv2 Impact Score': 30
}

out_column_width_dict = {
    'Plugin Name': 30,
    'Product Name': 30,
    'Description': 50,
    'Synopsis': 50,
    'Plugin Output': 50,
    'Solution': 50,
    'Patch Publication Date': 20,
    'Plugin Publication Date': 20,
    'Plugin Modification Date': 20,
    'Target Name': 20,
    'FQDN': 20,
    'Hostname': 20,
    'IP': 15,
    'Port': 10,
    'Protocol': 10,
    'Nessus Plugin ID': 15,
    'Associated CVEs': 30,
    'Reference Links': 50,
    'Exploit Available': 15,
    'Operating Systems': 30,
    'Nessus Severity Rating': 20,
    'CVSSv3 Base Score': 20,
    'CVSSv3 Temporal Score': 20,
    'CVSSv3 Vector': 30,
    'CVSSv3 Exploitability Score': 20,
    'CVSSv3 Impact Score': 20,
    'CVSSv2 Base Score': 20,
    'CVSSv2 Temporal Score': 20,
    'CVSSv2 Vector': 30,
    'CVSSv2 Exploitability Score': 20,
    'CVSSv2 Impact Score': 20
}

def fix_spacing_issues(text):
    """Sanitize text input to remove extra whitespace and escape HTML."""
    if text is None:
        return ""
    text = escape(text.strip())
    text = re.sub(r'\s+', ' ', text)
    return text

def print_scan_errors(file, report_name, plugin_id, plugin_name, plugin_output, target_name, fqdn, ip):
    """Log scan errors for specific plugin IDs."""
    if plugin_id in error_pluginId_list:
        scan_error_list.append({
            'fileName': file,
            'reportName': report_name,
            'pluginId': plugin_id,
            'pluginName': plugin_name,
            'pluginOutput': plugin_output,
            'target_name': target_name,
            'fqdn': fqdn,
            'ip': ip
        })

def print_audit_check_error(file, report_name, plugin_id, plugin_name, plugin_output, target_name, fqdn, ip):
    """Log audit check errors based on description."""
    if any(error_desc in plugin_output for error_desc in audit_error_description_list):
        audit_error_list.append({
            'fileName': file,
            'reportName': report_name,
            'pluginId': plugin_id,
            'pluginName': plugin_name,
            'pluginOutput': plugin_output,
            'target_name': target_name,
            'fqdn': fqdn,
            'ip': ip
        })

def fetch_scans(api_url, api_keys, export_dir):
    """Fetch scans from Nessus API and save to export_dir."""
    try:
        response = requests.get(f"{api_url}/scans", headers={'X-ApiKeys': api_keys}, timeout=10)
        response.raise_for_status()
        scans = response.json().get('scans', [])
        for scan in scans:
            scan_id = scan['id']
            export_response = requests.post(
                f"{api_url}/scans/{scan_id}/export",
                headers={'X-ApiKeys': api_keys},
                json={'format': 'nessus'},
                timeout=10
            )
            export_response.raise_for_status()
            token = export_response.json()['file']
            # Poll for export readiness
            for _ in range(10):  # Retry up to 10 times
                status_response = requests.get(
                    f"{api_url}/scans/{scan_id}/export/{token}/status",
                    headers={'X-ApiKeys': api_keys},
                    timeout=5
                )
                status_response.raise_for_status()
                if status_response.json()['status'] == 'ready':
                    break
                import time
                time.sleep(2)
            download_response = requests.get(
                f"{api_url}/scans/{scan_id}/export/{token}/download",
                headers={'X-ApiKeys': api_keys},
                timeout=30
            )
            download_response.raise_for_status()
            scan_file = os.path.join(export_dir, f"scan_{scan_id}.nessus")
            with open(scan_file, 'wb') as f:
                f.write(download_response.content)
            print(f"Saved scan {scan_id} to {scan_file}")
    except requests.RequestException as e:
        print(f"Failed to fetch scans: {e}")
        return False
    return True

def main():
    """Parse Nessus XML files and generate XLSX/CSV reports."""
    parser = argparse.ArgumentParser(description='Nessus File Parser')
    parser.add_argument('--files', nargs='*', default=[], help='Nessus XML files to parse')
    parser.add_argument('--api-url', default='https://api-fw.testing.io:8088', help='Nessus API URL')
    parser.add_argument('--api-keys', help='Nessus API keys (accessKey=;secretKey=)')
    parser.add_argument('--export-dir', default='/exports', help='Directory for scan exports')
    parser.add_argument('--output', '-o', default='/output/nessus_report.xlsx', help='Output file (XLSX/CSV)')
    args = parser.parse_args()

    try:
        # Validate output directory
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, mode=0o755)

        # Determine output format
        out_file_name = args.output
        out_format = 'csv' if out_file_name.lower().endswith('.csv') else 'xlsx'

        # Initialize output file
        if out_format == 'xlsx':
            workbook = xlsxwriter.Workbook(out_file_name)
            ws = workbook.add_worksheet('Vulnerability Details')
            ws_audit_error = workbook.add_worksheet('Compliance Audit Errors')
            ws_time = workbook.add_worksheet('Summary Time')
            ws_scan_errors = workbook.add_worksheet('Summary Errors')
            bold = workbook.add_format({'bold': True, 'align': 'center'})
            centerfont = workbook.add_format({'align': 'center'})
            leftfont = workbook.add_format({'align': 'left'})
            datefont = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss', 'align': 'center'})
        else:
            csv_file = open(out_file_name, 'w', newline='', encoding='utf-8')
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(out_column_num_dict.keys())

        # Write column headers for XLSX
        if out_format == 'xlsx':
            for col_name, col_num in out_column_num_dict.items():
                ws.write(0, col_num, col_name, bold)
                ws_audit_error.write(0, col_num, col_name, bold)
                ws.set_column(col_num, col_num, out_column_width_dict[col_name])
                ws_audit_error.set_column(col_num, col_num, out_column_width_dict[col_name])

        # Fetch scans from API if keys provided
        files = args.files
        if args.api_keys and args.api_url:
            if not os.path.exists(args.export_dir):
                os.makedirs(args.export_dir, mode=0o755)
            fetch_scans(args.api_url, args.api_keys, args.export_dir)
            files.extend([
                os.path.join(args.export_dir, f)
                for f in os.listdir(args.export_dir)
                if f.endswith('.nessus') and os.path.isfile(os.path.join(args.export_dir, f))
            ])

        if not files:
            print("No files to parse.")
            if out_format == 'xlsx':
                workbook.close()
            else:
                csv_file.close()
            sys.exit(1)

        row_count = 1
        row_count_audit_error = 1

        for file in files:
            print(f'Parsing file: {file}')
            if not os.path.exists(file):
                print(f'File not found: {file}')
                continue

            try:
                context = ET.iterparse(file, events=("start", "end"))
                context = iter(context)
                event, root = next(context)
                ns = {'cm': 'http://www.nessus.org/cm'}

                for event, elem in context:
                    if event == 'end' and elem.tag == 'Report':
                        report_name = elem.get('name')
                        for host in elem.findall('ReportHost'):
                            ip = host.get('name')
                            try:
                                ipaddress.ip_address(ip)
                            except ValueError:
                                print(f"Invalid IP address in file {file}: {ip}")
                                continue

                            target_info_dict = {'IP Address': ip}
                            for host_prop in host.findall('HostProperties/tag'):
                                target_info_dict[host_prop.get('name')] = fix_spacing_issues(host_prop.text)

                            for item in host.findall('ReportItem'):
                                plugin_id = item.get('pluginID')
                                plugin_name = fix_spacing_issues(item.get('pluginName'))
                                port = item.get('port')
                                protocol = item.get('protocol')
                                hostname = target_info_dict.get('host-fqdn', target_info_dict.get('hostname', 'N/A'))

                                plugin_output = fix_spacing_issues(item.findtext('plugin_output'))
                                description = fix_spacing_issues(item.findtext('description'))
                                synopsis = fix_spacing_issues(item.findtext('synopsis'))
                                solution = fix_spacing_issues(item.findtext('solution'))
                                severity = item.get('severity', 'None')

                                # CVSS scores
                                cvss3_scores = {key: fix_spacing_issues(item.findtext(val)) for key, val in cvss3_keyvalue_dict.items()}
                                cvss2_scores = {key: fix_spacing_issues(item.findtext(val)) for key, val in cvss2_keyvalue_dict.items()}

                                # Compliance data
                                compliance_check_name = fix_spacing_issues(
                                    item.find('cm:compliance-check-name', ns).text if item.find('cm:compliance-check-name', ns) is not None else ""
                                )
                                compliance_info = fix_spacing_issues(
                                    item.find('cm:compliance-info', ns).text if item.find('cm:compliance-info', ns) is not None else ""
                                )
                                compliance_solution = fix_spacing_issues(
                                    item.find('cm:compliance-solution', ns).text if item.find('cm:compliance-solution', ns) is not None else ""
                                )
                                compliance_see_also = fix_spacing_issues(
                                    item.find('cm:compliance-see-also', ns).text if item.find('cm:compliance-see-also', ns) is not None else ""
                                )

                                # Error reporting
                                print_scan_errors(file, report_name, plugin_id, plugin_name, plugin_output,
                                                target_info_dict.get('Target Name', 'N/A'),
                                                target_info_dict.get('FQDN', 'N/A'), ip)
                                print_audit_check_error(file, report_name, plugin_id, plugin_name, plugin_output,
                                                      target_info_dict.get('Target Name', 'N/A'),
                                                      target_info_dict.get('FQDN', 'N/A'), ip)

                                # Write to output
                                if out_format == 'xlsx':
                                    ws.write(row_count, out_column_num_dict['Plugin Name'], compliance_check_name or plugin_name, leftfont)
                                    ws.write(row_count, out_column_num_dict['Product Name'], "N/A", centerfont)
                                    ws.write(row_count, out_column_num_dict['Description'], description, leftfont)
                                    ws.write(row_count, out_column_num_dict['Synopsis'], synopsis or compliance_info, leftfont)
                                    ws.write(row_count, out_column_num_dict['Plugin Output'], plugin_output, leftfont)
                                    ws.write(row_count, out_column_num_dict['Solution'], solution or compliance_solution, leftfont)
                                    ws.write(row_count, out_column_num_dict['Patch Publication Date'], fix_spacing_issues(item.findtext('patch_publication_date')), datefont)
                                    ws.write(row_count, out_column_num_dict['Plugin Publication Date'], fix_spacing_issues(item.findtext('plugin_publication_date')), datefont)
                                    ws.write(row_count, out_column_num_dict['Plugin Modification Date'], fix_spacing_issues(item.findtext('plugin_modification_date')), datefont)
                                    ws.write(row_count, out_column_num_dict['Target Name'], target_info_dict.get('Target Name', 'N/A'), centerfont)
                                    ws.write(row_count, out_column_num_dict['FQDN'], target_info_dict.get('FQDN', 'N/A'), centerfont)
                                    ws.write(row_count, out_column_num_dict['Hostname'], hostname, centerfont)
                                    ws.write(row_count, out_column_num_dict['IP'], ip, centerfont)
                                    ws.write(row_count, out_column_num_dict['Port'], port, centerfont)
                                    ws.write(row_count, out_column_num_dict['Protocol'], protocol, centerfont)
                                    ws.write(row_count, out_column_num_dict['Nessus Plugin ID'], plugin_id, centerfont)
                                    ws.write(row_count, out_column_num_dict['Associated CVEs'], fix_spacing_issues(item.findtext('cve')), centerfont)
                                    ws.write(row_count, out_column_num_dict['Reference Links'], compliance_see_also or fix_spacing_issues(item.findtext('see_also')), leftfont)
                                    ws.write(row_count, out_column_num_dict['Exploit Available'], fix_spacing_issues(item.findtext('exploit_available')), centerfont)
                                    ws.write(row_count, out_column_num_dict['Operating Systems'], target_info_dict.get('OS', 'Unavailable'), centerfont)
                                    ws.write(row_count, out_column_num_dict['Nessus Severity Rating'], severity, centerfont)
                                    for key, val in cvss3_scores.items():
                                        ws.write(row_count, out_column_num_dict[key], val, centerfont)
                                    for key, val in cvss2_scores.items():
                                        ws.write(row_count, out_column_num_dict[key], val, centerfont)
                                    row_count += 1

                                    # Write audit errors
                                    if plugin_id in error_pluginId_list or any(error_desc in plugin_output for error_desc in audit_error_description_list):
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Name'], compliance_check_name or plugin_name, leftfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Product Name'], "N/A", centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Description'], description, leftfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Synopsis'], compliance_info, leftfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Output'], plugin_output, leftfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Solution'], compliance_solution, leftfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Patch Publication Date'], '', centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Publication Date'], fix_spacing_issues(item.findtext('plugin_publication_date')), datefont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Modification Date'], '', centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Target Name'], target_info_dict.get('Target Name', 'N/A'), centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['FQDN'], target_info_dict.get('FQDN', 'N/A'), centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Hostname'], hostname, centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['IP'], ip, centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Port'], port, centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Protocol'], protocol, centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Nessus Plugin ID'], plugin_id, centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Associated CVEs'], "N/A", centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Reference Links'], compliance_see_also, leftfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Exploit Available'], 'N/A', centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Operating Systems'], target_info_dict.get('OS', 'Unavailable'), centerfont)
                                        ws_audit_error.write(row_count_audit_error, out_column_num_dict['Nessus Severity Rating'], 'None', centerfont)
                                        for key, val in cvss3_keyvalue_dict.items():
                                            ws_audit_error.write(row_count_audit_error, out_column_num_dict[key], "", centerfont)
                                        for key, val in cvss2_keyvalue_dict.items():
                                            ws_audit_error.write(row_count_audit_error, out_column_num_dict[key], "", centerfont)
                                        row_count_audit_error += 1
                                else:
                                    csv_writer.writerow([
                                        compliance_check_name or plugin_name,
                                        "N/A",
                                        description,
                                        synopsis or compliance_info,
                                        plugin_output,
                                        solution or compliance_solution,
                                        fix_spacing_issues(item.findtext('patch_publication_date')),
                                        fix_spacing_issues(item.findtext('plugin_publication_date')),
                                        fix_spacing_issues(item.findtext('plugin_modification_date')),
                                        target_info_dict.get('Target Name', 'N/A'),
                                        target_info_dict.get('FQDN', 'N/A'),
                                        hostname,
                                        ip,
                                        port,
                                        protocol,
                                        plugin_id,
                                        fix_spacing_issues(item.findtext('cve')),
                                        compliance_see_also or fix_spacing_issues(item.findtext('see_also')),
                                        fix_spacing_issues(item.findtext('exploit_available')),
                                        target_info_dict.get('OS', 'Unavailable'),
                                        severity
                                    ] + [cvss3_scores.get(key, '') for key in cvss3_keyvalue_dict.keys()] +
                                      [cvss2_scores.get(key, '') for key in cvss2_keyvalue_dict.keys()])

                            # Capture scan timing
                            start_time = host.find('HostProperties/tag[@name="HOST_START"]').text if host.find('HostProperties/tag[@name="HOST_START"]') is not None else ''
                            end_time = host.find('HostProperties/tag[@name="HOST_END"]').text if host.find('HostProperties/tag[@name="HOST_END"]') is not None else ''
                            scan_time_list.append({
                                'fileName': file,
                                'reportName': report_name,
                                'target_name': target_info_dict.get('Target Name', 'N/A'),
                                'fqdn': target_info_dict.get('FQDN', 'N/A'),
                                'ip': ip,
                                'start': start_time,
                                'end': end_time
                            })

                        elem.clear()  # Free memory
                root.clear()  # Free memory
                print(f'Finished parsing file: {file}')
            except ET.ParseError as e:
                print(f'Error parsing XML file {file}: {e}')
                continue

        # Write scan timing and errors to XLSX
        if out_format == 'xlsx':
            ws_time_rownum = 1
            for scan_time_entry in scan_time_list:
                ws_time.write(ws_time_rownum, 0, scan_time_entry['fileName'], centerfont)
                ws_time.write(ws_time_rownum, 1, scan_time_entry['reportName'], centerfont)
                ws_time.write(ws_time_rownum, 2, scan_time_entry['target_name'], centerfont)
                ws_time.write(ws_time_rownum, 3, scan_time_entry['fqdn'], centerfont)
                ws_time.write(ws_time_rownum, 4, scan_time_entry['ip'], centerfont)
                try:
                    ws_time.write(ws_time_rownum, 5, dateparser.parse(scan_time_entry['start']).strftime('%Y-%m-%d %H:%M:%S'), datefont)
                    ws_time.write(ws_time_rownum, 6, dateparser.parse(scan_time_entry['end']).strftime('%Y-%m-%d %H:%M:%S'), datefont)
                except:
                    ws_time.write(ws_time_rownum, 5, "", centerfont)
                    ws_time.write(ws_time_rownum, 6, "", centerfont)
                ws_time_rownum += 1

            ws_scan_errors_rownum = 1
            for scan_error_entry in scan_error_list:
                ws_scan_errors.write(ws_scan_errors_rownum, 0, scan_error_entry['fileName'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 1, scan_error_entry['reportName'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 2, scan_error_entry['pluginId'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 3, scan_error_entry['pluginName'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 4, scan_error_entry['pluginOutput'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 5, scan_error_entry['target_name'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 6, scan_error_entry['fqdn'], centerfont)
                ws_scan_errors.write(ws_scan_errors_rownum, 7, scan_error_entry['ip'], centerfont)
                ws_scan_errors_rownum += 1

            workbook.close()
        else:
            csv_file.close()

        print(f'\nDone. Output saved: {out_file_name}\n')

    except Exception as e:
        print(f'\n==== Exception ====\n\tMain execution: file parsing\n----\n{e}\n')
        traceback.print_exc()
        if out_format == 'xlsx' and 'workbook' in locals():
            workbook.close()
        elif out_format == 'csv' and 'csv_file' in locals():
            csv_file.close()
        sys.exit(1)

if __name__ == "__main__":
    main()