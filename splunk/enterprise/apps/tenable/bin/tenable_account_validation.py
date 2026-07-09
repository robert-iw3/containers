import os
import io
import json
import six.moves.configparser
import splunk.admin as admin
import splunk.entity as entity
from splunk.clilib.bundle_paths import make_splunkhome_path
from splunktaucclib.rest_handler.endpoint.validator import Validator
from tenable_utility import get_proxy_settings, get_app_version, get_host_port, is_true, save_cert_file, get_credentials
from tenable.io import TenableIO as TIO
from tenable.asm.session import TenableASM
from tenable.sc import TenableSC as TSC
from tenable.ot.session import TenableOT as TOT
from custom_http_adapter import CustomHTTPAdapter
from distutils.version import LooseVersion
from ssl import SSLError
import tenable_consts
from setup_logger import setup_logging

from tenable.errors import ConnectionError

logger = setup_logging("ta_tenable_account_validation")

def get_ssl_and_save_cert_file(custom_certificate, account_name):
    """
    Get SSL and save custom certificate file.

    :param session_key: session key
    :param use_ca_cert: use ca certificate
    :param custom_certificate: custom certificate
    :param account_name: account name
    :return: verify_ssl or cert_file_loc
    """
    try:
        cert_file_loc = save_cert_file(
            custom_certificate, tenable_consts.CUSTOM_CERT_FILE_LOC.format(account_name), logger
        )
        return cert_file_loc
    except Exception as e:
        logger.error("Error while saving custom certificate: {}".format(e))


class GetSessionKey(admin.MConfigHandler):
    def __init__(self):
        self.session_key = self.getSessionKey()


class Utility:
    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def get_entities(self, app_name):
        session_key_obj = GetSessionKey()
        session_key = session_key_obj.session_key
        return entity.getEntities(['admin', 'passwords'], namespace=app_name, owner='nobody', sessionKey=session_key, search=app_name)

    def get_access_key(self, app_name, global_account_name):
        for _, value in self.get_entities(app_name).items():
            if value['username'].partition('`')[0] == str(global_account_name) and not value['clear_password'].startswith('`'):
                cred = json.loads(value['clear_password'])
                return cred.get('access_key', '')

    def get_sc_access_key(self, app_name, global_account_name):
        for _, value in self.get_entities(app_name).items():
            if value['username'].partition('`')[0] == str(global_account_name) and not value['clear_password'].startswith('`'):
                cred = json.loads(value['clear_password'])
                return cred.get('tenable_sc_access_key', '')

    def get_proxy(self, data):
        return get_proxy_settings(global_account_dict=data)

    def check_uniqueness_of_account(self, session_key, path, app_name, tenable_account_name, tenable_account_type, address, username, certficate_path, access_key, sc_access_key):
        msg = ''
        if os.path.exists(tenable_consts.ACCOUTNS_CONF_LOCAL_PATH):
            accounts_conf, _ = get_credentials(session_key, None)
            stanzas = list(accounts_conf.get_all().keys())
            for stanza in stanzas:
                if stanza == tenable_account_name or accounts_conf.get(stanza).get('tenable_account_type') == "tenable_asm":
                    continue
                tenable_account_found = accounts_conf.get(stanza).get('tenable_account_type')
                [host, port, complete_address] = get_host_port(accounts_conf.get(stanza).get('address'))
                if tenable_account_found == tenable_account_type == "tenable_securitycenter_credentials" and address == complete_address and username == accounts_conf.get(stanza).get('username'):
                    msg = "Account with same Address and Username already exists!"
                elif tenable_account_found == tenable_account_type == "tenable_securitycenter_certificate" and address == complete_address and certficate_path == accounts_conf.get(stanza).get('certificate_path'):
                    msg = "Account with same Address and Certificate already exists!"
                elif tenable_account_found == tenable_account_type == "tenable_io" and address == complete_address and access_key == self.get_access_key(app_name, stanza):
                    msg = "Account with same Address and Access Key already exists!"
                elif tenable_account_found == tenable_account_type == "tenable_securitycenter_api_keys" and address == complete_address and sc_access_key == self.get_sc_access_key(app_name, stanza):
                    msg = "Account with same Address and Access Key already exists!"
        return msg


