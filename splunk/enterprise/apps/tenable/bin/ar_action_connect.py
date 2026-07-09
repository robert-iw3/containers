import json
import splunk.rest as rest

from ar_action_utility import get_passwords, get_certs_path, get_api_keys
from tenable_utility import get_proxy_settings, is_true, get_app_version

from tenable.io import TenableIO
from custom_http_adapter import CustomHTTPAdapter
from tenable.sc import TenableSC
import tenable_consts


class ArActionUtil(object):
    """ArActionUtil is a base class for IOUtil and SCUtil and keeps common parameters stored
    """
    def __init__(self, event, session_key):
        self.event = event
        self.session_key = session_key
        self.app_name = 'TA-tenable'
        self.build = get_app_version(self.app_name)

class ArActionUtilIO(object):
    """ArActionUtil is a base class for IOUtil and SCUtil and keeps common parameters stored
    """
    def __init__(self, event, session_key, account_name):
        self.event = event
        self.session_key = session_key
        self.app_name = 'TA-tenable'
        self.build = get_app_version(self.app_name)
        self.account_name = account_name


class ArActionUtilSC(object):
    """ArActionUtil is a base class for IOUtil and SCUtil and keeps common parameters stored
    """
    def __init__(self, session_key, account_name, name_of_scan=None, event=None):
        self.event = event
        self.session_key = session_key
        self.scan_name = name_of_scan
        self.account_name = account_name
        self.app_name = "TA-tenable"
        self.build = get_app_version(self.app_name)

class IOUtilNew(ArActionUtilIO):
    """IOUtil allows Tenable IO related AR actions to use common methods for making connections
    to IO instance
    """
    def __init__(self, event, session_key, account_name):
        """Init method for IOUtil

        Args:
            ArActionUtil (object): Base class having some common variables
            event (dict): event received from splunk to perform ar action
            helper (object): object of ModularAlertBase
        """
        super(IOUtilNew, self).__init__(event, session_key, account_name)
        self._set_input_data()

    def _set_input_data(self):
        """Set IO fields required to connect and initialize TenableIO object.
        """
        acceptable_account = False
        io_account_found = False

        _, content = rest.simpleRequest(
            "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_account/{}".format(self.account_name),
            sessionKey=self.session_key,
            getargs={"output_mode": "json"},
            raiseAllErrors=True)
        account_data = json.loads(content)["entry"]
        content = account_data[0]["content"]

        name = ""
        addr = None
        if content.get("tenable_account_type") == "tenable_io":
            addr = content.get("address")
            name = account_data[0]["name"]

        if name:
            io_account_found = True
            self.name = name
            self.address = addr
            account_info = account_data[0]["content"]
            creds = get_passwords(self.name, self.app_name, self.session_key)
            self.access_key = creds.get("access_key", "")
            self.secret_key = creds.get("secret_key", "")
            self.proxies = get_proxy_settings(global_account_dict=account_info)

            self.tio = TenableIO(
                access_key=self.access_key,
                secret_key=self.secret_key,
                url="https://" + self.address,
                proxies=self.proxies,
                vendor='Tenable',
                product='SplunkTA',
                build=self.build
            )
            if self.tio.session.details().get('permissions') < 32:
                raise Exception("AR actions require Scan Manager user permissions at minimum. Please update the account you are using to have Scan Manager permissions and try again.")


