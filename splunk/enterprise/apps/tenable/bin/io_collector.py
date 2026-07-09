import json
from typing import Tuple, Union
import arrow
from tenable_collector import TenableCollector
from tenable.io import TenableIO



TIME_PATTERN = "%Y-%m-%dT%H:%M:%S.%fZ"
ASSET_TF_DICT = {
    'terminated_at': 'Terminated',
    'deleted_at': 'Deleted',
    'updated_at': 'Active',
}


class IOCollector(TenableCollector):
    """The purpose of IOCollector is to fetch the vulnerability, asset, and plugin events from tenable io,
    transform them accordingly, and index them into splunk.
    """

    PRODUCT = 'TVM'

    def _set_input_data(self) -> None:
        """
        Set Tenable VM input form fields and initialize tio object.
        """
        #Set default class data
        super(IOCollector, self)._set_input_data()
        self.check_point_name = self.input_name
        self.get_checkpoint()

        #Set TVM unique class data
        self.vuln_num_assets = int(self.get_argus.get('vuln_num_assets')) if self.get_argus.get(
            'vuln_num_assets') else 500
        self.assets_chunk_size = int(self.get_argus.get('assets_chunk_size')) if self.get_argus.get(
            'assets_chunk_size') else 1000
        lowest_severity = self.get_argus.get("lowest_severity_to_store")
        if lowest_severity:
            self._severity = self.SEVERITIES[self.SEVERITIES.index(
                lowest_severity):]

        # we support both types tags format legacy - dictionary of key value pairs
        # and new - list of tuples of key value pairs
        #TODO THIS ALL NEEDS CLEANUP
        self._tags = self.get_argus.get("tags") if self.get_argus.get("tags") else []
        if self._tags:
            try:
                # if the new tag format is used i.e [("key1", "value1"), ...] json.loads with fail with ValueError
                self._tags = list(json.loads(self._tags).items())
                self._convert_tags()
            except ValueError:
                self._tags = eval(self._tags, {"__builtins__": None}, {})
            except Exception as e:
                self._tags = []
                self.log_error("Unexpected error occured while processing tags: {}".format(str(e)))
        #Setup connection and ensure we have the correct perms
        try:
            self._tio = TenableIO(
                access_key=self._account["access_key"],
                secret_key=self._account["secret_key"],
                url="https://" + self._account["address"].strip("/"),
                proxies=self.proxies,
                vendor='Tenable',
                product='SplunkTA',
                build=self.build
            )
        except ConnectionError as e:
            msg = (f'error occured while initializing connection: {e}')
            self.log_error(msg)
            raise Exception(msg)

        input_type = self.get_argus.get("name").split("://")[0]
        perm_level = self._tio.session.details().get('permissions')
        if input_type == "tenable_io_audit_logs" and perm_level < 64:
            msg  = (
                'The Audit Log input requires that the user we connect with is a Tenable.io '
                'Administrator. Please update the account in Tenable.io and try again.'
            )
            self.log_error(msg)
            raise Exception(msg)
        elif perm_level < 16:
            msg  = (
                'This integration requires basic user permissions at minimum. Please update the '
                'account you are using to have basic permissions and try again.'
            )
            self.log_error(msg)
            raise Exception(msg)

    def plugin_event_transformer(self,
                                    event: dict,
                                    time_filter: str
                                    ) -> Tuple:
        """
        Plugin event transformer
        """
        # for plugins we have time field under attributes key
        attrs = event.pop("attributes", {})
        event.update(attrs)
        event.update(self.basic_event_transform(event))
        # Cant use time_filter time as many plugins are super old
        return event, arrow.utcnow().int_timestamp

    def compliance_event_transformer(self,
                                        event: dict,
                                        time_filter: str
                                    ) -> Tuple:
        """
        Compliance event transformer
        """
        event.update(self.basic_event_transform(event))
        asset = event.pop("asset", {})
        updates = {
            "asset_uuid": asset.get("id"),
            "asset_name": asset.get("name", None),
            "agent_name": asset.get("agent_name", None),
            "agent_uuid": asset.get("agent_uuid", None),
            "state": event.get("state", "").lower(),
            "compliance_state": event.pop('status'),
            'output': self._check_fix_plugin_output(event.pop('actual_value', ''))
        }
        event.update(updates)

        if event.get('state') == 'fixed':
            event_time = event.get('last_fixed')
        else:
            event_time = event.get('last_observed')

        return event, arrow.get(event_time).int_timestamp

    def audit_log_event_transformer(self,
                                        event: dict,
                                        time_filter: str
                                    ) -> Tuple:
        """
        Audit Log event transformer
        """
        event.update(self.basic_event_transform(event))
        event_time = event.get('received')
        return event, arrow.get(event_time).int_timestamp

    def asset_event_transformer(self,
                                    event: dict,
                                    time_filter: str
                                    ) -> Tuple:
        """
        Asset event transformer
        """
        event.update(self.basic_event_transform(event))
        updates = {
            'state': ASSET_TF_DICT[time_filter],
            'uuid': event.pop("id", None)
        }
        event.update(updates)
        event_time = arrow.get(event.get(time_filter,
                                         self.current_time
                                         )).int_timestamp
        return event, event_time

    def was_asset_event_transformer(self,
                                    event: dict,
                                    time_filter: str
                                    ) -> Tuple:
        """
        WAS Asset event transformer
        """
        event.update(self.basic_event_transform(event))
        updates = {
            'state': ASSET_TF_DICT[time_filter],
            'uuid': event.pop("id", None)
        }
        event.update(updates)
        event_time = arrow.get(event.get("timestamps", {}).get(time_filter,
                                         self.current_time
                                         )).int_timestamp
        return event, event_time

    def vuln_event_transformer(self, event: dict,
                                    time_filter:str
                                    ) -> Tuple:
        """
        Vuln event transformer
        """
        event.update(self.basic_event_transform(event))
        # process the event
        asset = event.pop("asset", {})
        if event.get("source"):
            event["finding_source"] = event.pop("source")
        updates = {
            "asset_uuid": asset.get("uuid"),
            "asset_fqdn": asset.get("fqdn"),
            "asset_hostname": asset.get("hostname"),
            "agent_uuid": asset.get("agent_uuid"),
            "ipv4": asset.get("ipv4"),
            "ipv6": asset.get("ipv6"),
            "vendor_severity": event.get("severity", ""),
            "state": event.get("state", "").lower(),
            "indexed_at": event.get("indexed_at") or event.pop("indexed", ""),
            'severity': self.SEVERITY_ID_MAP[int(event.get('severity_id', 0))]
        }
        event.update(updates)
        if event.get('state') == 'fixed':
            event_time = event.get('last_fixed')
        else:
            event_time = event.get("last_found")

        event['output'] = self._check_fix_plugin_output(event.pop('output', ''))
        return event, arrow.get(event_time).int_timestamp

    def basic_event_transform(self, event: dict) -> dict:
        """
        Returns data we want added to every event
        """
        return {
            'IO_address': self._account["address"]
        }

    def _convert_tags(self) -> None:
        """
        Convert the old format of tags to newer one that pytenable library accepts.
        Old format: {"tag_key1": ["tag_value1", "tag_value2"...], "tag_key2": ...}
        New format: [("key1", "value1"), ("key2", "value2"), ...]
        """
        #TODO THIS ALL NEEDS CLEANUP
        separated_tags = []
        for i in range(len(self._tags)-1, -1, -1):
            if isinstance(self._tags[i][1], list):
                tag = self._tags.pop(i)
                for j in range(len(tag[1])):
                    separated_tags.append((tag[0], tag[1][j]))

        self._tags = self._tags + separated_tags

    def _gen_check_point_time_field(self,
                                        export_type: str,
                                        time_field: str,
                                        **kwargs
                                    ) -> str:
        return f'{export_type}_{time_field}'

    def start_compliance(self) -> dict:
        """
        Start TVM Compliance export and return job
        """
        job = {
            'export_type': 'compliance',
            'state': 'all',
            'time_field': 'indexed_at',
            'check_point_time_field': 'compliance_last_run_date',
            'sourcetype': 'tenable:io:compliance',
            'func': self._tio.exports.compliance,
            'transform_func': self.compliance_event_transformer
        }
        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        job['func_params'] = {'indexed_at': self.check_point.get(job['check_point_time_field'], self.start_time)}
        job['iterator'] = self._start_job(**job)
        return job

    def start_was_vulns(self) -> dict:
        """
        Start WAS Vulns export and return job
        """
        was_vuln_states = ["OPEN", "REOPENED", "FIXED"]
        job = {
            'export_type': 'was_vulns',
            'state': 'all',
            'time_field': 'indexed_at',
            'check_point_time_field': 'was_vulns_last_run_date',
            'sourcetype': 'tenable:was:vuln',
            'func': self._tio.exports.was,
            'transform_func': self.vuln_event_transformer
        }
        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        is_first_run = False if self.check_point.get(job['check_point_time_field']) is not None else True
        self.log_debug(f'func=start_was_vulns is_first_run={is_first_run}')
        if (not self.fixed_vulnerability) and is_first_run:
            was_vuln_states.remove('FIXED')
            self.log_debug('func=start_was_vulns action=skipped process={} state=fixed reason=first_run'.format(job['export_type']))
        job['state'] = '/'.join(was_vuln_states)
        self._severity = [s.upper() for s in self._severity]
        job['func_params'] = {
            "indexed_at": int(self.check_point.get(job['check_point_time_field'], self.start_time)),
            "num_assets": self.vuln_num_assets,
            "severity": self._severity,
            "state": was_vuln_states
        }
        job['iterator'] = self._start_job(**job)
        return job

    def start_was_assets(self, time_field: str) -> Union[dict, None]:
        """
        Start WAS asset export and return job
        """
        job = {
            'export_type': 'was_assets',
            'time_field': time_field,
            'state': time_field.rstrip('_at'),
            'sourcetype': 'tenable:was:assets',
            'func': self._tio.exports.assets_v2,
            'transform_func': self.was_asset_event_transformer
        }
        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        is_first_run = False if self.check_point.get(job['check_point_time_field']) is not None else True
        self.log_debug(f'func=start_was_assets is_first_run={is_first_run} time_field={time_field}')
        #Dont download deleted/terminated assets on first run
        if is_first_run and job['time_field'] in ["deleted_at", "terminated_at"]:
            #set checkpoint so that no longer first run.
            self.check_point[job['check_point_time_field']] = self.current_time
            self.save_checkpoint()
            self.log_debug('func=start_was_assets action=skipped process=assets state={} reason=first_run'.format(job['state']))
            return None
        job['func_params'] = {
            "chunk_size": self.assets_chunk_size,
            "types": ["webapp"],
            time_field: int(self.check_point.get(job['check_point_time_field'], self.start_time))
        }
        job['iterator'] = self._start_job(**job)
        return job

    def start_audit_logs(self) -> dict:
        """
        Start IO Audit Logs export and return job
        """
        job = {
            'export_type': 'audit_logs',
            'state': 'all',
            'time_field': 'received',
            'check_point_time_field': 'audit_logs_received',
            'sourcetype': 'tenable:io:audit_logs',
            'func': self._tio.audit_log.events,
            'transform_func': self.audit_log_event_transformer
        }
        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        job['func_params'] = ('date',
                                'gte',
                                arrow.get(
                                    self.check_point.get(
                                        job['check_point_time_field'],
                                        self.start_time_date
                                    )
                                ).isoformat()
        )
        job['iterator'] = self._start_job(**job)
        return job

    def start_vulns(self) -> dict:
        """
        Start TVM Vuln export and return job
        """
        vuln_states = ["open", "reopened", "fixed"]
        job = {
            'export_type': 'vulns',
            'time_field': 'indexed_at',
            'sourcetype': 'tenable:io:vuln',
            'func': self._tio.exports.vulns,
            'check_point_time_field': 'vuln_last_run_date',
            'transform_func': self.vuln_event_transformer
        }
        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        is_first_run = False if self.check_point.get(job['check_point_time_field']) is not None else True
        self.log_debug(f'func=start_vulns is_first_run={is_first_run}')
        if (not self.fixed_vulnerability) and is_first_run:
            vuln_states.remove('fixed')
            self.log_debug('func=start_vulns action=skipped process={} state=fixed reason=first_run'.format(job['export_type']))
        job['state'] = '/'.join(vuln_states)
        job['func_params'] = {
            "indexed_at": int(self.check_point.get(job['check_point_time_field'], self.start_time)),
            "num_assets": self.vuln_num_assets,
            "severity": self._severity,
            "state": vuln_states,
            "tags": self._tags,
        }
        job['iterator'] = self._start_job(**job)
        return job

    def start_assets(self, time_field: str) -> Union[dict, None]:
        """
        Start TVM asset export and return job
        """
        job = {
            'export_type': 'assets',
            'time_field': time_field,
            'state': time_field.rstrip('_at'),
            'sourcetype': 'tenable:io:assets',
            'func': self._tio.exports.assets,
            'transform_func': self.asset_event_transformer

        }
        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        is_first_run = False if self.check_point.get(job['check_point_time_field']) is not None else True
        self.log_debug(f'func=start_assets is_first_run={is_first_run} time_field={time_field}')
        #Dont download deleted/terminated assets on first run
        if is_first_run and job['time_field'] in ["deleted_at", "terminated_at"]:
            #set checkpoint so that no longer first run.
            self.check_point[job['check_point_time_field']] = self.current_time
            self.save_checkpoint()
            self.log_debug('func=start_assets action=skipped process=assets state={} reason=first_run'.format(job['state']))
            return None
        job['func_params'] = {
            "chunk_size": self.assets_chunk_size,
            "tags": self._tags,
            time_field: int(self.check_point.get(job['check_point_time_field'], self.start_time))
        }
        job['iterator'] = self._start_job(**job)
        return job

    def start_plugins(self) -> Union[dict, None]:
        """
        Start TVM Plugin export and return job
        """
        job = {
            'export_type': 'plugins',
            'time_field': 'plugin_modification_date',
            'state': 'plugin_modification_date',
            'sourcetype': 'tenable:io:plugin',
            'func': self._tio.plugins.list,
            'transform_func': self.plugin_event_transformer
        }

        if not self.sync_plugins:
            self.log_debug('func=start_plugins action=skipped process={} state=not_enabled'.format(job['export_type']))
            return None

        job['check_point_time_field'] = self._gen_check_point_time_field(**job)
        plugin_modification_time = self.check_point.get(job['check_point_time_field'], self.start_time)
        plugin_modification_date = arrow.get(plugin_modification_time).date()
        # Only collect plugin data if the difference between current time and the last input invocation time
        # is greater or equal to 24 hrs. Added this because the API only has the fidelity of date.
        # Note: This won't prevent data duplication completely but will reduce multiple duplications to only once.
        time_diff = self.current_time - int(plugin_modification_time)
        is_first_run = False if self.check_point.get(job['check_point_time_field']) is not None else True
        self.log_debug(f'func=start_plugins is_first_run={is_first_run}')
        if (not is_first_run) and time_diff < 86400:
            self.log_debug('func=start_plugins action=skipped process={} state=reduce_data'.format(job['export_type']))
            return None
        job['func_params'] = {
            'last_updated': plugin_modification_date
        }
        job['iterator'] = self._start_job(**job)
        return job

    def collect_events(self, collect_compliance_data: bool=False, collect_audit_data: bool=False, collect_was_data: bool=False) -> None:
        """
        Collect vulnerabilities, assets, and plugins of tenable io based on given filters.
        """
        asset_export_types = ['updated_at', 'deleted_at','terminated_at']
        self.log_info('action=started process=data_collection')
        jobs = []
        if collect_compliance_data:
            jobs.append(self.start_compliance())
        elif collect_audit_data:
            jobs.append(self.start_audit_logs())
        elif collect_was_data:
            jobs.append(self.start_was_vulns())
            for export_type in asset_export_types:
                jobs.append(self.start_was_assets(export_type))
        else:
            #Start all jobs
            jobs.append(self.start_vulns())
            for export_type in asset_export_types:
                jobs.append(self.start_assets(export_type))
            jobs.append(self.start_plugins())
        #process all jobs we created
        self.process_jobs(jobs)
        #log that we completed with everything
        self.log_info('action=completed process=data_collection')