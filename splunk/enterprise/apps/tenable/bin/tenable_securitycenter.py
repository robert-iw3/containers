import import_declare_test  # noqa: F401
import sys
from splunklib import modularinput as smi

from tenable_validations import *  # noqa: F403
from sc_collector import SCCollector
import tenable_consts

import splunk.entity as entity
import tenable_utility as utility

from tenable.sc import TenableSC as TSC
from custom_http_adapter import CustomHTTPAdapter
from setup_logger import setup_logging
logger = setup_logging("ta_tenable_tenable_securitycenter")

class TENABLE_SECURITYCENTER(smi.Script):
    def __init__(self):
        super(TENABLE_SECURITYCENTER, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('tenable_securitycenter')
        scheme.description = 'TSC Assets & Vulns'
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False

        scheme.add_argument(
            smi.Argument(
                'name',
                title='Name',
                description='Name',
                required_on_create=True
            )
        )
        scheme.add_argument(
            smi.Argument(
                'global_account',
                required_on_create=True,
            )
        )
        scheme.add_argument(
            smi.Argument(
                'start_time',
                required_on_create=False,
            )
        )
        scheme.add_argument(
            smi.Argument(
                'sync_plugins',
                required_on_create=False,
            )
        )
        scheme.add_argument(
            smi.Argument(
                'fixed_vulnerability',
                required_on_create=False,
            )
        )
        scheme.add_argument(
            smi.Argument(
                'query_name',
                required_on_create=False,
            )
        )
        return scheme

    def validate_input(self, definition: smi.ValidationDefinition):
        session_key = definition.metadata["session_key"]
        name = definition.metadata["name"]
        app_name = 'TA-tenable'
        global_account_name = definition.parameters.get("global_account")
        sync_plugins = definition.parameters.get("sync_plugins")
        query_name = definition.parameters.get("query_name")

        account_conf, account_stanza = utility.get_credentials(session_key, global_account_name)
        tenable_account_type = account_stanza.get("tenable_account_type")
        if tenable_account_type not in [
            "tenable_securitycenter_credentials",
            "tenable_securitycenter_certificate",
            "tenable_securitycenter_api_keys"
        ]:
            raise ValueError("Please select the correct account.")

        input_parser_obj, input_stanzas = utility.get_configuration(app_name, "inputs.conf")
        validate_sync_plugins(  # noqa: F405
            sync_plugins,
            "tenable_securitycenter://",
            account_conf,
            account_stanza,
            input_parser_obj,
            input_stanzas,
            name,
        )

        verify_ssl_certificate = False
        if tenable_account_type == "tenable_securitycenter_credentials":
            verify_ssl_certificate = tenable_consts.verify_ssl_for_sc_creds
        elif tenable_account_type == "tenable_securitycenter_certificate":
            verify_ssl_certificate = tenable_consts.verify_ssl_for_sc_cert
        elif tenable_account_type == "tenable_securitycenter_api_keys":
            verify_ssl_certificate = tenable_consts.verify_ssl_for_sc_api_key

        if verify_ssl_certificate and utility.is_true(account_stanza.get("use_ca_cert")):
            verify_ssl_certificate = tenable_consts.CUSTOM_CERT_FILE_LOC.format(global_account_name)

        validate_sc_interval(definition.parameters.get("interval"))  # noqa: F405
        validate_start_time(definition.parameters.get("start_time"))  # noqa: F405

        entities = entity.getEntities(
            ["admin", "passwords"],
            namespace=app_name,
            owner="nobody",
            sessionKey=session_key,
            search=app_name,
        )
        proxies = utility.get_proxy_settings(
            session_key=session_key, global_account_name=global_account_name, app=app_name, entities=entities
        )

        [host, port, complete_address] = utility.get_host_port(account_stanza["address"])

        if tenable_account_type == "tenable_securitycenter_api_keys":
            sc_access_key = utility.get_decrypted_sc_keys(
                account_stanza["tenable_account_type"],
                entities,
                global_account_name,
                "tenable_sc_access_key",
            )
            sc_secret_key = utility.get_decrypted_sc_keys(
                account_stanza["tenable_account_type"],
                entities,
                global_account_name,
                "tenable_sc_secret_key",
            )
            tsc = TSC(
                host = host,
                port = port,
                access_key=sc_access_key,
                secret_key=sc_secret_key,
                ssl_verify=verify_ssl_certificate,
                proxies=proxies,
            )
        elif tenable_account_type == "tenable_securitycenter_credentials":
            username = account_stanza["username"]
            password = utility.get_password(
                account_stanza["tenable_account_type"], entities, global_account_name
            )
            tsc = TSC(
                host = host,
                port = port,
                ssl_verify=verify_ssl_certificate,
                proxies=proxies,
            )
            tsc.login(username, password)
        else:
            certificate_path, key_file_path = utility.get_certificate_path(
                app_name,
                account_stanza["certificate_path"],
                account_stanza["key_file_path"],
            )
            password = utility.get_password(
                account_stanza["tenable_account_type"], entities, global_account_name
            )
            adapter = CustomHTTPAdapter(
                certfile=certificate_path, keyfile=key_file_path, password=password
            )
            sc_access_key = utility.get_decrypted_sc_keys(
                account_stanza["tenable_account_type"],
                entities,
                global_account_name,
                "tenable_sc_access_key",
            )
            sc_secret_key = utility.get_decrypted_sc_keys(
                account_stanza["tenable_account_type"],
                entities,
                global_account_name,
                "tenable_sc_secret_key",
            )
            tsc = TSC(
                host = host,
                port = port,
                access_key=sc_access_key,
                secret_key=sc_secret_key,
                ssl_verify=verify_ssl_certificate,
                proxies=proxies,
                adapter=adapter
            )

        validate_sc_query_name(query_name, tsc)  # noqa: F405

        tsc.logout()

    def stream_events(self, inputs: smi.InputDefinition, ew: smi.EventWriter):
        input_items = [{'count': len(inputs.inputs)}]
        for input_name, input_item in inputs.inputs.items():
            input_item['name'] = input_name
            input_items.append(input_item)
        meta_configs = self._input_definition.metadata
        session_key = meta_configs['session_key']

        ingester = SCCollector(logger, ew, input_items[1], session_key, analysis_type="sc_vuln")
        ingester.collect_events()


if __name__ == '__main__':
    exit_code = TENABLE_SECURITYCENTER().run(sys.argv)
    sys.exit(exit_code)
