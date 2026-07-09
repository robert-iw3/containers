import os
import re
import json
import splunk.rest as rest
import splunk.entity as entity
import tenable_utility as utility
from splunk.clilib.bundle_paths import make_splunkhome_path


def get_certs_path(app_name, certificate_path, key_file_path):
    """Returns complete certificate and key file path using base path as splunk home path

    Args:
        app_name (str): app package name
        certificate_path (str): provided certificate path
        key_file_path (str): provide key file path

    Returns:
        str, str: absolute certificate path and key file path
    """
    cert_base_path = os.path.join(
        make_splunkhome_path(["etc", "apps", app_name, "certs"]))
    certificate_path_list = str(certificate_path).split(
        "/") if "/" in certificate_path else str(certificate_path).split("\\")
    certificate_path = cert_base_path
    for path in certificate_path_list:
        certificate_path = os.path.join(certificate_path, path)

    key_path_list = str(key_file_path).split(
        "/") if "/" in key_file_path else str(key_file_path).split("\\")
    key_file_path = cert_base_path
    for path in key_path_list:
        key_file_path = os.path.join(key_file_path, path)

    return certificate_path, key_file_path


def get_passwords(name, app_name, session_key):
    """Gets password dict with the given name from splunk

    Args:
        name (str): name of the password entry
        app_name (str): app package name
        session_key (str): splunk session key

    Returns:
        dict: credentials dict
    """
    entities = entity.getEntities(["admin", "passwords"],
                                  namespace=app_name,
                                  owner="nobody",
                                  sessionKey=session_key,
                                  search=app_name)
    for _, value in entities.items():
        if value["username"].partition("`")[0] == str(name) and not value.get(
                "clear_password", "`").startswith("`"):
            cred = json.loads(value.get("clear_password", "{}"))
            return cred
    return {}


def get_api_keys(name, app_name, session_key):
    """Gets Tenable.sc access key and secret key dict with the given name from Splunk

    Args:
        name (str): name of the password entry
        app_name (str): app package name
        session_key (str): Splunk session key

    Returns:
        dict: Tenable.sc keys dict
    """

    entities = entity.getEntities(["admin", "passwords"],
                                  namespace=app_name,
                                  owner="nobody",
                                  sessionKey=session_key,
                                  search=app_name)
    sc_access_key = utility.get_decrypted_sc_keys(
        "tenable_securitycenter_api_keys",
        entities,
        name,
        "tenable_sc_access_key",
    )
    sc_secret_key = utility.get_decrypted_sc_keys(
        "tenable_securitycenter_api_keys",
        entities,
        name,
        "tenable_sc_secret_key",
    )
    return {"sc_access_key": sc_access_key, "sc_secret_key": sc_secret_key}


def validate_ip(ip):
    """Validates passed IP address using regex for ipv4 and ipv6 format

    Args:
        ip (str): IP address

    Returns:
        bool: if valid IP is given returns True else will return False
    """
    valid_ip4 = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
    valid_ip6 = "^((([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:)\
        {1,4}(:[0-9a-fA-F]\
        {1,4}){1,3}|([0-9a-fA-F]{1,4}:)\
        {1,3}(:[0-9a-fA-F]\
        {1,4}){1,4}|([0-9a-fA-F]{1,4}:)\
        {1,2}(:[0-9a-fA-F]\
        {1,4}){1,5}|[0-9a-fA-F]\
        {1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4})\
        {0,4}%[0-9a-zA-Z]\
        {1,}|::(ffff(:0{1,4})\
        {0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9])\
        {0,1}[0-9])|([0-9a-fA-F]{1,4}:)\
        {1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.)\
        {3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9])\
        {0,1}[0-9])))$"

    if not re.match(valid_ip4, str(ip)) and not re.match(valid_ip6, str(ip)):
        return False
    return True


def get_ar_index(session_key):
    """Gets the ar_index set in app settings conf required to index response from
    performed AR action

    Args:
        session_key (str): Splunk session key

    Returns:
        str: AR Index
    """
    ar_index = "main"
    _, content = rest.simpleRequest(
        "/servicesNS/nobody/TA-tenable/configs/conf-ta_tenable_settings",
        sessionKey=session_key,
        getargs={"output_mode": "json"},
        raiseAllErrors=True)
    settings_data = json.loads(content)["entry"]
    for i in range(len(settings_data)):
        data = settings_data[i].get("content")
        if data.get("ar_index"):
            return data.get("ar_index")
    return ar_index

def handle_error(logger, ar_type, message, err_str=""):
        """Formats error messages for indexing it into splunk

        Args:
            helper (object): object of ModularAlertBase
            ar_type (str): for example: 'SC' or 'IO'
            message (str): Custom error message to add in event
            err_str (str): specific error string

        Returns:
            dict: formatted error and error message kv-pair
        """
        logger.error("Tenable {} Error: {} {}".format(ar_type, err_str, message))
        data = {"message": str(message), "error": str(err_str)}
        return data
