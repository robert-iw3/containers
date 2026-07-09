#!/usr/bin/python3
'''
	Nessus File Parser
	Nessus scan results parser that exports the results into a spreadsheet format.

	Requirements:
		Python 3 with imported modules listed below
		One or more Nessus XML scan output files
			(".nessus" format)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import xml.etree.ElementTree as ET
import xlsxwriter
import argparse
import os
import datetime
import dateparser
import decimal
import traceback
import sys
import ipaddress
import re

#
# -- Global variables --
#
error_pluginId_list = ['10428', '21745', '24786', '26917', '35705', '104410', '110385', '117885']
scan_error_list = []
scan_time_list = []
audit_error_description_list = ["This audit check is not running as"]
audit_error_list = []
cvss3_keyvalue_dict = {'AV:N':"Attack Vector: Network", 'AV:A':"Attack Vector: Adjacent", 'AV:L':"Attack Vector: Local", 'AV:P':"Attack Vector: Physical", 'AC:L':"Attack Complexity: Low", 'AC:H':"Attack Complexity: High", 'PR:N':"Privileges Required: None", 'PR:L':"Privileges Required: Low", 'PR:H':"Privileges Required: High", 'UI:N':"User Interaction: None", 'UI:R':"User Interaction: Required", 'S:U':"Scope: Unchanged", 'S:C':"Scope: Changed", 'C:N':"Confidentiality: None", 'C:L':"Confidentiality: Low", 'C:H':"Confidentiality: High", 'I:N':"Integrity: None", 'I:L':"Integrity: Low", 'I:H':"Integrity: High", 'A:N':"Availability: None", 'A:L':"Availability: Low", 'A:H':"Availability: High", 'E:X':"Exploit Code Maturity: Not Defined", 'E:U':"Exploit Code Maturity: Unproven", 'E:P':"Exploit Code Maturity: Proof-of-Concept", 'E:F':"Exploit Code Maturity: Functional", 'E:H':"Exploit Code Maturity: High", 'RL:X':"Remediation Level: Not Defined", 'RL:O':"Remediation Level: Official Fix", 'RL:T':"Remediation Level: Temporary Fix", 'RL:W':"Remediation Level: Workaround", 'RL:U':"Remediation Level: Unavailable", 'RC:X':"Report Confidence: Not Defined", 'RC:U':"Report Confidence: Unknown", 'RC:R':"Report Confidence: Reasonable", 'RC:C':"Report Confidence: Confirmed"}
cvss2_keyvalue_dict = {'AV:N':"Access Vector: Network", 'AV:A':"Access Vector: Adjacent Network", 'AV:L':"Access Vector: Local", 'AC:L':"Attack Complexity: Low", 'AC:M':"Attack Complexity: Medium", 'AC:H':"Attack Complexity: High", 'Au:M':"Authentication: Multiple", 'Au:S':"Authentication: Single", 'Au:N':"Authentication: None", 'C:N':"Confidentiality Impact: None", 'C:P':"Confidentiality Impact: Partial", 'C:C':"Confidentiality Impact: Complete", 'I:N':"Integrity Impact: None", 'I:P':"Integrity Impact: Partial", 'I:C':"Integrity Impact: Complete", 'A:N':"Availability Impact: None", 'A:P':"Availability Impact: Partial", 'A:C':"Availability Impact: Complete", 'E:U':"Exploitability: Unproven", 'E:POC':"Exploitability: Proof-of-Concept", 'E:F':"Exploitability: Functional", 'E:H':"Exploitability: High", 'E:ND':"Exploitability: Not Defined", 'RL:OF':"Remediation Level: Official Fix", 'RL:TF':"Remediation Level: Temporary Fix", 'RL:W':"Remediation Level: Workaround", 'RL:U':"Remediation Level: Unavailable", 'RL:ND':"Remediation Level: Not Defined", 'RC:UC':"Report Confidence: Unconfirmed", 'RC:UR':"Report Confidence: Uncorroborated", 'RC:C':"Report Confidence: Confirmed", 'RC:ND':"Report Confidence: Not Defined"}
#	out_column_num_dict contains the column number (order) for the output
#		note: output code below assumes that the CVSS Base and Temporal vectors will be in columns directly after their base scores' columns, so if you change the column numbering be sure to keep them together
out_column_num_dict = {'Plugin Name': 0, 'Product Name': 1, 'Description': 2, 'Synopsis': 3, 'Plugin Output': 4, 'Solution': 5, 'Patch Publication Date': 6, 'Plugin Publication Date': 7, 'Plugin Modification Date': 8, 'Target Name': 9, 'FQDN': 10, 'Hostname': 11, 'IP': 12, 'Port': 13, 'Protocol': 14, 'Nessus Plugin ID': 15, 'Associated CVEs': 16, 'Reference Links': 17, 'Exploit Available': 18, 'Operating Systems': 19, 'Nessus Severity Rating': 20, 'CVSS 3-or-2 Base Score': 21, 'CVSS 3 Base Score': 22, 'CVSS 3 Attack Vector': 23, 'CVSS 3 Attack Complexity': 24, 'CVSS 3 Privileges Required': 25, 'CVSS 3 User Interaction': 26, 'CVSS 3 Scope': 27, 'CVSS 3 Confidentiality': 28, 'CVSS 3 Integrity': 29, 'CVSS 3 Availability': 30, 'CVSS 3 Temporal Score': 31, 'CVSS 3 Exploit Code Maturity': 32, 'CVSS 3 Remediation Level': 33, 'CVSS 3 Report Confidence': 34, 'CVSS 2 Base Score': 35, 'CVSS 2 Attack Vector': 36, 'CVSS 2 Attack Complexity': 37, 'CVSS 2 Privileges Required': 38, 'CVSS 2 Confidentiality': 39, 'CVSS 2 Integrity': 40, 'CVSS 2 Availability': 41, 'CVSS 2 Temporal Score': 42, 'CVSS 2 Exploit Code Maturity': 43, 'CVSS 2 Remediation Level': 44, 'CVSS 2 Report Confidence': 45}
#	out_column_width_dict contains the column width for the output
#		note: ensure out_column_num_dict and out_column_width_dict have the same keys
out_column_width_dict = {'Plugin Name':20, 'Product Name':30, 'Description':50, 'Synopsis':25, 'Plugin Output':40, 'Solution':30, 'Patch Publication Date':20, 'Plugin Publication Date':20, 'Plugin Modification Date':20, 'Target Name': 42, 'FQDN': 25, 'Hostname':25, 'IP':15, 'Port':6, 'Protocol':8, 'Nessus Plugin ID':13, 'Associated CVEs':15, 'Reference Links':50, 'Exploit Available':13, 'Operating Systems':30, 'Nessus Severity Rating':13, 'CVSS 3-or-2 Base Score': 20, 'CVSS 3 Base Score':15, 'CVSS 3 Attack Vector':15, 'CVSS 3 Attack Complexity':15, 'CVSS 3 Privileges Required':15, 'CVSS 3 User Interaction':15, 'CVSS 3 Scope':15, 'CVSS 3 Confidentiality':15, 'CVSS 3 Integrity':15, 'CVSS 3 Availability':15, 'CVSS 3 Temporal Score':15, 'CVSS 3 Exploit Code Maturity':15, 'CVSS 3 Remediation Level':15, 'CVSS 3 Report Confidence':15, 'CVSS 2 Base Score':15, 'CVSS 2 Attack Vector':15, 'CVSS 2 Attack Complexity':15, 'CVSS 2 Privileges Required':15, 'CVSS 2 Confidentiality':15, 'CVSS 2 Integrity':15, 'CVSS 2 Availability':15, 'CVSS 2 Temporal Score':15, 'CVSS 2 Exploit Code Maturity':15, 'CVSS 2 Remediation Level':15, 'CVSS 2 Report Confidence':15}
severity_risk_dict = {'4':"Critical", '3':"High", '2':"Medium", '1':"Low", '0':"None"}
#
#
# -- Start of function declarations --
#
#
# findNessusOutput(): function to find all Nessus output files
#
def findNessusOutput(directory):
	try:
		files = []
		for file in os.listdir(directory):
			if (file.endswith(".nessus") and not file.startswith("~$")):
				print('Found ' + file)
				files.append(file)
			else:
				continue
		return files
	except Exception as e:
		print('\n==== Exception ====\n\tfindNessusOutput()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
		return []
#
#
# fixSpacingIssues(): function to fix spacing issues within a string
#	this might seem like overkill, but some plugins include unnecessary whitespace chars inside individual strings
#	also this code gives up a little efficiency for easier readability and editability
#
def fixSpacingIssues(instring):
	try:
		if (instring == None or instring == ''):
			return ''
		instring = instring.strip()
		while '  ' in instring:
			instring = instring.replace('  ', ' ')
		while '\n ' in instring:
			instring = instring.replace('\n ', '\n')
		while ' \n' in instring:
			instring = instring.replace(' \n', '\n')
		while ' \t' in instring:
			instring = instring.replace(' \t', '\t')
		while '\t ' in instring:
			instring = instring.replace('\t ', '\t')
		while '\n\n' in instring:
			instring = instring.replace('\n\n', '\n')
		while '\t\t' in instring:
			instring = instring.replace('\t\t', '\t')
		while '\t\n' in instring:
			instring = instring.replace('\t\n', '\n')
		while '\n;' in instring:
			instring = instring.replace('\n;', ';')
		instring = instring.replace(' :', ':')
		instring = instring.replace(' ;', ';')
		instring = instring.replace(' ,', ',')
		instring = instring.replace('( ', '(')
		instring = instring.replace(' )', ')')
	except Exception as e:
		print('\n==== Exception ====\n\tfixSpacingIssues()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
	return instring
#
#
# patchAbbreviationFix(): function to replace abbreviated versions of the word "patch" written by some plugins
#
def patchAbbreviationFix(instring):
	try:
		instring = instring.strip()
		instring = instring.replace(' patc.', ' patch')
		instring = instring.replace(' pat.', ' patch')
		instring = instring.replace(' pa.', ' patch')
		instring = instring.replace(' p.', ' patch')
	except Exception as e:
		print('\n==== Exception ====\n\tpatchAbbreviationFix()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
	return instring
#
#
# printScanErrors(): function to print scan problems to standard out and add to error list
#	for scan validation and troubleshooting purposes
#
def printScanErrors(fileName, reportName, pluginId, pluginName, pluginOutput, target_name, fqdn, ip):
	try:
		if pluginId in error_pluginId_list:
			print("\t\tScan Error - Plugin ID = "+pluginId+"; Plugin Name = \""+pluginName+"\" for:\n\t\t"+target_name+" / "+fqdn+" ("+ip+")")
			scan_error_list.append({'fileName':fileName, 'reportName':reportName, 'pluginId':pluginId, 'pluginName':pluginName, 'pluginOutput':pluginOutput, 'target_name':target_name, 'fqdn':fqdn, 'ip':ip})
	except Exception as e:
		print('\n==== Exception ====\n\tprintScanErrors()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
	return
#
#
# printAuditCheckError(): function to print audit compliance check errors to standard out and add to error list
#	for scan validation and troubleshooting purposes
#	using separate function and error list to make it simple and easy to modify
#
def printAuditCheckError(fileName, reportName, pluginId, pluginName, pluginOutput, target_name, fqdn, ip):
	try:
		if any(s in description for s in audit_error_description_list):
			print("\t\tCompliance Check Error - Plugin ID = "+pluginId+"; Plugin Name = \""+pluginName+"\" for:\n\t\t"+hostname+" ("+ip+")")
			audit_error_list.append({'fileName':fileName, 'reportName':reportName, 'pluginId':pluginId, 'pluginName':pluginName, 'pluginOutput':pluginOutput, 'target_name':target_name, 'fqdn':fqdn, 'ip':ip})
	except Exception as e:
		print('\n==== Exception ====\n\tprintAuditCheckError()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
	return
#
#
# appendScanTime(): function to append individual host's scan time to the list
#
def appendScanTime(fileName, reportName, target_name, fqdn, ip, startTimeStr, endTimeStr):
	try:
		startTime = dateparser.parse(startTimeStr) # should provide an object: datetime.datetime(YYYY, MM, DD, HH, MM, SS)
		endTime = dateparser.parse(endTimeStr) # should provide an object: datetime.datetime(YYYY, MM, DD, HH, MM, SS)
		scan_time_list.append({'fileName':file, 'reportName':reportName, 'target_name':target_name, 'fqdn':fqdn, 'ip':ip, 'start':startTime,'end':endTime})
	except Exception as e:
		print('\n==== Exception ====\n\tappendScanTime()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
	return
#
#
# parseCVSSVector(): function to parse a CVSS vector
#	Nessus uses different notation for CVSS 2 and 3 vector strings (excluding quotes):
#		CVSS 2 vector starts with: "CVSS2#" (followed by the usual '/' separator)
#		CVSS 3 vector starts with: "CVSS:3.0" (followed by the usual '/' separator)
# input is a CVSS 2 or 3 string from nessus that uses the abbreviations
# return value is a list containing the key-value pairs spelled out (see cvss#_keyvalue_dict global variables)
#
def parseCVSSVector(vector):
	try:
		vectorReturnList = []
		version = 2 #default to cvss 2
		if vector != None:
			vector = re.sub('#', '/', vector)
			vectorList = vector.split('/')
			if vectorList[0] == "CVSS:3.0":
				version = 3
			del vectorList[0] # we don't need the version identifier any more
			for bvitem in vectorList:
				if version == 3:
					vectorReturnList.append(cvss3_keyvalue_dict[bvitem])
				elif version == 2:
					vectorReturnList.append(cvss2_keyvalue_dict[bvitem])
		return vectorReturnList
	except Exception as e:
		print('\n==== Exception ====\n\tparseCVSSVector()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
		return []
#
#
# prepWorksheet(): function to prepare a results worksheet
#
def prepWorksheet(wsthis, wsfont):
	try:
		# set column width and column titles (first row values)
		for colnum_key,colnum_val in out_column_num_dict.items():
			wsthis.set_column(colnum_val, colnum_val, out_column_width_dict[colnum_key])
			wsthis.write(0, colnum_val, colnum_key, wsfont)
		wsthis.freeze_panes(1, 0)
		return wsthis
	except Exception as e:
		print('\n==== Exception ====\n\tprepWorksheet()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
		return wsthis
#
#
#
def coolLogo():
	try:
		retval = ''
		retval = retval + '\n _   _                           ____                          '
		retval = retval + '\n| \ | | ___  ___ ___ _   _ ___  |  _ \ __ _ _ __ ___  ___ _ __ '
		retval = retval + '\n|  \| |/ _ \/ __/ __| | | / __| | |_) / _` | ^__/ __|/ _ \ ^__|'
		retval = retval + '\n| |\  |  __/\__ \__ \ |_| \__ \ |  __/ (_| | |  \__ \  __/ |   '
		retval = retval + '\n|_| \_|\___||___/___/\__,_|___/ |_|   \__,_|_|  |___/\___|_|   '
		retval = retval + '\n\nNessus File Parser\n'
		return retval
	except Exception as e:
		print('\n==== Exception ====\n\tcoolLogo()\n----')
		print(e)
		traceback.print_exc()
		print('\n===================')
		print('(this is really embarrassing)')
		return 'oopsies'
#
#
# -- End of function declarations --
#
#
parser = argparse.ArgumentParser()
parser.add_argument("-d", help="Location of the directory in which the Nessus output files are stored.")
parser.add_argument("-f", help="Name of the nessus file you want to parse. Ignored if '-d' option is used.")
parser.add_argument("-i", help="('-i F') Do not include Informational severity items in output (default/omitted == True).")
parser.add_argument("-o", help="Base name of spreadsheet file to which you want the parsed results to be written.")
parser.add_argument("-e", help="Not a usable flag. Just for clarification. Usage Example: python nessus-parser.py -d .")
args = parser.parse_args()
#
# -- main execution --
#
print('\n\n' + coolLogo() + '\n\nRunning Parser...\n')
print('<< Finding Nessus output files >>')
fileList = []
try:
	if args.d:
		fileList = findNessusOutput(args.d)
	elif args.f:
		fileList.append(args.f)
	else:
		print('No directory or file argument provided. Trying current directory.')
		fileList = findNessusOutput('.')
except:
	print('\nERROR: Something went wrong when trying to get .nessus file(s). This is not my fault. You failed miserably and should feel bad.')
	sys.exit()
print('<< Finished finding Nessus output files >>')
if fileList == []:
	print("\nNote: input file list is empty; that's bad. But also we're done. That's good. Better luck next time. The sprinkles are also cursed.")
	sys.exit()
include_info_items = True
if args.i:
	infos = args.i.casefold()
	if (infos == 'false' or infos.startswith('f') or args.i == '0'):
		include_info_items = False
#
# -- Start of output file prep --
#
try:
	timestamp_filename = datetime.datetime.now().strftime('%Y%m%d_%H%M')
	outFileNameBase = ''
	if args.o:
		outFileNameBase = str(args.o)
		outFileNameBase = outFileNameBase.replace('.xlsx', '')
	elif len(fileList) == 1:
		outFileNameBase = fileList[0].replace('.nessus', '')
	else:
		outFileNameBase = 'Unnamed_File_Group'
	outFileNameBase = outFileNameBase + '__parsed'
	outFileNameBase = outFileNameBase + '__(' + timestamp_filename + ')'
	outFileName = outFileNameBase + '.xlsx'
	print('<< Generating Excel Workbook and Worksheets >>')
	workbook = xlsxwriter.Workbook(outFileName, {'strings_to_urls': False})
	workbook.set_size(2400, 1350)
	# Declaring cell formatting styles
	leftfont = workbook.add_format()
	leftfont.set_align('top')
	leftfont.set_text_wrap()
	leftfont.set_border()
	centerfont = workbook.add_format()
	centerfont.set_align('center')
	centerfont.set_align('top')
	centerfont.set_text_wrap()
	centerfont.set_border()
	headerfont = workbook.add_format({'bold': True})
	headerfont.set_bg_color('#336699')
	headerfont.set_font_color('#FFFFFF')
	headerfont.set_align('center')
	headerfont.set_align('top')
	headerfont.set_text_wrap()
	headerfont.set_border()
	redfont = workbook.add_format()
	redfont.set_align('center')
	redfont.set_align('top')
	redfont.set_text_wrap()
	redfont.set_font_color('#FF0000')
	redfont.set_border()
	datefont = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
	datefont.set_align('center')
	datefont.set_align('top')
	datefont.set_text_wrap()
	datefont.set_border()
	# Add vuln and audit data worksheet to the workbook
	ws_vuln = workbook.add_worksheet('Scan Data (vuln)')
	ws_vuln = prepWorksheet(ws_vuln, headerfont)
	ws_audit_fail = workbook.add_worksheet('Scan Data (audit fails)')
	ws_audit_fail = prepWorksheet(ws_audit_fail, headerfont)
	ws_audit_error = workbook.add_worksheet('Scan Data (audit errors)')
	ws_audit_error = prepWorksheet(ws_audit_error, headerfont)
	# Add the Summary Error worksheet
	ws_scan_errors = workbook.add_worksheet('Errors')
	ws_scan_errors.set_column(0, 0, 50) #file name
	ws_scan_errors.set_column(1, 1, 50) #report name
	ws_scan_errors.set_column(2, 2, 10) #plugin ID
	ws_scan_errors.set_column(3, 3, 50) #plugin name
	ws_scan_errors.set_column(4, 4, 50) #plugin output
	ws_scan_errors.set_column(5, 5, 42) #target name
	ws_scan_errors.set_column(6, 6, 30) #fqdn
	ws_scan_errors.set_column(7, 7, 22) #ip address
	#	Add header row to Summary Error worksheet
	ws_scan_errors.write(0, 0, 'File Name', headerfont)
	ws_scan_errors.write(0, 1, 'Report Name', headerfont)
	ws_scan_errors.write(0, 2, 'Plugin ID', headerfont)
	ws_scan_errors.write(0, 3, 'Plugin Name', headerfont)
	ws_scan_errors.write(0, 4, 'Plugin Output', headerfont)
	ws_scan_errors.write(0, 5, 'Target Name', headerfont)
	ws_scan_errors.write(0, 6, 'FQDN', headerfont)
	ws_scan_errors.write(0, 7, 'IP Address', headerfont)
	# Add the Summary Time worksheet
	ws_time = workbook.add_worksheet('Time')
	ws_time.set_column(0, 0, 50) #file name
	ws_time.set_column(1, 1, 50) #report name
	ws_time.set_column(2, 2, 42) #target name
	ws_time.set_column(3, 3, 30) #fqdn
	ws_time.set_column(4, 4, 22) #ip address
	ws_time.set_column(5, 5, 20) #start time
	ws_time.set_column(6, 6, 20) #end time
	#	Add header row to Summary Time worksheet
	ws_time.write(0, 0, 'File Name', headerfont)
	ws_time.write(0, 1, 'Report Name', headerfont)
	ws_time.write(0, 2, 'Target Name', headerfont)
	ws_time.write(0, 3, 'FQDN', headerfont)
	ws_time.write(0, 4, 'IP Address', headerfont)
	ws_time.write(0, 5, 'Start Time', headerfont)
	ws_time.write(0, 6, 'End Time', headerfont)
	#	Freeze panes
	ws_scan_errors.freeze_panes(1, 0)
	ws_time.freeze_panes(1, 0)
	print('<< Finished generating Excel Workbook and Worksheets >>\n')
	#
	# -- End of output file prep
	#
except Exception as e:
	print('\n==== Exception ====\n\tmain execution: output file prep\n----')
	print(e)
	traceback.print_exc()
	print('\n===================')
	print('Exiting.')
	sys.exit()

try:
	#
	# Nessus XML Namespace
	#	This is required to parse the audit compliance results that use an XML namespace
	ns = {'cm': 'http://www.nessus.org/cm'}
	#
	# Row counters for each worksheet
	row_count_vuln=1
	row_count_audit_fail=1
	row_count_audit_error=1
	#
	# -- Start of file parsing --
	#
	for file in fileList:
		print('<< Parsing files and writing main output >>')
		print('Parsing file: ' + file + '\n...')
		#
		# Get XML tree/root
		tree = ET.parse(file)
		root = tree.getroot()
		#
		# Report subelement contains results of scan
		for report in root.iter('Report'):
			reportName = report.get('name')
			#
			#	Iterating through each host
			for host in report.iter('ReportHost'):
				targetInfoDict = {}
				hostname = host.get('name')
				print('\tParsing:', hostname)
				targetStart = ''
				targetEnd = ''
				for item in host.iter('HostProperties'):
					for data in item:
						if data.get('name') == 'operating-system':
							targetInfoDict['OS'] = data.text
						elif data.get('name') == 'host-ip':
							targetInfoDict['IP Address'] = data.text
							ip = data.text
						elif data.get('name') == 'hostname':
							targetInfoDict['Hostname'] = data.text
							hostname = data.text
						elif data.get('name') == 'host-fqdn':
							targetInfoDict['FQDN'] = data.text
							fqdn = data.text
						elif data.get('name') == 'netbios-name':
							if (not 'Hostname' in targetInfoDict.keys() or targetInfoDict['Hostname'] == "" or targetInfoDict['Hostname'] == 'Unavailable'):
								targetInfoDict['Hostname'] = data.text
								hostname = data.text
						elif data.get('name') == 'system-type':
							targetInfoDict['System Type'] = data.text
						elif data.get('name') == 'operating-system':
							targetInfoDict['Operating System'] = data.text
						elif data.get('name') == 'HOST_START':
							targetStart = data.text
						elif data.get('name') == 'HOST_END':
							targetEnd = data.text
						elif data.get('name') == 'Credentialed_Scan':
							targetInfoDict['Credentialed_Scan'] = data.text
						else:
							pass
				try:
					#
					#	Test if the IP address is in the host 'name' field
					test = ipaddress.ip_address(hostname)
					#
					#	If the test passed, then the target IP address is in hostname
					if (not 'IP Address' in targetInfoDict.keys() or targetInfoDict['IP Address'] == ""):
						targetInfoDict['IP Address'] = hostname
					if (not 'Hostname' in targetInfoDict.keys() or targetInfoDict['Hostname'] == ""):
						targetInfoDict['Hostname'] = "Unavailable"
					if (not 'FQDN' in targetInfoDict.keys() or targetInfoDict['FQDN'] == ""):
						targetInfoDict['FQDN'] = "Unavailable"
				except:
					if (not 'Hostname' in targetInfoDict.keys() or targetInfoDict['Hostname'] == ""):
						targetInfoDict['Hostname'] = hostname
					if (not 'FQDN' in targetInfoDict.keys() or targetInfoDict['FQDN'] == ""):
						targetInfoDict['FQDN'] = targetInfoDict['Hostname']
					if (not 'IP Address' in targetInfoDict.keys() or targetInfoDict['IP Address'] == ""):
						targetInfoDict['IP Address'] = 'x.x.x.x'
				#
				#	Preferred target name format is "FQDN (IP Address)"; backup is "Hostname (IP Address)" or just "IP Address" if we have no FQDN/hostname
				targetInfoDict['Target Name'] = targetInfoDict['FQDN'] + " (" + targetInfoDict['IP Address'] + ")"
				if (targetInfoDict['FQDN'] == targetInfoDict['IP Address']):
					targetInfoDict['Target Name'] = targetInfoDict['IP Address']
				appendScanTime(file, reportName, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'], targetStart, targetEnd)
				#
				#	print targetInfoDict for testing
				#print("\ntargetInfoDict:\n", targetInfoDict, "\n")
				#
				#	Iterating through each report item (vuln) that is not part of a compliance check
				for item in host.iter('ReportItem'):
					severity = item.get('severity')
					pluginName = item.get('pluginName')
					#
					#	print pluginName for testing
					#print("pluginName:", pluginName)
					#
					pluginId = item.get('pluginID')
					port = item.get('port')
					protocol = item.get('protocol')
					description = 'None'
					pluginOutput = 'None'
					try:
						description = fixSpacingIssues(item.findtext('./description'))
						description = patchAbbreviationFix(description)
					except:
						print('findtext description threw exception')
						pass
					try:
						pluginOutput = fixSpacingIssues(item.findtext('./plugin_output'))
					except:
						print('findtext plugin_output threw exception')
						pass
					#
					#	printScanErrors and printAuditCheckError contains the error checks
					#		just need to supply the fields
					printScanErrors(file, reportName, pluginId, pluginName, pluginOutput, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'])
					printAuditCheckError(file, reportName, pluginId, pluginName, pluginOutput, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'])
					#
					#	Skip if item is informational/none (severity == 0) and these items should not be included (command line option)
					if (severity == '0' and include_info_items == False):
						continue
					#
					#	First set - deal with plugins that are not compliance checks
					if not 'Compliance' in pluginName:
						#
						#	Back to parsing fields
						solution = ''
						patch_pub_date = ''
						plugin_pub_date = ''
						plugin_mod_date = ''
						exploit_available = ''
						try:
							solution = fixSpacingIssues(item.findtext('solution'))
						except:
							pass
						patch_pub_date = item.findtext('patch_publication_date')
						plugin_pub_date = item.findtext('plugin_publication_date')
						plugin_mod_date = item.findtext('plugin_modification_date')
						exploit_available = item.findtext('exploit_available')
						if (exploit_available == None):
							exploit_available = 'N/A'
						cvss3BaseScore = item.findtext('cvss3_base_score')
						cvss3BaseVector = item.findtext('cvss3_vector')
						if cvss3BaseVector != None:
							cvss3BaseVector = parseCVSSVector(cvss3BaseVector)
						cvss3TemporalScore = item.findtext('cvss3_temporal_score')
						cvss3TemporalVector = item.findtext('cvss3_temporal_vector')
						if cvss3TemporalVector != None:
							cvss3TemporalVector = parseCVSSVector(cvss3TemporalVector)
						cvss2BaseScore = item.findtext('cvss_base_score')
						cvss2BaseVector = item.findtext('cvss_vector')
						if cvss2BaseVector != None:
							cvss2BaseVector = parseCVSSVector(cvss2BaseVector)
						cvss2TemporalScore = item.findtext('cvss_temporal_score')
						cvss2TemporalVector = item.findtext('cvss_temporal_vector')
						if cvss2TemporalVector != None:
							cvss2TemporalVector = parseCVSSVector(cvss2TemporalVector)
						#
						#	Plugins will include only v3, only v2, both v3 and v2, or neither CVSS base scores
						#	cvss3or2BaseScore opts for v3 when it exists and v2 if not; otherwise leave blank
						cvss3or2BaseScore = ''
						if (cvss3BaseScore != None and cvss3BaseScore != ''):
							cvss3or2BaseScore = cvss3BaseScore
						elif (cvss2BaseScore != None and cvss2BaseScore != ''):
							cvss3or2BaseScore = cvss2BaseScore
						cve_list = []
						all_cves = item.findall('cve')
						for cve in all_cves:
							cve_list.append(cve.text)
						cpe_list = []
						all_cpes = item.findall('cpe')
						for all_cpe in all_cpes:
							cpe_list_lines = all_cpe.text.splitlines()
							#
							#	Nessus puts all CPEs inside a single <cpe> tag with individual CPEs separated by a newline
							#	Each line will include -- cpe:/ {part} : {vendor} : {product} : {version} : {update} : {edition} : {language}
							#		Note: the following is optional -- ": {version} : {update} : {edition} : {language}"
							#	Sometimes the vendor is the same as the product so try to prevent repeat text in output (e.g. "splunk splunk")
							#
							for cpe_line in cpe_list_lines:
								cpe_words = cpe_line.split(':')
								vendor = cpe_words[2]
								product = cpe_words[3]
								version = ''
								if len(cpe_words) > 4:
									version = cpe_words[4]
								if vendor == product:
									cpe_list.append(vendor)
								else:
									if len(cpe_words) > 4 and product != version:
										cpe_list.append(vendor+" "+product+" "+version)
									else:
										cpe_list.append(vendor+" "+product)
						os = targetInfoDict.get('OS', 'Unavailable')
						#
						#	We have the data that we need; write it out
						ws_vuln.write(row_count_vuln, out_column_num_dict['Plugin Name'], pluginName, leftfont)
						try:
							ws_vuln.write(row_count_vuln, out_column_num_dict['Product Name'], "\n".join(cpe_list), centerfont)
						except:
							ws_vuln.write(row_count_vuln, out_column_num_dict['Product Name'], "", centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Description'], description, leftfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Synopsis'], fixSpacingIssues(item.findtext('synopsis')), leftfont) # Weakness Description
						ws_vuln.write(row_count_vuln, out_column_num_dict['Plugin Output'], pluginOutput, leftfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Solution'], solution, leftfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Patch Publication Date'], patch_pub_date, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Plugin Publication Date'], plugin_pub_date, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Plugin Modification Date'], plugin_mod_date, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Target Name'], targetInfoDict['Target Name'], centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['FQDN'], targetInfoDict['FQDN'], centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Hostname'], targetInfoDict['Hostname'], centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['IP'], targetInfoDict['IP Address'], centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Port'], port, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Protocol'], protocol, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Nessus Plugin ID'], pluginId, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Associated CVEs'], "\n".join(cve_list), centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Reference Links'], item.findtext('see_also'), centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Exploit Available'], exploit_available, centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Operating Systems'], os, centerfont)
						#ws_vuln.write(row_count_vuln, out_column_num_dict['Nessus Severity Rating'], item.findtext('risk_factor'), centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['Nessus Severity Rating'], severity_risk_dict[severity], centerfont)
						#
						#	Add CVSS 3 and CVSS 2 details if the info for either was included in the results
						#	We want to format the cells even if there is no CVSS data, so use blank if missing
						#
						if cvss3BaseScore != None:
							ws_vuln.write(row_count_vuln, out_column_num_dict['CVSS 3 Base Score'], cvss3BaseScore, centerfont)
							if cvss3BaseVector != None:
								col_count = 1
								for item in cvss3BaseVector:
									ws_vuln.write(row_count_vuln, col_count+out_column_num_dict['CVSS 3 Base Score'], item.split(':')[1].strip(), centerfont)
									col_count += 1
							if cvss3TemporalScore != None:
								ws_vuln.write(row_count_vuln, out_column_num_dict['CVSS 3 Temporal Score'], cvss3TemporalScore, centerfont)
								if cvss3TemporalVector != None:
									col_count = 1
									for item in cvss3TemporalVector:
										ws_vuln.write(row_count_vuln, col_count+out_column_num_dict['CVSS 3 Temporal Score'], item.split(':')[1].strip(), centerfont)
										col_count += 1
						else:
							for key in out_column_num_dict.keys():
								if key.startswith('CVSS 3 '):
									ws_vuln.write(row_count_vuln, out_column_num_dict[key], '', centerfont)
						if cvss2BaseScore != None:
							ws_vuln.write(row_count_vuln, out_column_num_dict['CVSS 2 Base Score'], cvss2BaseScore, centerfont)
							if cvss2BaseVector != None:
								col_count = 1
								for item in cvss2BaseVector:
									ws_vuln.write(row_count_vuln, col_count+out_column_num_dict['CVSS 2 Base Score'], item.split(':')[1].strip(), centerfont)
									col_count += 1
							if cvss2TemporalScore != None:
								ws_vuln.write(row_count_vuln, out_column_num_dict['CVSS 2 Temporal Score'], cvss2TemporalScore, centerfont)
								if cvss2TemporalVector != None:
									col_count = 1
									for item in cvss2TemporalVector:
										ws_vuln.write(row_count_vuln, col_count+out_column_num_dict['CVSS 2 Temporal Score'], item.split(':')[1].strip(), centerfont)
										col_count += 1
						else:
							for key in out_column_num_dict.keys():
								if key.startswith('CVSS 2 '):
									ws_vuln.write(row_count_vuln, out_column_num_dict[key], '', centerfont)
						ws_vuln.write(row_count_vuln, out_column_num_dict['CVSS 3-or-2 Base Score'], cvss3or2BaseScore, centerfont)
						row_count_vuln+=1
					#
					#	Second set - deal with compliance checks
					elif  'Compliance' in pluginName and '[FAILED]' in description:
						# use cm:compliance-actual-value instead of pluginOutput
						pluginOutput = 'None'
						complianceCheckName = 'None'
						complianceInfo = 'None'
						complianceSolution = 'None'
						complianceSeeAlso = 'None'
						#	Not all audit compliance checks have each field, so using independent try's
						try:
							pluginOutput = fixSpacingIssues(item.find('cm:compliance-actual-value', ns).text)
						except:
							pass
						try:
							complianceCheckName = fixSpacingIssues(item.find('cm:compliance-check-name', ns).text)
						except:
							pass
						try:
							complianceInfo = fixSpacingIssues(item.find('cm:compliance-info', ns).text)
						except:
							pass
						try:
							complianceSolution = fixSpacingIssues(item.find('cm:compliance-solution', ns).text)
						except:
							pass
						try:
							complianceSeeAlso = fixSpacingIssues(item.find('cm:compliance-see-also', ns).text)
						except:
							pass
						printScanErrors(file, reportName, pluginId, pluginName, pluginOutput, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'])
						printAuditCheckError(file, reportName, pluginId, pluginName, pluginOutput, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'])
						cvss2BaseScore = 'N/A'
						cve_list = []
						cve_list.append('N/A')
						cpe_list = []
						cpe_list.append('N/A')
						os = targetInfoDict.get('OS', 'Unavailable')
						#
						#	We have the data that we need; write it out
						#	use cm:compliance-check-name instead of pluginName
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Plugin Name'], complianceCheckName, leftfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Product Name'], "\n".join(cpe_list), centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Description'], description, leftfont)
						#	use cm:compliance-info instead of synopsis
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Synopsis'], complianceInfo, leftfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Plugin Output'], pluginOutput, leftfont)
						#	use cm:compliance-solution instead of solution
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Solution'], complianceSolution, leftfont)
						#	there is no patch_publication_date, only plugin_publication_date
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Patch Publication Date'], '', centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Plugin Publication Date'], item.findtext('plugin_publication_date'), centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Plugin Modification Date'], item.findtext('plugin_modification_date'), centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Target Name'], targetInfoDict['Target Name'], centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['FQDN'], targetInfoDict['FQDN'], centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Hostname'], hostname, centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['IP'], ip, centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Port'], port, centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Protocol'], protocol, centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Nessus Plugin ID'], pluginId, centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Associated CVEs'], "\n".join(cve_list), centerfont)
						#	use cm:compliance-see-also instead of see_also
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Reference Links'], complianceSeeAlso, centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Exploit Available'], 'N/A', centerfont)
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Operating Systems'], os, centerfont)
						#	Nessus assigns a default of severity=3 (High) and risk_factor="None" for failed compliance checks
						ws_audit_fail.write(row_count_audit_fail, out_column_num_dict['Nessus Severity Rating'], 'High', centerfont)
						#	There is no CVSS info for audit compliance checks
						for key,val in out_column_num_dict.items():
							if 'CVSS' in key:
								ws_audit_fail.write(row_count_audit_fail, val, "", centerfont)
						row_count_audit_fail+=1
					#
					#	Third set - add [ERROR] compliance checks to a second tab in the audit worksheet
					elif 'Compliance' in pluginName and '[ERROR]' in description:
						#	use cm:compliance-actual-value instead of pluginOutput
						pluginOutput = 'None'
						complianceCheckName = 'None'
						complianceInfo = 'None'
						complianceSolution = 'None'
						complianceSeeAlso = 'None'
						#	Not all audit compliance checks have each field, so using independent try's
						try:
							pluginOutput = fixSpacingIssues(item.find('cm:compliance-actual-value', ns).text)
						except:
							pass
						try:
							complianceCheckName = fixSpacingIssues(item.find('cm:compliance-check-name', ns).text)
						except:
							pass
						try:
							complianceInfo = fixSpacingIssues(item.find('cm:compliance-info', ns).text)
						except:
							pass
						try:
							complianceSolution = fixSpacingIssues(item.find('cm:compliance-solution', ns).text)
						except:
							pass
						try:
							complianceSeeAlso = fixSpacingIssues(item.find('cm:compliance-see-also', ns).text)
						except:
							pass
						printScanErrors(file, reportName, pluginId, pluginName, pluginOutput, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'])
						printAuditCheckError(file, reportName, pluginId, pluginName, pluginOutput, targetInfoDict['Target Name'], targetInfoDict['FQDN'], targetInfoDict['IP Address'])
						cvss2BaseScore = 'N/A'
						cve_list = []
						cve_list.append('N/A')
						cpe_list = []
						cpe_list.append('N/A')
						os = targetInfoDict.get('OS', 'Unavailable')
						#
						#	We have the data that we need; write it out
						#	use cm:compliance-check-name instead of pluginName
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Name'], complianceCheckName, leftfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Product Name'], "\n".join(cpe_list), centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Description'], description, leftfont)
						#	use cm:compliance-info instead of synopsis
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Synopsis'], complianceInfo, leftfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Output'], pluginOutput, leftfont)
						#	use cm:compliance-solution instead of solution
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Solution'], complianceSolution, leftfont)
						#	there is no patch_publication_date, only plugin_publication_date
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Patch Publication Date'], '', centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Publication Date'], item.findtext('plugin_publication_date'), centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Plugin Modification Date'], item.findtext('plugin_modification_date'), centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Target Name'], targetInfoDict['Target Name'], centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['FQDN'], targetInfoDict['FQDN'], centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Hostname'], hostname, centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['IP'], ip, centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Port'], port, centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Protocol'], protocol, centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Nessus Plugin ID'], pluginId, centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Associated CVEs'], "\n".join(cve_list), centerfont)
						#	use cm:compliance-see-also instead of see_also
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Reference Links'], complianceSeeAlso, centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Exploit Available'], 'N/A', centerfont)
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Operating Systems'], os, centerfont)
						#	Nessus assigns a default of severity=3 (High) and risk_factor="None" for failed compliance checks
						ws_audit_error.write(row_count_audit_error, out_column_num_dict['Nessus Severity Rating'], 'None', centerfont)
						#	There is no CVSS info for audit compliance checks
						for key,val in out_column_num_dict.items():
							if 'CVSS' in key:
								ws_audit_error.write(row_count_audit_error, val, "", centerfont)
						row_count_audit_error+=1
				#--End ReportItem iter --
				print('\t\tFinished parsing:', ip)
			#--End ReportHost iter
		print('...\nFinished parsing file: ' + file)
		#--End Report iter
	print('<< Finished parsing files and writing main output >>')
	#
	# Add scan_time_list items to Summary Time worksheet
	print('<< Adding scan time and errors to output >>')
	ws_time_rownum = 1
	for scan_time_entry in scan_time_list:
		ws_time.write(ws_time_rownum, 0, scan_time_entry['fileName'], centerfont)
		ws_time.write(ws_time_rownum, 1, scan_time_entry['reportName'], centerfont)
		ws_time.write(ws_time_rownum, 2, scan_time_entry['target_name'], centerfont)
		ws_time.write(ws_time_rownum, 3, scan_time_entry['fqdn'], centerfont)
		ws_time.write(ws_time_rownum, 4, scan_time_entry['ip'], centerfont)
		ws_time.write(ws_time_rownum, 5, scan_time_entry['start'], datefont)
		ws_time.write(ws_time_rownum, 6, scan_time_entry['end'], datefont)
		ws_time_rownum += 1
	# Add scan_error_list to Summary Error worksheet
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
	print('<< Finished adding scan time and errors to output >>')
	workbook.close()
	print('\n--\nDone. Output workbook saved:\n' + outFileName + '\n')
	#
	# -- End of file parsing --
	#
except Exception as e:
	print('\n==== Exception ====\n\tmain execution: file parsing\n----')
	print(e)
	traceback.print_exc()
	print('\n===================')
	print('Exiting.')
	sys.exit()