import os
import sys
import json
from ar_action_utility import get_ar_index, validate_ip, handle_error
from ar_action_connect import SCUtilNew
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import arrow
from tzlocal import get_localzone

def dowork(self):
    """Activates machine scan on Tenable SC server

    Args:
        helper (object): object of ModularAlertBase class

    Returns:
        dict: The scan resource for the created scan or the error response from handle_error method
    """
    name_of_scan = self.get_param("name_of_scan")
    ip = self.get_param("ip")
    acc = self.get_param("account_name")
    if not name_of_scan.strip():
        return handle_error(
            self.logger,
            "SC",
            "No Scan name/ID has been provided. Please provide Scan name/ID to proceed."
        )
    if not ip.strip():
        return handle_error(
            self.logger,
            "SC",
            "No IP address has been provided. Please provide an IP address to proceed."
        )
    if not acc.strip():
        return handle_error(
            self.logger,
            "SC",
            "No account has been selected. Please select an account to proceed."
        )
    try:
        scu = SCUtilNew(self.session_key, acc, name_of_scan=name_of_scan)
    except Exception as e:
        return handle_error(
            self.logger,
            "SC",
            "Failed initializing TenableSC. Make sure you have SC account configured"
            " and you are running the AR action on SC notable event.",
            str(e)
        )

    # Validate IP
    if not validate_ip(ip):
        return handle_error(self.logger, "SC", "Invalid IP address")
    scan_found = False
    scans = scu.tsc.scans.list().get('usable')
    try:
        name_of_scan = int(name_of_scan)
        for scan in scans:
            if name_of_scan == int(scan.get("id")):
                scan_final = name_of_scan
                scan_found = True
                break
    except ValueError:
        for scan in scans:
            if scan.get('name').lower() == name_of_scan.lower():
                scan_final = int(scan.get("id"))
                scan_found = True
                break
    except Exception as err:
        return handle_error(
            self.logger, "SC", "An error occured. Error: {}".format(err))

    if not scan_found:
        return handle_error(self.logger, "SC", "Could not find scan with name/id: {}".format(name_of_scan))

    scan_template = scu.tsc.scans.details(id=scan_final)
    repo_id = scan_template.get("repository").get("id")
    scan_template.pop('name')
    tmp_scan_name = "{} - Splunk AR - {}".format(self.get_param("name_of_scan"), self.get_param("ip"))
	# Updates we will make to template before we create scan
    scan_updates = {}
    tzid_val = "TZID={}:{}".format(str(get_localzone()), arrow.now().strftime("%Y%m%dT%H%M%S"))
    ip_val = str(self.get_param("ip"))
    scan_updates = {"schedule": {"start": tzid_val, "repeatRule": "FREQ=NOW;INTERVAL=1", "type": "now"}, "ipList": ip_val}
	# Update Template
    scan_template.update(scan_updates)
	# Create scan
    try:
        scan_resource_resp = scu.tsc.scans.create(name=tmp_scan_name, repo=repo_id, **scan_template)
        return scan_resource_resp
    except Exception as e:
        return handle_error(self.logger, "SC", "Failed to activate scan", str(e))

def process_event(self, *args, **kwargs):
    """Write response event in sourcetype

    Args:
        helper (object): object of ModularAlertBase class

    Returns:
        int: return code
    """
    self.logger.info("Alert action activate_machine_scan started.")
    content = dowork(self)
    self.addevent(json.dumps(content, ensure_ascii=False),
                    sourcetype="tenable:sc:machinescan:ar")
    ar_index = get_ar_index(self.session_key)
    self.writeevents(index=ar_index)
    return 0