class IOUtil(ArActionUtil):
    """IOUtil allows Tenable IO related AR actions to use common methods for making connections
    to IO instance
    """
    def __init__(self, event, session_key):
        """Init method for IOUtil

        Args:
            ArActionUtil (object): Base class having some common variables
            event (dict): event received from splunk to perform ar action
            helper (object): object of ModularAlertBase
        """
        super(IOUtil, self).__init__(event, session_key)
        self._set_input_data()

    def _set_input_data(self):
        """Set IO fields required to connect and initialize TenableIO object.
        """
        self.userinfo = None
        self.address = self.event.get("IO_address")
        self.source = str(self.event.get("orig_source", "")).split("|")
        if len(self.source) > 1 and str(self.address) == str(self.source[1]):
            self.userinfo = str(self.source[0])
        acceptable_account = False
        io_account_found = False

        # get credentials
        _, content = rest.simpleRequest(
            "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_account",
            sessionKey=self.session_key,
            getargs={"output_mode": "json"},
            raiseAllErrors=True)
        account_data = json.loads(content)["entry"]
        for i in range(len(account_data)):
            ga = account_data[i].get("name")
            _, content = rest.simpleRequest(
                "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_account/"
                + ga,
                sessionKey=self.session_key,
                getargs={"output_mode": "json"},
                raiseAllErrors=True)
            data = json.loads(content)["entry"]
            content = data[0]["content"]
            name = ""
            addr = None
            if content.get("tenable_account_type") == "tenable_io":
                addr = content.get("address")
                if addr == self.address or not self.userinfo:
                    name = data[0]["name"]
            # if an account found exit the loop
            if name:
                io_account_found = True
                self.name = name
                account_info = data[0]["content"]
                creds = get_passwords(self.name, self.app_name, self.session_key)
                self.access_key = creds.get("access_key", "")
                self.secret_key = creds.get("secret_key", "")
                self.proxies = get_proxy_settings(global_account_dict=account_info)

                self.tio = TenableIO(
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    url="https://" + self.address,
                    proxies=self.proxies,
                    vendor='Tenable',
                    product='SplunkTA',
                    build=self.build
                )
                if self.tio.session.details().get('permissions') < 32:
                    continue
                acceptable_account = True
                break
        else:
            if io_account_found and not acceptable_account:
                raise Exception("AR actions require Scan Manager user permissions at minimum. Please update the account you are using to have Scan Manager permissions and try again.")
            if self.userinfo:
                msg = "Global Account of type tenable_io with Address: {} and Username: {} not found".format(
                    self.address, self.userinfo)
            else:
                msg = "Global Account of type tenable_io not found."
            raise Exception(msg)

