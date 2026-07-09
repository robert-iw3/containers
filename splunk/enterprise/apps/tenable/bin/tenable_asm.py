import import_declare_test  # noqa: F401
import sys
import traceback
from tenable_validations import *  # noqa: F403
from solnlib import conf_manager
from tenable_utility import get_credentials
from splunklib import modularinput as smi
import tenable_consts
import tenable_utility as utility
from setup_logger import setup_logging
from asm_processor import TASM_Event_Proccessor

logger = setup_logging("ta_tenable_tenable_asm")

class TENABLE_EASM(smi.Script):
    def __init__(self):
        super(TENABLE_EASM, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('tenable_asm')
        scheme.description = 'TASM'
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
        if tenable_account_type != "tenable_asm":
            raise ValueError("Please select the correct account.")

    def stream_events(self, inputs: smi.InputDefinition, ew: smi.EventWriter):
        input_items = [{'count': len(inputs.inputs)}]
        for input_name, input_item in inputs.inputs.items():
            input_item['name'] = input_name
            input_items.append(input_item)
        input_name = input_items[1]['name']
        meta_configs = self._input_definition.metadata
        session_key = meta_configs['session_key']
        tasm = TASM_Event_Proccessor(logger, ew, input_items[1], session_key)
        tasm.create_events()

if __name__ == '__main__':
    exit_code = TENABLE_EASM().run(sys.argv)
    sys.exit(exit_code)
