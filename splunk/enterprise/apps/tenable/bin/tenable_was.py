import import_declare_test  # noqa: F401
import sys
from tenable_validations import *  # noqa: F403
from io_collector import IOCollector
from tenable_utility import get_credentials
from splunklib import modularinput as smi
from setup_logger import setup_logging
logger = setup_logging("ta_tenable_tenable_was")

class TENABLE_WAS(smi.Script):
    def __init__(self):
        super(TENABLE_WAS, self).__init__()

    def get_scheme(self):
        scheme = smi.Scheme('tenable_was')
        scheme.description = 'WAS Assets & Vulns'
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
                'lowest_severity_to_store',
                required_on_create=True,
            )
        )
        scheme.add_argument(
            smi.Argument(
                'fixed_vulnerability',
                required_on_create=False,
            )
        )
        return scheme

    def validate_input(self, definition: smi.ValidationDefinition):
        global_account_name = definition.parameters.get('global_account')
        _, account_stanza = get_credentials(definition.metadata['session_key'], global_account_name)
        tenable_account_type = account_stanza.get("tenable_account_type")
        if tenable_account_type != "tenable_io":
            raise ValueError("Please select the correct account.")

        validate_io_interval(definition.parameters.get("interval"))  # noqa: F405
        validate_start_time(definition.parameters.get("start_time"))  # noqa: F405
        validate_lowest_severity(definition.parameters.get("lowest_severity_to_store"))  # noqa: F405

        validate_fixed_vulnerability(  # noqa: F405
            definition.parameters.get("fixed_vulnerability"))

        max_event_size = definition.parameters.get("max_event_size")
        validate_max_event_size(max_event_size)  # noqa: F405

        vuln_num_assets = definition.parameters.get("vuln_num_assets")
        validate_vuln_num_assets(vuln_num_assets)  # noqa: F405
        assets_chunk_size = definition.parameters.get("assets_chunk_size")
        validate_assets_chunk_size(assets_chunk_size)  # noqa: F405
        vulns_indexed_buffer_interval = definition.parameters.get("vulns_indexed_buffer_interval")
        validate_vulns_indexed_time_sync_interval(vulns_indexed_buffer_interval)  # noqa: F405
        assets_buffer_interval = definition.parameters.get("assets_buffer_interval")
        validate_assets_buffer_interval(assets_buffer_interval)  # noqa: F405

    def stream_events(self, inputs: smi.InputDefinition, ew: smi.EventWriter):
        input_items = [{'count': len(inputs.inputs)}]
        for input_name, input_item in inputs.inputs.items():
            input_item['name'] = input_name
            input_items.append(input_item)
        input_name = input_items[1]['name']
        meta_configs = self._input_definition.metadata
        session_key = meta_configs['session_key']

        ingester = IOCollector(logger, ew, input_items[1], session_key)
        ingester.collect_events(collect_was_data=True)


if __name__ == '__main__':
    exit_code = TENABLE_WAS().run(sys.argv)
    sys.exit(exit_code)