class SCUtil(ArActionUtil):
    """SCUtil allows Tenable SC related AR actions to use common methods for making connections
    to SC instance
    """
    def __init__(self, event, session_key):
        """Init method for IOUtil

        Args:
            ArActionUtil (object): Base class having some common variables
            event (dict): event received from splunk to perform ar action
            helper (object): object of ModularAlertBase
        """
        super(SCUtil, self).__init__(event, session_key)
        # scan_name required only for request span ar action
        # self.scan_name = self.get_param("scan_name")

        self.name = ""
        self.verify_ssl = 0
        self.auth_type = "credentials"
        self.addr = None
        self.user = None
        self.certificate_path = None
        self.key_file_path = None
        self._set_input_data()

    def _set_input_data(self):
        """Set SC fields required to connect and initialize TenableSC object.
        """
        self.userinfo = None
        self.address = self.event.get("SC_address")
        self.source = str(self.event.get("orig_source", "")).split("|")
        if len(self.source) > 1 and str(self.address) == str(self.source[1]):
            self.userinfo = str(self.source[0])

        # get credentials
        _, content = rest.simpleRequest(
            "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_account",
            sessionKey=self.session_key,
            getargs={"output_mode": "json"},
            raiseAllErrors=True)
        account_data = json.loads(content)["entry"]
        for i in range(len(account_data)):
            ga = account_data[i].get("name")
            _, content = rest.simpleRequest(
                "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_account/"
                + ga,
                sessionKey=self.session_key,
                getargs={"output_mode": "json"},
                raiseAllErrors=True)
            data = json.loads(content)["entry"]
            content = data[0]["content"]

            name = ""
            verify_ssl = False
            auth_type = "credentials"
            addr = None
            user = None
            certificate_path = None
            key_file_path = None
            if content.get("tenable_account_type"
                           ) == "tenable_securitycenter_credentials":
                addr = content.get("address")
                user = content.get("username", "")
                verify_ssl = tenable_consts.verify_ssl_for_sc_creds
                if (addr == self.address
                        and user == self.userinfo) or (not self.userinfo):
                    name = data[0]["name"]

            elif content.get("tenable_account_type"
                             ) == "tenable_securitycenter_api_keys":
                auth_type = "api_keys"
                addr = content.get("address")
                user = content.get("username", "")
                verify_ssl = tenable_consts.verify_ssl_for_sc_api_key
                self.address = addr
                if not self.userinfo:
                    name = data[0]["name"]

            elif content.get("tenable_account_type"
                             ) == "tenable_securitycenter_certificate":
                auth_type = "certificate"
                addr = content.get("address")
                certificate_path = content.get("certificate_path")
                key_file_path = content.get("key_file_path")
                verify_ssl = tenable_consts.verify_ssl_for_sc_cert
                self.address = addr
                if not self.userinfo:
                    name = data[0]["name"]
            if verify_ssl and is_true(content.get("use_ca_cert")):
                verify_ssl = tenable_consts.CUSTOM_CERT_FILE_LOC.format(ga)
            if name:
                break

        self.user = user
        self.verify_ssl = verify_ssl
        self.name = name
        self.auth_type = auth_type
        self.certificate_path = certificate_path
        self.key_file_path = key_file_path

        self.account_info = data[0]["content"]

        # if no account found raise exception
        if not self.name:
            if self.userinfo:
                msg = "Global Account of type tenable_sc with Address: {} and Username/Certificate: {} not found".format(
                    self.address, self.userinfo)
            else:
                msg = "Global Account of type tenable_sc not found"
            raise Exception(msg)

        self.sc_access_key = ""
        self.sc_secret_key = ""
        if self.auth_type == "api_keys" or self.auth_type == "certificate":
            sc_api_keys = get_api_keys(self.name, self.app_name, self.session_key)
            self.sc_access_key = sc_api_keys.get("sc_access_key", "")
            self.sc_secret_key = sc_api_keys.get("sc_secret_key", "")

        creds = get_passwords(self.name, self.app_name, self.session_key)
        self.password = creds.get("password", "")
        self.certificate_key_password = creds.get("key_password", "")
        self.account_info["proxy_password"] = creds.get("proxy_password", "")
        self.proxies = get_proxy_settings(
            global_account_dict=self.account_info)

        # create TenableSC connection
        if self.auth_type == "certificate":
            self.certificate_path, self.key_file_path = get_certs_path(
                self.app_name, self.certificate_path, self.key_file_path)
            adapter = CustomHTTPAdapter(certfile=self.certificate_path,
                                        keyfile=self.key_file_path,
                                        password=self.certificate_key_password)
            self.tsc = TenableSC(self.address,
                                 ssl_verify=self.verify_ssl,
                                 proxies=self.proxies,
                                 adapter=adapter,
                                 access_key=self.sc_access_key,
                                 secret_key=self.sc_secret_key
                                 )

        elif self.auth_type == "api_keys":
            self.tsc = TenableSC(
                host=self.address,
                access_key=self.sc_access_key,
                secret_key=self.sc_secret_key,
                ssl_verify=self.verify_ssl,
                proxies=self.proxies)

        else:
            self.tsc = TenableSC(self.address,
                                 ssl_verify=self.verify_ssl,
                                 proxies=self.proxies)
            self.tsc.login(self.user, self.password)

