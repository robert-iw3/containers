import csv
import gzip
import logging
import sys
from setup_logger import setup_logging
from splunktaucclib.cim_actions import ModularAction
from splunktaucclib.splunk_aoblib.rest_helper import TARestHelper
from splunktaucclib.splunk_aoblib.setup_util import Setup_Util
class ModularAlertBase(ModularAction):
    def __init__(self, ta_name, alert_name):
        self._alert_name = alert_name
        self._logger_name = alert_name + "_modalert"
        self._logger = setup_logging(self._logger_name)
        super(ModularAlertBase, self).__init__(
            sys.stdin.read(), self._logger, alert_name
        )
        self.setup_util_module = None
        self.setup_util = None
        self.result_handle = None
        self.ta_name = ta_name
        self.splunk_uri = self.settings.get("server_uri")
        self.setup_util = Setup_Util(self.splunk_uri, self.session_key, self._logger)
        self.rest_helper = TARestHelper(self._logger)
    def log_error(self, msg):
        self.message(msg, "failure", level=logging.ERROR)
    def log_info(self, msg):
        self.message(msg, "success", level=logging.INFO)
    def log_debug(self, msg):
        self.message(msg, None, level=logging.DEBUG)
    def log_warn(self, msg):
        self.message(msg, None, level=logging.WARN)
    def set_log_level(self, level):
        self._logger.setLevel(level)
    def get_param(self, param_name):
        return self.configuration.get(param_name)
    def get_global_setting(self, var_name):
        return self.setup_util.get_customized_setting(var_name)
    def get_user_credential(self, username):
        """
        if the username exists, return
        {
            "username": username,
            "password": credential
        }
        """
        return self.setup_util.get_credential_by_username(username)
    def get_user_credential_by_account_id(self, account_id):
        """
        if the account_id exists, return
        {
            "username": username,
            "password": credential
        }
        """
        return self.setup_util.get_credential_by_id(account_id)
    @property
    def log_level(self):
        return self.get_log_level()
    @property
    def proxy(self):
        return self.get_proxy()
    def get_log_level(self):
        return self.setup_util.get_log_level()
    def get_proxy(self):
        """if the proxy setting is set. return a dict like
        {
        proxy_url: ... ,
        proxy_port: ... ,
        proxy_username: ... ,
        proxy_password: ... ,
        proxy_type: ... ,
        proxy_rdns: ...
        }
        """
        return self.setup_util.get_proxy_settings()
    def _get_proxy_uri(self):
        uri = None
        proxy = self.get_proxy()
        if proxy and proxy.get("proxy_url") and proxy.get("proxy_type"):
            uri = proxy["proxy_url"]
            if proxy.get("proxy_port"):
                uri = "{0}:{1}".format(uri, proxy.get("proxy_port"))
            if proxy.get("proxy_username") and proxy.get("proxy_password"):
                uri = "{0}://{1}:{2}@{3}/".format(
                    proxy["proxy_type"],
                    proxy["proxy_username"],
                    proxy["proxy_password"],
                    uri,
                )
            else:
                uri = "{0}://{1}".format(proxy["proxy_type"], uri)
        return uri
    def send_http_request(
        self,
        url,
        method,
        parameters=None,
        payload=None,
        headers=None,
        cookies=None,
        verify=True,
        cert=None,
        timeout=None,
        use_proxy=True,
    ):
        return self.rest_helper.send_http_request(
            url=url,
            method=method,
            parameters=parameters,
            payload=payload,
            headers=headers,
            cookies=cookies,
            verify=verify,
            cert=cert,
            timeout=timeout,
            proxy_uri=self._get_proxy_uri() if use_proxy else None,
        )
    def process_event(self, *args, **kwargs):
        raise NotImplementedError("Derived class shall overrides this")
    def pre_handle(self, num, result):
        result.setdefault("rid", str(num))
        self.update(result)
        return result
    def get_events(self):
        try:
            self.result_handle = gzip.open(self.results_file, "rt")
            return (
                self.pre_handle(num, result)
                for num, result in enumerate(csv.DictReader(self.result_handle))
            )
        except IOError:
            msg = "Error: {}."
            self.log_error(msg.format("No search result. Cannot send alert action."))
            sys.exit(2)
    def prepare_meta_for_cam(self):
        rf = None
        try:
            try:
                rf = gzip.open(self.results_file, 'rt')
            except ValueError:  # Workaround for Python 2.7 on Windows
                rf = gzip.open(self.results_file, 'r')
            except FileNotFoundError:
                self.log_info("No Results file found.")
            if rf:
                for num, result in enumerate(csv.DictReader(rf)):
                    result.setdefault('rid', str(num))
                    self.update(result)
                    self.invoke()
                    break
        finally:
            if rf:
                rf.close()

    def run(self, argv):
        status = 0
        if len(argv) < 2 or argv[1] != "--execute":
            msg = 'Error: argv="{}", expected="--execute"'.format(argv)
            print(msg, file=sys.stderr)
            sys.exit(1)
        # prepare meta first for permission lack error handling: TAB-2455
        try:
            level = self.get_log_level()
            if level:
                self._logger.setLevel(level)
        except Exception as e:
            if str(e) and "403" in str(e):
                self.log_error("User does not have permissions")
            else:
                self.log_error("Unable to set log level")
            sys.exit(2)
        self.prepare_meta_for_cam()
        try:
            status = self.process_event()
        except IOError:
            msg = "Error: {}."
            self.log_error(msg.format("No search result. Cannot send alert action."))
            sys.exit(2)
        except Exception as e:
            msg = "Unexpected error: {}."
            if str(e):
                self.log_error(msg.format(str(e)))
            else:
                import traceback
                self.log_error(msg.format(traceback.format_exc()))
            sys.exit(2)
        finally:
            if self.result_handle:
                self.result_handle.close()
        return status
