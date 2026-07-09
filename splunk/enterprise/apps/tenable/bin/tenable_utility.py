import import_declare_test
import io
import os
import json
import sys
import requests
from solnlib import conf_manager
from typing import Tuple, Union
from six.moves.configparser import ConfigParser
from solnlib.conf_manager import ConfManager
import splunk.rest as rest
from splunk.clilib.bundle_paths import make_splunkhome_path
import tenable_consts
import traceback

def get_app_version(my_app: str) -> str:
    config, stanza = get_configuration(my_app, 'app.conf', folder='default')
    return '{}-b{}'.format(
        config.get('launcher', 'version'),
        config.get('install', 'build')
    )

def get_configuration(my_app: str, file:str, folder: str="local") -> Tuple:
    conf_parser = ConfigParser()
    conf = os.path.join(make_splunkhome_path(
        ["etc", "apps", my_app, folder, file]))
    stanzas = []
    if os.path.isfile(conf):
        with io.open(conf, 'r', encoding='utf_8_sig') as conffp:
            conf_parser.readfp(conffp)
        stanzas = conf_parser.sections()
    return conf_parser, stanzas


def get_certificate_path(my_app: str, cert_path: str, key_path: str) -> Tuple:
    base_path = os.path.join(make_splunkhome_path(
        ["etc", "apps", my_app, "certs"]))
    certificate_path_list = cert_path.split(
        '/') if '/' in cert_path else cert_path.split('\\')
    certificate_path = base_path
    for path in certificate_path_list:
        certificate_path = os.path.join(certificate_path, path)
    if not os.path.exists(certificate_path):
        msg = "Certificate Path: {} not found.".format(certificate_path)
        raise Exception(msg)

    key_path_list = key_path.split(
        '/') if '/' in key_path else key_path.split('\\')
    key_file_path = base_path
    for path in key_path_list:
        key_file_path = os.path.join(key_file_path, path)
    if not os.path.exists(key_file_path):
        msg = "Key File Path: {} not found.".format(key_file_path)
        raise Exception(msg)

    return certificate_path, key_file_path


def get_decrypted_sc_keys(tenable_app:str, entities: dict, name:str, field_name:str) -> str:
    '''
    Give decrypted sc keys
    :param entities: dict which will have clear password
    :param name: name of modular input
    :return: access key and secret key password
    '''
    password = ''
    for _, value in entities.items():
        if value['username'].partition('`')[0] == str(name) and not value.get('clear_password', '`').startswith('`'):
            cred = json.loads(value.get('clear_password', '{}'))
            password = cred.get(field_name, '')
            break
    return password


def get_password(tenable_app:str, entities:dict, name: str) -> str:
    '''
    Give password
    :param entities: dict which will have clear password
    :param name: name of modular input
    :return: password and certificate key password
    '''
    password = ''
    for _, value in entities.items():
        if value['username'].partition('`')[0] == str(name) and not value.get('clear_password', '`').startswith('`'):
            cred = json.loads(value.get('clear_password', '{}'))
            password = cred.get('password', '') if tenable_app == 'tenable_securitycenter_credentials' else cred.get(
                'key_password', '')
            break
    return password


def is_true(val) -> bool:

    value = str(val).strip().upper()
    if val is None:
        return False
    if value in ["1", "TRUE", "T", "Y", "YES"]:
        return True
    return False


def create_uri(proxy_enabled: str, global_account_dict: dict) -> Union[str, None]:

    uri = None
    if is_true(proxy_enabled) and global_account_dict.get('proxy_url') and global_account_dict.get('proxy_type'):
        uri = global_account_dict['proxy_url']
        if global_account_dict.get('proxy_port'):
            uri = '{}:{}'.format(uri, global_account_dict.get('proxy_port'))
        if global_account_dict.get("proxy_username") and global_account_dict.get(
            "proxy_password"
        ):
            uri = "{}://{}:{}@{}/".format(
                global_account_dict["proxy_type"],
                requests.compat.quote_plus(global_account_dict["proxy_username"]),
                requests.compat.quote_plus(global_account_dict["proxy_password"]), uri,
            )
        else:
            uri = '{}://{}'.format(global_account_dict['proxy_type'], uri)
    return uri


def get_proxy_settings(session_key: Union[str,None]=None,
                        global_account_dict: Union[dict,None]=None,
                        global_account_name: Union[str,None]=None,
                        app: Union[str,None]=None,
                        entities: Union[dict,None]=None,
                        ) -> dict:
    '''
    Give proxy uri
    :param global_account_dict: global account dictionary
    :param global_account_name: global account name
    :param app: name of app
    :param entities: dict which will have clear password
    :return: proxy settings
    '''
    proxies = {}
    if global_account_name and app and not global_account_dict:
        _, global_account_dict = get_credentials(session_key, global_account_name)

    if not global_account_dict:
        return proxies

    if global_account_dict.get('proxy_username') and entities:
        for _, value in entities.items():
            if value['username'].partition('`')[0] == global_account_name and not value.get('clear_password', '`').startswith('`'):
                cred = json.loads(value.get('clear_password', '{}'))
                global_account_dict['proxy_password'] = cred.get(
                    'proxy_password', '')
                break

    proxy_enabled = global_account_dict.get('proxy_enabled', False)

    uri = create_uri(proxy_enabled, global_account_dict)

    if uri:
        proxies = {
            'http': uri,
            'https': uri
        }
    return proxies


