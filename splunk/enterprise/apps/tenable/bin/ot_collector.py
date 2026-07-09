import arrow
from tenable.ot.exports.api import OTExportsIterator
import tenable_consts
from tenable_utility import is_true
from typing import Tuple
from tenable_collector import TenableCollector
from tenable.ot.session import TenableOT

class OTCollector(TenableCollector):
    """
    The purpose of OTCollector is to fetch the asset and plugin events from tenable ot,
    and index them into splunk.
    """

    PRODUCT = 'TOT'

    def _set_input_data(self) -> None:
        """Set Tenable OT input form fields and initialize tio object.
        """
        super(OTCollector, self)._set_input_data()
        self.check_point_name = self.input_name
        self.get_checkpoint()
        try:
            verify_ssl = tenable_consts.verify_ssl_for_ot
            custom_cert = is_true(self._account.get('use_ca_cert'))
            if custom_cert:
                verify_ssl = tenable_consts.CUSTOM_CERT_FILE_LOC.format(self.get_argus.get("global_account"))

            self.tot = TenableOT(
                api_key=self._account['api_secret'],
                url="https://" + self._account["address"].strip("/"),
                proxies=self.proxies,
                vendor='Tenable',
                product='SplunkTA',
                build=self.build,
                ssl_verify=verify_ssl
            )

        except Exception as e:
            msg = f'Couldnt initialize Tenable OT ICP connection: {e}'
            self.log_error(f'message={msg}')
            raise Exception(msg)

    def basic_event_transformer(self, event: dict) -> dict:
        """
        Add standard content to events
        """
        return {
            'OT_address': self._account["address"].strip("/")
        }

    def vuln_event_transformer(self, event: dict, time_field: str) -> Tuple:
        """
        Tranform vulnerability events
        Args:
            event (dict): event data to be transformed
            time_field: the time field in the event to use to create event_time if applicable
        Returns:
            Tuple(dict, int)
        """
        event.update(self.basic_event_transformer(event))

        return event, arrow.utcnow().int_timestamp

    def asset_event_transformer(self, event: dict, time_field: str) -> Tuple:
        """
        Tranform asset events
        Args:
            event (dict): event data to be transformed
            time_field: the time field in the event to use to create event_time if applicable
        Returns:
            Tuple(dict, int)
        """
        new_event = event.pop('details', {})
        new_event.update(self.basic_event_transformer(new_event))
        event_time = new_event.get(time_field, arrow.utcnow().int_timestamp)
        return new_event, arrow.get(event_time).int_timestamp

    def plugin_event_transformer(self, event: dict, time_field: str) -> tuple:
        """
        Tranform plugin events
        Args:
            event (dict): event data to be transformed
            time_field: the time field in the event to use to create event_time if applicable
        Returns:
            Tuple(dict, int)
        """
        updates = self.basic_event_transformer(event)
        if event.get('source') is not None:
            updates['pluginSource'] = event.pop('source')
        event.update(updates)

        return event, arrow.utcnow().int_timestamp

    def process_vulns(self) -> None:
        """
        Process all vulnerabilities
        """
        job = {
            'state': 'all',
            'export_type': 'vulns',
            'time_field': 'last_seen',
            'check_point_time_field': 'vulns_last_seen',
            'sourcetype': 'tenable:ot:vuln',
            'transform_func': self.vuln_event_transformer
        }
        job['iterator'] = self.tot.exports.findings()
        self._process_job(**job)

    def process_plugins(self) -> None:
        """
        Process all plugins
        """
        job = {
            'state': 'all',
            'export_type': 'plugins',
            'time_field': 'last_update',
            'check_point_time_field': 'plugins_last_update',
            'sourcetype': 'tenable:ot:plugin',
            'transform_func': self.plugin_event_transformer,
        }
        job['iterator'] = self.tot.exports.plugins()
        self._process_job(**job)

    def process_assets(self) -> None:
        """
        Process all assets
        """
        job = {
            'state': 'all',
            'export_type': 'assets',
            'time_field': 'lastUpdate',
            'check_point_time_field': 'assets_lastUpdate',
            'sourcetype': 'tenable:ot:assets',
            'transform_func': self.asset_event_transformer,
        }
        job['iterator'] = self._query_assets(**job)
        self._process_job(**job)

    def _query_assets(self, check_point_time_field: str, **kwargs) -> OTExportsIterator:
        """
        Seperate out some asset collection logic for easier readability
        Args:
            check_point_time_field (str): field that we store asset checkpoint time under
        """

        if self.check_point.get(check_point_time_field) is not None:
            since = self.check_point.get(check_point_time_field)
        else:
            since = self.start_time
        filter = [
            {
                'op': 'Equal',
                'field': 'hidden',
                'values': 'false'
            },{
                'field': 'lastUpdate',
                'op': 'Greater',
                'values': arrow.get(since).isoformat()
            }
        ]
        sort = [
            {
                'field': 'lastUpdate',
                'direction': 'AscNullFirst'
            }
        ]
        return self.tot.exports.assets(filters=filter, sort=sort)

    def collect_events(self):
        """
        Collect TOT data
        """
        self.log_info('action=started process=data_collection')
        self.process_vulns()
        self.process_assets()
        self.process_plugins()
        self.log_info('action=completed process=data_collection')