class SCUtilNew(ArActionUtilSC):
    """SCUtil allows Tenable SC related AR actions to use common methods for making connections
    to SC instance
    """
    def __init__(self, session_key, account_name, name_of_scan=None, event=None):
        """Init method for IOUtil

        Args:
            ArActionUtil (object): Base class having some common variables
            event (dict): event received from splunk to perform ar action
            helper (object): object of ModularAlertBase
        """
        super(SCUtilNew, self).__init__(session_key, account_name, name_of_scan, event)
        self.scan_name = name_of_scan
        self.event = event
        self.account_name = account_name
        self.name = ""
        self.verify_ssl = 0
        self.auth_type = "credentials"
        self.addr = None
        self.user = None
        self.certificate_path = None
        self.key_file_path = None
        self._set_input_data()

    def _set_input_data(self):
        """Set SC fields required to connect and initialize TenableSC object.
        """
        # get credentials
        _, content = rest.simpleRequest(
            "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_account/{}".format(self.account_name),
            sessionKey=self.session_key,
            getargs={"output_mode": "json"},
            raiseAllErrors=True)
        account_data = json.loads(content)["entry"]
        content = account_data[0]["content"]

        name = ""
        verify_ssl = False
        auth_type = "credentials"
        addr = None
        user = None
        certificate_path = None
        key_file_path = None
        if content.get("tenable_account_type"
                        ) == "tenable_securitycenter_credentials":
            addr = content.get("address")
            user = content.get("username", "")
            verify_ssl = tenable_consts.verify_ssl_for_sc_creds
            self.address = addr
            name = account_data[0]["name"]

        elif content.get("tenable_account_type"
                            ) == "tenable_securitycenter_api_keys":
            auth_type = "api_keys"
            addr = content.get("address")
            user = content.get("username", "")
            verify_ssl = tenable_consts.verify_ssl_for_sc_api_key
            self.address = addr
            name = account_data[0]["name"]

        elif content.get("tenable_account_type"
                            ) == "tenable_securitycenter_certificate":
            auth_type = "certificate"
            addr = content.get("address")
            certificate_path = content.get("certificate_path")
            key_file_path = content.get("key_file_path")
            verify_ssl = tenable_consts.verify_ssl_for_sc_cert
            self.address = addr
            name = account_data[0]["name"]

        if verify_ssl and is_true(content.get("use_ca_cert")):
            verify_ssl = tenable_consts.CUSTOM_CERT_FILE_LOC.format(self.account_name)

        self.user = user
        self.verify_ssl = verify_ssl
        self.name = name
        self.auth_type = auth_type
        self.certificate_path = certificate_path
        self.key_file_path = key_file_path

        self.account_info = account_data[0]["content"]

        # if no account found raise exception
        if not self.name:
            msg = "Global Account of type tenable_sc not found"
            raise Exception(msg)

        self.sc_access_key = ""
        self.sc_secret_key = ""
        if self.auth_type == "api_keys" or self.auth_type == "certificate":
            sc_api_keys = get_api_keys(self.name, self.app_name, self.session_key)
            self.sc_access_key = sc_api_keys.get("sc_access_key", "")
            self.sc_secret_key = sc_api_keys.get("sc_secret_key", "")

        creds = get_passwords(self.name, self.app_name, self.session_key)
        self.password = creds.get("password", "")
        self.certificate_key_password = creds.get("key_password", "")
        self.account_info["proxy_password"] = creds.get("proxy_password", "")
        self.proxies = get_proxy_settings(
            global_account_dict=self.account_info)

        # create TenableSC connection
        if self.auth_type == "certificate":
            self.certificate_path, self.key_file_path = get_certs_path(
                self.app_name, self.certificate_path, self.key_file_path)
            adapter = CustomHTTPAdapter(certfile=self.certificate_path,
                                        keyfile=self.key_file_path,
                                        password=self.certificate_key_password)
            self.tsc = TenableSC(self.address,
                                 ssl_verify=self.verify_ssl,
                                 proxies=self.proxies,
                                 adapter=adapter,
                                 access_key=self.sc_access_key,
                                 secret_key=self.sc_secret_key
                                 )

        elif self.auth_type == "api_keys":
            self.tsc = TenableSC(
                host=self.address,
                access_key=self.sc_access_key,
                secret_key=self.sc_secret_key,
                ssl_verify=self.verify_ssl,
                proxies=self.proxies)

        else:
            self.tsc = TenableSC(self.address,
                                 ssl_verify=self.verify_ssl,
                                 proxies=self.proxies)
            self.tsc.login(self.user, self.password)