class Address(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(Address, self).__init__()
        self._args = args
        self._kwargs = kwargs

    def validate(self, value, data):
        return True


class Proxy(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(Proxy, self).__init__()
        self._args = args
        self._kwargs = kwargs

    def validate(self, value, data):
        try:
            if data.get('proxy_enabled', 'false').lower() not in ['0', 'false', 'f']:
                if not data.get('proxy_url'):
                    msg = 'Proxy Host can not be empty'
                    raise Exception(msg)
                elif not data.get('proxy_port'):
                    msg = 'Proxy Port can not be empty'
                    raise Exception(msg)
                elif (data.get('proxy_username') and not data.get('proxy_password')) or (not data.get('proxy_username') and data.get('proxy_password')):
                    msg = 'Please provide both proxy username and proxy password'
                    raise Exception(msg)
                elif not data.get('proxy_type'):
                    msg = 'Proxy Type can not be empty'
                    raise Exception(msg)
        except Exception as exc:
            self.put_msg(exc)
            return False
        else:
            return True


class TenableAccountType(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(TenableAccountType, self).__init__()
        self._args = args
        self._kwargs = kwargs

    def validate(self, value, data):
        try:
            if data.get("tenable_account_type") == "tenable_io":
                if not data.get("access_key"):
                    msg = "Account Type Tenable.io is selected but Access Key is not provided!"
                    raise Exception(msg)
                elif not data.get("secret_key"):
                    msg = "Account Type Tenable.io is selected but Secret Key is not provided!"
                    raise Exception(msg)
            elif data.get("tenable_account_type") == "tenable_securitycenter_credentials":
                if not data.get("username"):
                    msg = "Account Type Tenable.sc Credentials is selected but Username is not provided!"
                    raise Exception(msg)
                elif not data.get("password"):
                    msg = "Account Type Tenable.sc Credentials is selected but Password is not provided!"
                    raise Exception(msg)
            elif data.get("tenable_account_type") == "tenable_securitycenter_api_keys":
                if not data.get("tenable_sc_access_key"):
                    msg = "Account Type Tenable.sc API Key is selected but Access key is not provided!"
                    raise Exception(msg)
                elif not data.get("tenable_sc_secret_key"):
                    msg = "Account Type Tenable.sc API Key is selected but Secret key is not provided!"
                    raise Exception(msg)
            elif data.get("tenable_account_type") == "tenable_securitycenter_certificate":
                if not data.get("tenable_sc_access_key"):
                    msg = "Account Type Tenable.sc Certificate is selected but Access key is not provided!"
                    raise Exception(msg)
                elif not data.get("tenable_sc_secret_key"):
                    msg = "Account Type Tenable.sc Certificate is selected but Secret key is not provided!"
                    raise Exception(msg)
                elif not data.get("certificate_path"):
                    msg = "Account Type Tenable.sc Certificate is selected but Certificate Path is not provided!"
                    raise Exception(msg)
                elif not data.get("key_file_path"):
                    msg = "Account Type Tenable.sc Certificate is selected but Key File Path is not provided!"
                    raise Exception(msg)
            elif data.get("tenable_account_type") == "tenable_ot_security_icp":
                if not data.get("api_secret"):
                    msg = "Account Type Tenable OT Security (ICP) is selected but API Secret is not provided!"
                    raise Exception(msg)
        except Exception as exc:
            self.put_msg(exc)
            return False
        else:
            return True


class Credentials(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(Credentials, self).__init__()
        self._args = args
        self._kwargs = kwargs
        self.path = os.path.abspath(__file__)
        self.util = Utility()

    def validate(self, value, data):
        if data.get("tenable_account_type") == "tenable_securitycenter_credentials":
            try:
                logger.info("Tenable SC (Credentials): Validating account details.")
                # Check uniqueness
                app_name = self.path.split(
                    '/')[-3] if '/' in self.path else self.path.split('\\')[-3]
                [host,port,complete_address] = get_host_port(data.get("address"))
                session_key_obj = GetSessionKey()
                session_key = session_key_obj.session_key
                msg = self.util.check_uniqueness_of_account(
                    session_key,
                    os.path.dirname(self.path).split('bin')[0],
                    app_name,
                    data.get('name'),
                    data.get("tenable_account_type"),
                    complete_address,
                    data.get("username"),
                    data.get("certificate_path"),
                    data.get("access_key"),
                    data.get("tenable_sc_access_key")
                )
                if msg:
                    raise Exception(msg)
                try:
                    # defined retries as 3 in the TSC to reduce the
                    # response time of the request when wrong port is entered.
                    use_ca_cert = data.get("use_ca_cert")
                    verify_ssl = tenable_consts.verify_ssl_for_sc_creds
                    if verify_ssl and is_true(use_ca_cert):
                        custom_certificate = data.get("custom_certificate", "").strip()
                        cert_file_loc = verify_ssl = get_ssl_and_save_cert_file(custom_certificate, data.get("name"))

                    tsc = TSC(
                        host=host,
                        port=port,
                        retries=3,
                        ssl_verify=verify_ssl,
                        proxies=self.util.get_proxy(data),
                        vendor='Tenable',
                        product='SplunkTA',
                        build=get_app_version(app_name)
                    )
                    tsc.login(data.get("username"), data.get("password"))
                    sc_version = tsc.system.details().get('version')
                except ConnectionError as e:
                    raise Exception(str(e))
                except Exception:
                    msg = "Please enter valid Address, Username and Password or configure valid proxy settings or verify SSL certificate."
                    raise Exception(msg)
                else:
                    if LooseVersion(sc_version) < LooseVersion('5.7.0'):
                        raise Exception("Please upgrade SC version to 5.7.0 or above")
                finally:
                    try:
                        tsc.logout()
                    except:  # noqa: E722
                        pass
            except Exception as exc:
                if is_true(data.get("use_ca_cert")) and data.get("custom_certificate") and os.path.exists(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name"))):
                    os.remove(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name")))
                logger.error("Tenable SC (Credentials): Error occured while validating account. Error: {}".format(exc))
                self.put_msg(exc)
                return False
            else:
                logger.info("Tenable SC (Credentials): Account validated successfully.")
                data["access_key"] = ''
                data["secret_key"] = ''
                data["certificate_path"] = ''
                data["key_file_path"] = ''
                data["key_password"] = ''
                data["tenable_sc_access_key"] = ''
                data["tenable_sc_secret_key"] = ''
                return True
        else:
            return True


class ScAPIKeys(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(ScAPIKeys, self).__init__()
        self._args = args
        self._kwargs = kwargs
        self.path = os.path.abspath(__file__)
        self.util = Utility()

    def validate(self, value, data):
        if data.get("tenable_account_type") == "tenable_securitycenter_api_keys":
            try:
                logger.info("Tenable SC (API keys): Validating account details.")
                # Check uniqueness
                app_name = self.path.split(
                    '/')[-3] if '/' in self.path else self.path.split('\\')[-3]
                [host,port,complete_address] = get_host_port(data.get("address"))
                session_key_obj = GetSessionKey()
                session_key = session_key_obj.session_key
                msg = self.util.check_uniqueness_of_account(
                    session_key,
                    os.path.dirname(self.path).split('bin')[0],
                    app_name,
                    data.get('name'),
                    data.get("tenable_account_type"),
                    complete_address,
                    data.get("username"),
                    data.get("certificate_path"),
                    data.get("access_key"),
                    data.get("tenable_sc_access_key")
                )
                if msg:
                    raise Exception(msg)
                try:
                    # defined retries as 3 in the TSC to reduce the
                    # response time of the request when wrong port is entered.
                    use_ca_cert = data.get("use_ca_cert")
                    verify_ssl = tenable_consts.verify_ssl_for_sc_api_key
                    if verify_ssl and is_true(use_ca_cert):
                        custom_certificate = data.get("custom_certificate", "").strip()
                        cert_file_loc = verify_ssl = get_ssl_and_save_cert_file(custom_certificate, data.get("name"))

                    tsc = TSC(
                        host=host,
                        port=port,
                        retries=3,
                        access_key=data.get("tenable_sc_access_key"),
                        secret_key=data.get("tenable_sc_secret_key"),
                        ssl_verify=verify_ssl,
                        proxies=self.util.get_proxy(data),
                        vendor='Tenable',
                        product='SplunkTA',
                        build=get_app_version(app_name)
                    )
                    sc_version = tsc.system.details().get('version')
                except ConnectionError as e:
                    raise Exception(str(e))
                except:  # noqa: E722
                    msg = "Please enter valid Address, SC Access key and SC Secret key or configure valid proxy settings or verify SSL certificate."
                    raise Exception(msg)
                else:
                    if LooseVersion(sc_version) < LooseVersion('5.7.0'):
                        raise Exception("Please upgrade SC version to 5.7.0 or above")
                finally:
                    try:
                        tsc.logout()
                    except:  # noqa: E722
                        pass
            except Exception as exc:
                logger.error("Tenable SC (API keys): Error occured while validating account. Error: {}".format(str(exc)))
                if is_true(data.get("use_ca_cert")) and data.get("custom_certificate") and os.path.exists(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name"))):
                    os.remove(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name")))
                self.put_msg(exc)
                return False
            else:
                logger.info("Tenable SC (API keys): Account validated successfully.")
                data["access_key"] = ''
                data["secret_key"] = ''
                data["username"] = ''
                data["password"] = ''
                data["certificate_path"] = ''
                data["key_file_path"] = ''
                data["key_password"] = ''
                return True
        else:
            return True


class Certificate(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(Certificate, self).__init__()
        self._args = args
        self._kwargs = kwargs
        self.path = os.path.abspath(__file__)
        self.util = Utility()

    def validate(self, value, data):
        if data.get("tenable_account_type") == "tenable_securitycenter_certificate":
            try:
                logger.info("Tenable SC (Certificate): Validating account details.")
                # Checking Uniqueness
                app_name = self.path.split('/')[-3] if '/' in self.path else self.path.split('\\')[-3]
                [host,port,complete_address] = get_host_port(data.get("address"))
                session_key_obj = GetSessionKey()
                session_key = session_key_obj.session_key
                msg = self.util.check_uniqueness_of_account(
                    session_key,
                    os.path.dirname(self.path).split('bin')[0],
                    app_name,
                    data.get('name'),
                    data.get("tenable_account_type"),
                    complete_address,
                    data.get("username"),
                    data.get("certificate_path"),
                    data.get("access_key"),
                    data.get("tenable_sc_access_key")
                )
                if msg:
                    raise Exception(msg)
                base_path = self.path.split(app_name)[0]
                cert_base_path = base_path + app_name + "/certs/"
                certificate_path_list = data.get("certificate_path").split(
                    '/') if '/' in data.get("certificate_path") else data.get("certificate_path").split('\\')
                certificate_path = key_file_path = cert_base_path
                for path in certificate_path_list:
                    certificate_path = os.path.join(certificate_path, path)
                if not os.path.exists(certificate_path):
                    msg = "Certificate Path: {} not found.".format(
                        certificate_path)
                    raise Exception(msg)

                key_path_list = data.get("key_file_path").split(
                    '/') if '/' in data.get("key_file_path") else data.get("key_file_path").split('\\')
                for path in key_path_list:
                    key_file_path = os.path.join(key_file_path, path)
                if not os.path.exists(key_file_path):
                    msg = "Key File Path: {} not found.".format(key_file_path)
                    raise Exception(msg)

                cert_key_password = data.get('key_password', '')

                try:
                    adapter = CustomHTTPAdapter(certfile=certificate_path, keyfile=key_file_path, password=cert_key_password)
                    # defined retries as 3 in the TSC to reduce the
                    # response time of the request when wrong port is entered.
                    use_ca_cert = data.get("use_ca_cert")
                    verify_ssl = tenable_consts.verify_ssl_for_sc_cert
                    if verify_ssl and is_true(use_ca_cert):
                        custom_certificate = data.get("custom_certificate", "").strip()
                        cert_file_loc = verify_ssl = get_ssl_and_save_cert_file(custom_certificate, data.get("name"))

                    tsc = TSC(host=host, port=port, retries=3, access_key=data.get("tenable_sc_access_key"),
                              secret_key=data.get("tenable_sc_secret_key"), ssl_verify=verify_ssl,
                              proxies=self.util.get_proxy(data),
                              adapter=adapter)
                    tsc.scans.list()
                except ConnectionError as e:
                    raise Exception(str(e))
                except SSLError:
                    msg = "Please provide valid Certificate file, Key file or Key Password."
                    raise Exception(msg)
                except:  # noqa: E722
                    msg = "Please enter valid Address, configure valid proxy settings or verify SSL certificate."
                    raise Exception(msg)
            except Exception as exc:
                logger.error("Tenable SC (Certificate): Error occured while validating account. Error: {}".format(str(exc)))
                if is_true(data.get("use_ca_cert")) and data.get("custom_certificate") and os.path.exists(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name"))):
                    os.remove(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name")))
                self.put_msg(exc)
                return False
            else:
                logger.info("Tenable SC (Certificate): Account validated successfully.")
                data["access_key"] = ''
                data["secret_key"] = ''
                data["username"] = ''
                data["password"] = ''
                data["tenable_sc_access_key"] = ''
                data["tenable_sc_secret_key"] = ''
                return True
        else:
            return True


class TenableIO(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(TenableIO, self).__init__()
        self._args = args
        self._kwargs = kwargs
        self.path = os.path.abspath(__file__)
        self.util = Utility()

    def validate(self, value, data):
        if data.get("tenable_account_type") == "tenable_io":
            try:
                logger.info("Tenable IO: Validating account details.")
                app_name = self.path.split(
                    '/')[-3] if '/' in self.path else self.path.split('\\')[-3]
                session_key_obj = GetSessionKey()
                session_key = session_key_obj.session_key
                msg = self.util.check_uniqueness_of_account(
                    session_key,
                    os.path.dirname(self.path).split("bin")[0],
                    app_name,
                    data.get("name"),
                    data.get("tenable_account_type"),
                    data.get("address"),
                    data.get("username"),
                    data.get("certificate_path"),
                    data.get("access_key"),
                    data.get("tenable_sc_access_key"),
                )
                if msg:
                    raise Exception(msg)
                try:
                    # Respect SSL verify from account page for when customers MITM our connection...
                    tio = TIO(
                        access_key=data.get("access_key"),
                        secret_key=data.get("secret_key"),
                        url="https://" + data.get("address").strip('/'),
                        proxies=self.util.get_proxy(data),
                        vendor='Tenable',
                        product='SplunkTA',
                        build=get_app_version(app_name)
                    )
                except Exception as e:
                    msg = "Please enter valid Address, Access key and Secret key or configure valid proxy settings or verify SSL certificate. {}".format(e)
                    raise Exception(msg)
                if tio.session.details().get('permissions') < 16:
                    msg = 'This integration requires basic user permissions at minimum. Please update the account you are using to have basic permissions and try again.'
                    raise Exception(msg)

            except Exception as exc:
                logger.error("Tenable IO: Error occured while validating account. Error: {}".format(exc))
                self.put_msg(exc)
                return False
            else:
                logger.info("Tenable IO: Account validated successfully.")
                data["username"] = ''
                data["password"] = ''
                data["certificate_path"] = ''
                data["key_file_path"] = ''
                data["key_password"] = ''
                data["tenable_sc_access_key"] = ''
                data["tenable_sc_secret_key"] = ''
                return True
        else:
            return True


class TenableOT(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(TenableOT, self).__init__()
        self._args = args
        self._kwargs = kwargs
        self.path = os.path.abspath(__file__)
        self.util = Utility()

    def validate(self, value, data):
        if data.get("tenable_account_type") == "tenable_ot_security_icp":
            try:
                logger.info("Tenable OT: Validating account details.")
                app_name = self.path.split(
                    '/')[-3] if '/' in self.path else self.path.split('\\')[-3]
                use_ca_cert = data.get("use_ca_cert")
                verify_ssl = tenable_consts.verify_ssl_for_ot
                if verify_ssl and is_true(use_ca_cert):
                    custom_certificate = data.get("custom_certificate", "").strip()
                    cert_file_loc = verify_ssl = get_ssl_and_save_cert_file(custom_certificate, data.get("name"))
                tot = TOT(
                    api_key=data.get("api_secret"),
                    url="https://" + data.get("address").strip('/'),
                    proxies=self.util.get_proxy(data),
                    ssl_verify=verify_ssl,
                    vendor='Tenable',
                    product='SplunkTA',
                    build=get_app_version(app_name)
                )
                resp = tot.graphql(query='''query getVersion { systemInfo { version { version } } }''')  # noqa: F841
            except Exception as err:
                if is_true(data.get("use_ca_cert")) and data.get("custom_certificate") and os.path.exists(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name"))):
                    os.remove(tenable_consts.CUSTOM_CERT_FILE_LOC.format(data.get("name")))
                msg = "Please enter valid Address, API Secret or configure valid proxy settings or check SSL Certificate."
                self.put_msg(msg)
                logger.error("Tenable OT: Error occured while validating account. " + msg + " Error: {}".format(str(err)))
                return False

            else:
                logger.info("Tenable OT: Account validated successfully.")
                data["username"] = ''
                data["password"] = ''
                data["certificate_path"] = ''
                data["key_file_path"] = ''
                data["key_password"] = ''
                data["tenable_sc_access_key"] = ''
                data["tenable_sc_secret_key"] = ''
                data["access_key"] = ''
                data["secret_key"] = ''
                return True
        else:
            return True


class TenableEASM(Validator):
    def __init__(self, *args, **kwargs):
        """

        :param validator: user-defined validating function
        """
        super(TenableEASM, self).__init__()
        self._args = args
        self._kwargs = kwargs
        self.path = os.path.abspath(__file__)
        self.util = Utility()

    def validate(self, value, data):
        if data.get("tenable_account_type") == "tenable_asm":
            try:
                logger.info("Tenable ASM: Validating account details.")
                try:
                    tasm = TenableASM(api_key=data.get("tenable_easm_api_key"), proxies=self.util.get_proxy(data), url="https://{}".format(data.get("tenable_easm_domain").strip().strip('/')))
                    tasm_sf_list = tasm.smart_folders.list()
                except Exception as e:
                    msg = "Please enter valid Domain and Key or configure valid proxy settings."
                    raise Exception(msg)
            except Exception as exc:
                logger.error("Tenable ASM: Error occured while validating account. Error: {}".format(exc))
                self.put_msg(exc)
                return False
            else:
                logger.info("Tenable ASM: Account validated successfully.")
                data["username"] = ''
                data["password"] = ''
                data["certificate_path"] = ''
                data["key_file_path"] = ''
                data["key_password"] = ''
                data["tenable_sc_access_key"] = ''
                data["tenable_sc_secret_key"] = ''
                return True
        else:
            return True