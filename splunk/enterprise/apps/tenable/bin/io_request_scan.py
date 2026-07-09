# encoding = utf-8
# Always put this line at the beginning of this file
import import_declare_test  # noqa: F401
import sys

from alert_actions_base import ModularAlertBase
import modalert_io_request_scan_helper


class AlertActionWorkerIORequestScan(ModularAlertBase):

    def __init__(self, ta_name, alert_name):
        super(AlertActionWorkerIORequestScan,
              self).__init__(ta_name, alert_name)

    def process_event(self, *args, **kwargs):
        status = 0
        try:
            status = modalert_io_request_scan_helper.process_event(
                self, *args, **kwargs)
        except (AttributeError, TypeError) as ae:
            self.log_error(
                "Error: {}. Please double check spelling and also verify that a compatible version of Splunk_SA_CIM is installed.".format(str(ae)))
            return 4
        except Exception as e:
            msg = "Unexpected error: {}."
            if str(e):
                self.log_error(msg.format(str(e)))
            else:
                import traceback
                self.log_error(msg.format(traceback.format_exc()))
            return 5
        return status


if __name__ == "__main__":
    exitcode = AlertActionWorkerIORequestScan(
        "TA-tenable", "io_request_scan").run(sys.argv)
    sys.exit(exitcode)