def set_proxy_attributes(account_config:ConfigParser, account_dict: dict, stanza: str) -> None:

    if account_config.has_option(stanza, "proxy_enabled"):
        account_dict["proxy_enabled"] = account_config.get(
            stanza, 'proxy_enabled')
    if account_config.has_option(stanza, "proxy_type"):
        account_dict["proxy_type"] = account_config.get(stanza, 'proxy_type')
    if account_config.has_option(stanza, "proxy_url"):
        account_dict["proxy_url"] = account_config.get(stanza, 'proxy_url')
    if account_config.has_option(stanza, "proxy_port"):
        account_dict["proxy_port"] = account_config.get(stanza, 'proxy_port')
    if account_config.has_option(stanza, "proxy_username"):
        account_dict["proxy_username"] = account_config.get(
            stanza, 'proxy_username')


def get_account_data(global_account: str, my_app: str) -> Tuple:

    account_config, account_stanzas = get_configuration(
        my_app, "ta_tenable_account.conf")
    account_dict = {}

    for stanza in account_stanzas:
        if str(stanza) == global_account:
            account_dict["address"] = account_config.get(stanza, 'address')
            account_dict["tenable_account_type"] = account_config.get(
                stanza, 'tenable_account_type')

            set_proxy_attributes(account_config, account_dict, stanza)

            if account_dict["tenable_account_type"] == "tenable_securitycenter_credentials":
                account_dict["username"] = account_config.get(
                    stanza, 'username')
            elif account_dict["tenable_account_type"] == "tenable_securitycenter_certificate":
                account_dict["certificate_path"] = account_config.get(
                    stanza, 'certificate_path')
                account_dict["key_file_path"] = account_config.get(
                    stanza, 'key_file_path')

    return account_config, account_dict


def get_kvstore_status(session_key: str) -> str:
    #TODO.  Why are we doing this here and in tenable_collector
    _, content = rest.simpleRequest("/services/kvstore/status", sessionKey=session_key,
                                    method="GET", getargs={"output_mode": "json"}, raiseAllErrors=True)
    data = json.loads(content)['entry']
    return data[0]["content"]["current"].get("status")

def get_host_port(data_address: str) -> list:
        address = data_address.strip('/')
        address_array = address.split(":")
        host = ''
        for i in range(len(address_array) - 1):
            host = host + address_array[i] + ":"
        host = host.strip(":")
        if(address_array[-1].isdigit()):
            port = address_array[-1]
            complete_address = host + ":" + port
        else:
            port = 443
            host = host + address_array[-1]
            complete_address = host + ":" + str(port)

        return [host, port, complete_address]

def read_conf_file(session_key: str,
                    app_name: str,
                    conf_fname:str,
                    stanza:Union[str, None]=None
                ) -> dict:
    """
    Get conf file content with conf_manager.

    :param session_key: Splunk session key
    :param conf_file: conf file name
    :param stanza: If stanza name is present then return only that stanza,
                    otherwise return all stanza
    """
    conf_file = ConfManager(
        session_key,
        app_name,
        realm="__REST_CREDENTIAL__#{}#configs/conf-{}".format(app_name, conf_fname),
    ).get_conf(conf_fname)

    if stanza:
        return conf_file.get(stanza)
    return conf_file.get_all(only_current_app=True)

def save_cert_file(custom_certificate, cert_file_loc, logger):
    """Save the certificate file."""
    logger.info("Custom CA Certificate has been provided.")

    # Ensure the directory exists
    cert_dir = os.path.dirname(cert_file_loc)
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir, exist_ok=True)
        logger.info("Created directory for custom CA Certificate at {}.".format(cert_dir))

    # Write the certificate file
    with open(cert_file_loc, 'w') as f:
        f.write(custom_certificate)

    verify_ssl = cert_file_loc
    logger.info("Custom CA Certificate has been copied at {}.".format(cert_file_loc))
    return verify_ssl

def get_credentials(session_key, account_name):
    """Provide credentials of the configured account.

    Args:
        session_key: current session session key
        logger: log object

    Returns:
        Dict: A Dictionary having account information.
    """
    try:
        cfm = conf_manager.ConfManager(
            session_key,
            import_declare_test.ta_name,
            realm="__REST_CREDENTIAL__#{}#configs/conf-{}".format(
                import_declare_test.ta_name, tenable_consts.ta_accounts_conf
            ),
        )
        account_conf_file = cfm.get_conf(tenable_consts.ta_accounts_conf)
        account_info_json = account_conf_file.get(account_name) if account_name else None
    except Exception:
        sys.exit(1)
    return account_conf_file, account_info_json