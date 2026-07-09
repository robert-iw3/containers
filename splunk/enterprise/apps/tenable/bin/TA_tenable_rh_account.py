
import import_declare_test  # noqa: F401
import os

from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    SingleModel,
)
from tenable_account_validation import *  # noqa: F403
from tenable_utility import read_conf_file
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.splunk_aoblib.rest_migration import ConfigMigrationHandler
import logging

util.remove_http_proxy_env_vars()


class AccountModel(SingleModel):
    def validate(self, name, data, existing=None):
        data_to_validate = data.copy()
        data_to_validate['name'] = name
        super(AccountModel, self).validate(name, data_to_validate, existing)


fields = [
    field.RestField(
        'tenable_account_type',
        required=True,
        encrypted=False,
        default='tenable_io',
        validator=TenableAccountType()  # noqa: F405
    ),
    field.RestField(
        'address',
        required=False,
        encrypted=False,
        default='cloud.tenable.com',
        validator=Address()  # noqa: F405
    ),
    field.RestField(
        'access_key',
        required=False,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=1,
        )
    ),
    field.RestField(
        'secret_key',
        required=False,
        encrypted=True,
        default=None,
        validator=TenableIO()  # noqa: F405
    ),
    field.RestField(
        'tenable_sc_access_key',
        required=False,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=1,
        )
    ),
    field.RestField(
        'tenable_sc_secret_key',
        required=False,
        encrypted=True,
        default=None,
        validator=ScAPIKeys()  # noqa: F405
    ),
    field.RestField(
        'username',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=200,
            min_len=1,
        )
    ),
    field.RestField(
        'password',
        required=False,
        encrypted=True,
        default=None,
        validator=Credentials()  # noqa: F405
    ),
    field.RestField(
        'certificate_path',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=500,
            min_len=1,
        )
    ),
    field.RestField(
        'key_file_path',
        required=False,
        encrypted=False,
        default=None,
        validator=Certificate()  # noqa: F405
    ),
    field.RestField(
        'key_password',
        required=False,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=1,
        )
    ),
    field.RestField(
        'api_secret',
        required=False,
        encrypted=True,
        default=None,
        validator=TenableOT()  # noqa: F405
    ),
    field.RestField(
        'tenable_easm_domain',
        required=False,
        encrypted=False,
        default='asm.cloud.tenable.com',
        validator=validator.String(
            max_len=8192,
            min_len=0,
        )
    ),
    field.RestField(
        'tenable_easm_api_key',
        required=False,
        encrypted=True,
        default=None,
        validator=TenableEASM()
    ),
    field.RestField(
        "use_ca_cert",
        required=False,
        encrypted=False,
        default=False,
        validator=None,
    ),
    field.RestField(
        "custom_certificate",
        required=False,
        encrypted=False,
        default="",
        validator=None,
    ),
    field.RestField(
        'proxy_enabled',
        required=False,
        encrypted=False,
        default=0,
        validator=Proxy()  # noqa: F405
    ),
    field.RestField(
        'proxy_type',
        required=False,
        encrypted=False,
        default='http',
        validator=None
    ),
    field.RestField(
        'proxy_url',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=4096,
            min_len=0,
        )
    ),
    field.RestField(
        'proxy_port',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Number(
            max_val=65535,
            min_val=1,
        )
    ),
    field.RestField(
        'proxy_username',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=50,
            min_len=0,
        )
    ),
    field.RestField(
        'proxy_password',
        required=False,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=0,
        )
    )
]
model = RestModel(fields, name=None)


endpoint = AccountModel(
    'ta_tenable_account',
    model,
    config_name='account'
)

class AccountHandler(ConfigMigrationHandler):
    """Account Handler."""

    def handleCreate(self, confInfo):
        """Handle creation of account in config file."""
        super(AccountHandler, self).handleCreate(confInfo)

    def handleRemove(self, confInfo):
        """Handle the delete operation."""
        session_key = GetSessionKey().session_key  # noqa: F405
        path = os.path.abspath(__file__)
        app_name = path.split('/')[-3] if '/' in path else path.split('\\')[-3]
        inputs_file = read_conf_file(session_key, app_name, "inputs")
        created_inputs = list(inputs_file.keys())
        input_list = []
        for each in created_inputs:
            each_tenable_input = each.split("://")
            configured_account = inputs_file.get(each).get("global_account")
            if configured_account == self.callerArgs.id:
                input_list.append(each_tenable_input[1])
        if len(input_list) > 0:
            raise admin.ArgValidationException(  # noqa: F405
                "Account '{}' will not be deleted because it is linked with the"
                " following inputs: {}".format(self.callerArgs.id, ", ".join(input_list))
            )
        else:
            super(ConfigMigrationHandler, self).handleRemove(confInfo)

if __name__ == '__main__':
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AccountHandler,
    )
