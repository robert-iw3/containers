import os
import sys
import json
from ar_action_utility import get_ar_index, validate_ip, handle_error
from ar_action_connect import IOUtilNew

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def dowork(self):
    """Requests a scan on Tenable IO asset

    Args:
        helper (object): object of ModularAlertBase class

    Returns:
        dict: either the scan launch response or error response from handle_error method
    """
    events = self.get_events()
    ip = self.get_param("ip")
    host_name = self.get_param("host_name")
    scan_name = self.get_param("scan_name")
    acc = self.get_param("account_name")
    for event in events:
        try:
            iou = IOUtilNew(event, self.session_key, acc)
        except Exception as e:
            if "Scan Manager permissions" in str(e):
                return handle_error(self.logger, "IO", "An error occured.", str(e))
            return handle_error(
                self.logger,
                "IO",
                "Failed initializing TenableIO. Make sure you have IO account configured"
                " and you are running the AR action on IO notable event.",
                str(e)
            )
        # if ip or host name is not provided try to get target from event
        if not ip and not host_name:
            target = event.get("dest_ip") if event.get(
                "dest_ip") else event.get("dest")
        elif ip:
            if not validate_ip(ip):
                return handle_error(self.logger, "IO", "Invalid IP address")
            else:
                target = ip
        else:
            target = host_name

        try:
            scans_resource_list = iou.tio.scans.list()
        except Exception as e:
            return handle_error(self.logger, "IO", "Failed to get fetch scan ID", str(e))
        scan_id = None
        for scan in scans_resource_list:
            # return with error response when multiple scan ids are found for given scan name
            if scan_name == scan.get("name"):
                if not scan_id:
                    scan_id = scan.get("id")
                else:
                    return handle_error(
                        self.logger,
                        "IO",
                        "Multiple scan IDs found for the given scan name: {}"
                        .format(scan_name))
        if not scan_id:
            return handle_error(
                self.logger,
                "IO",
                "No scan ID found for the given scan name: {}".format(scan_name)
            )
        try:
            # launch the scan
            scan_instance_uuid = iou.tio.scans.launch(scan_id,
                                                      targets=[target])
            return {"scan_instance_uuid": scan_instance_uuid}
        except Exception as e:
            return handle_error(self.logger, "IO", "Failed to launch the scan", str(e))

def process_event(self, *args, **kwargs):
    """Write response event in sourcetype

    Args:
        helper (object): object of ModularAlertBase class

    Returns:
        int: return code
    """
    self.logger.info("Alert action get_io_vulnerability_summary started.")
    data = dowork(self)
    self.addevent(json.dumps(data, ensure_ascii=False), sourcetype="tenable:io:scan:ar")
    ar_index = get_ar_index(self.session_key)
    self.writeevents(index=ar_index)
    return 0
