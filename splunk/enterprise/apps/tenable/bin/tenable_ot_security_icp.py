import import_declare_test  # noqa: F401
import sys
from ot_collector import OTCollector
from tenable_validations import *  # noqa: F403
from tenable_utility import get_credentials
from splunklib import modularinput as smi
from setup_logger import setup_logging
logger = setup_logging("ta_tenable_tenable_ot_security_icp")

class TENABLE_OT_SECURITY_ICP(smi.Script):
    def __init__(self):
        super(TENABLE_OT_SECURITY_ICP, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('tenable_ot_security_icp')
        scheme.description = 'TOT (ICP) Assets & Vulns'
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
        return scheme

    def validate_input(self, definition: smi.ValidationDefinition):
        global_account_name = definition.parameters.get('global_account')
        _, account_stanza = get_credentials(definition.metadata['session_key'], global_account_name)
        tenable_account_type = account_stanza.get("tenable_account_type")
        if tenable_account_type != "tenable_ot_security_icp":
            raise ValueError("Please select the correct account.")
        validate_start_time(definition.parameters.get("start_time"))  # noqa: F405

    def stream_events(self, inputs: smi.InputDefinition, ew: smi.EventWriter):
        input_items = [{'count': len(inputs.inputs)}]
        for input_name, input_item in inputs.inputs.items():
            input_item['name'] = input_name
            input_items.append(input_item)
        input_name = input_items[1]['name']
        meta_configs = self._input_definition.metadata
        session_key = meta_configs['session_key']
        ingester = OTCollector(logger, ew, input_items[1], session_key)
        ingester.collect_events()


if __name__ == '__main__':
    exit_code = TENABLE_OT_SECURITY_ICP().run(sys.argv)
    sys.exit(exit_code)
