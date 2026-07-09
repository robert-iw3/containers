import time
from typing import Tuple
from tenable.sc.analysis import AnalysisResultsIterator
import tenable_utility as utility
import tenable_consts
from tenable.sc import TenableSC
from tenable.sc.plugins import PluginResultsIterator
from tenable.errors import ConnectionError
from custom_http_adapter import CustomHTTPAdapter
from tenable_collector import TenableCollector

class SCCollector(TenableCollector):

    PRODUCT = 'TSC'

    def _set_input_data(self) -> None:
        """
        Set Tenable SC input form fields and initialize tio object.
        """
        super(SCCollector, self)._set_input_data()
        # Basic items we must have
        self.check_point_name = self.input_name + '_' + self.analysis_type
        self.get_checkpoint()
        #SC Unique things

        self.query_name = self.get_argus.get('query_name', None)
        self.make_time_ms = utility.is_true(self.get_argus.get('make_time_ms'))

        [self.host, self.port, self.complete_address] = utility.get_host_port(self._account['address'])

        try:
            self.page_size = self.get_argus.get('page_size') if self.get_argus.get('page_size') else 1000
        except (ValueError, TypeError) as e:
            self.log_warning(f'message=can not set page_size (defaulting page size to 1000): {e}')
            self.page_size = 1000

        tsc_kwargs = {
            'host': self.host,
            'port':self.port,
            'vendor': 'Tenable',
            'product': 'SplunkTA',
            'build': self.build,
            'proxies': self.proxies
        }
        self.basic_auth = False
        if self._account.get("certificate_path") != None:  # noqa: E711
            tsc_kwargs.update(self._get_cert_auth_details())
            self.log_debug('auth_type=certificate')
        elif self._account.get("tenable_sc_access_key") != None:  # noqa: E711
            tsc_kwargs.update(self._get_api_auth_details())
            self.log_debug('auth_type=api_keys')
        else:
            tsc_kwargs.update(self._get_basic_auth_details())
            self.log_debug('auth_type=basic')
            self.basic_auth = True

        try:
            self._tsc = TenableSC(**tsc_kwargs)
            if self.basic_auth:
                self._tsc.login(self._account["username"], self._account["password"])
        except ConnectionError as e:
            self.log_error(f'message={e}')
            raise Exception(e)
        self.log_debug(f'query_name={self.query_name} page_size={self.page_size}')
        self.organization = self.get_organization()

        self._set_query_details()

    def _set_query_details(self):
        self.query_id = None
        if self.query_name is not None:
            self.query_id = self._get_query_id(self.query_name)
            self.log_debug(f'func=_set_query_details query_id={self.query_id}')

    def _get_basic_auth_details(self) -> dict:
        """
        Return unique kwargs needed for basic auth
        """
        self._source = (
            self._account['username']
            + self._account['address']
        )
        verify_ssl = tenable_consts.verify_ssl_for_sc_creds
        if utility.is_true(self._account.get('use_ca_cert')):
            verify_ssl = tenable_consts.CUSTOM_CERT_FILE_LOC.format(self._account.get('account_name'))
        return {
            'ssl_verify': verify_ssl
        }

    def _get_api_auth_details(self) -> dict:
        """
        Return unique kwargs needed for API auth
        """
        self._source = (
            self.get_argus.get("global_account")
            + self._account["address"]
        )
        verify_ssl = tenable_consts.verify_ssl_for_sc_api_key
        if utility.is_true(self._account.get('use_ca_cert')):
            verify_ssl = tenable_consts.CUSTOM_CERT_FILE_LOC.format(self._account.get('account_name'))
        return {
            'access_key': self._account.get("tenable_sc_access_key"),
            'secret_key': self._account.get("tenable_sc_secret_key"),
            'ssl_verify': verify_ssl,
        }

    def _get_cert_auth_details(self) -> dict:
        """
        Return unique kwargs needed for basic auth
        """
        self._source = self._account["certificate_path"] + self._account["address"]
        certificate_path, key_file_path = utility.get_certificate_path(
            self.app_name,
            self._account["certificate_path"],
            self._account["key_file_path"]
        )
        certificate_key_password = self._account.get("key_password", '')
        adapter = CustomHTTPAdapter(
            certfile=certificate_path,
            keyfile=key_file_path,
            password=certificate_key_password
        )
        verify_ssl = tenable_consts.verify_ssl_for_sc_cert
        if utility.is_true(self._account.get('use_ca_cert')):
            verify_ssl = tenable_consts.CUSTOM_CERT_FILE_LOC.format(self._account.get('account_name'))
        return {
            # self._account["address"].strip('/'),
            'ssl_verify': verify_ssl,
            'access_key': self._account.get("tenable_sc_access_key"),
            'secret_key': self._account.get("tenable_sc_secret_key"),
            'adapter': adapter,
        }

    def generate_sc_uniqueness(self, event: dict) -> str:
        """
        Standard function to generate the sc_uniqueness value needed for event deduplication
        """
        ##TODO: Steven can this be done any faster?
        if event.get('uniqueness'):
            uniqness = event.get('uniqueness','').split(',')
            tmp_array = []
            for field in uniqness:
                if field == 'repositoryID':
                    tmp_array.append(event.get('repository',{}).get('id'))
                else:
                    tmp_array.append(event.get(field))
            return '_'.join(tmp_array)
        else:
            return ""


    def basic_event_transform(self, event: dict) -> dict:
        """
        Returns data we want added to every event
        """
        return {
            'SC_address': self._account["address"],
            'sc_uniqueness': self.generate_sc_uniqueness(event),
            'organization': self.organization,
        }

    def vuln_event_transformer(self,
                                    event: dict,
                                    time_field:str
                                ) -> Tuple:
        """
        Transform vuln events before they are written to events

        Args:
            event (dict): vuln, asset, or plugin event
            sourcetype: (str):
            time_field (str): time field filter e.g. lastSeen or lastMitigated

        Returns:
            dict, int: transformed event and epoch time on which to index the event
        """

        event.update(self.basic_event_transform(event))
        severity_info = event.pop("severity")
        updates = {
            'custom_severity': bool(int(event.get("recastRisk", "0"))),
            'acceptRisk': bool(int(event.get("acceptRisk", '0'))),
            'hasBeenMitigated': bool(int(event.get("hasBeenMitigated", "0"))),
            'recastRisk': bool(int(event.get("recastRisk", "0"))),
            'severity_id': severity_info.get("id", ""),
            'vendor_severity': severity_info.get("name", ""),
            'severity_description': severity_info.get("description", ""),
            'severity': self.SEVERITY_ID_MAP[int(severity_info.get("id", "0"))],
            'plugin_id': event.get("pluginID"),
            'pluginText': self._check_fix_plugin_output(event.pop('pluginText', ''))
        }

        event.update(updates)
        event_time = int(event.get(time_field, time.time()))
        if event.get('source', False):
            event["finding_source"] = event.pop("source")
        ## Update timestamps if feature enabled
        if self.make_time_ms:
            # TODO: Can we fix in python 3.9
            first_seen = event.get('firstSeen')
            last_seen = event.get('lastSeen')
            if len(first_seen) == 10:
                event['firstSeen'] = f'{first_seen}.000'
                event['lastSeen'] = f'{last_seen}.000'
        # for patched vulns set state of vuln to fixed
        if time_field == "lastMitigated":
            event["state"] = "fixed"
        else:
            event['state'] = 'reopened' if bool(int(event.get('hasBeenMitigated', '0'))) else 'open'
        return event, event_time

    def asset_event_transformer(self,
                                    event: dict,
                                    time_field: str,
                                    ) -> Tuple:
        """
        Transforms and updates the received json event.

        Args:
            event (dict): vuln, asset, compliance or plugin event
            sourcetype (str): sourcetype of the event
                e.g. tenable:io:vuln, tenable:io:assets, tenable:io:plugin, tenable:io:compliance
            time_field (str): time field filter based on export
                lastSeen - vulns and compliance

        Returns:
            Tuple(dict, int): transformed event and epoch time on which to index the event
        """

        event.update(self.basic_event_transform(event))
        return event, int(time.time())

    def _get_query_id(self, query_name: str) -> int:
        """
        Get filters of the given query. Query name must be of type vulndetails and should be unique.
        Args:
            query_name (str): query name for which to find the filters
        Raises:
            Exception: if multiple queries with same name is found or if it not of type vulndetails
        Returns:
            int: id of the found query
        """
        fields = ["id", "name", "filters", "tool"]
        response = self._tsc.queries.list(fields=fields)

        found_query = False
        query_info = {}
        found_query_with_other_tool = False
        self.log_debug(f'func=_get_query_id query={query_name}')
        for query in response.get("usable"):
            if query["name"] == query_name and query["tool"] == "vulndetails":
                if found_query:
                    msg = f'Multiple query IDs found with given query name {query_name}'
                    self.log_error(msg)
                    raise Exception(msg)
                else:
                    query_info = query
                    found_query = True
            elif query["name"] == query_name and query["tool"] != "vulndetails":
                found_query_with_other_tool = True

        if not query_info and found_query_with_other_tool:
            msg = 'Provided query must use the Vulnerability Detail List tool.'
            self.log_error(f'func=_get_query_id message={msg}')
            raise Exception(msg)
        qid = int(query_info.get('id'))
        self.log_debug(f'func=_get_query_id query={query_name} value={qid}')
        return qid

    def get_organization(self) -> dict:
        """
        Get organization details of the current user.
        Organization details are added to all events.

        Returns:
            dict
        """

        user = self._tsc.current.user()
        org = user.get('organization', {})
        self.log_debug(f'func=get_organization value={org}')
        return org

    def _get_analysis_data(self,
                                tool: str,
                                source: str,
                                time_field: str,
                                check_point_time_field: str,
                                **kwargs
                            ) -> AnalysisResultsIterator:
        """
        Get analysis data based filter params.
        This method is common for fetching active vulns, patched vulns, and assets.
        Fetches the checkpoint, forms the params, and filters to get the analysis data accordingly.

        Args:
            tool (str): The analysis tool for formatting and returning a specific view into the information.
                        e.g. vulndetails(for vulns), and sumip(for assets)
            source (str): The data source location.
                        e.g. cumulative(for active vulns and assets), and patched(for fixed vulns)
            time_field (str): Time filter to use while getting analysis data.
                        e.g. lastSeen(for active vulns and assets), and lastMitigated(for patched vulns)
                        Time from which to fetch the data
            check_point_time_field (str): Checkpoint time field.
                        e.g. vuln_last_run_date(for vulns), assets_last_run_date(for assets)

        Returns:
            AnalysisResultsIterator
        """

        params = {
            "tool": tool,
            "source": source,
            "limit": self.page_size
        }

        if self.query_id is not None:
            params.update({"query_id": self.query_id})

        last_run_date = self.check_point.get(check_point_time_field, self.start_time)
        filters = [
            (
                time_field, "=", str(last_run_date) + "-" + str(self.current_time)
            )
        ]
        self.log_debug(f'filters={filters} params={params}')
        return self._tsc.analysis.vulns(*filters, **params)

    def _get_mobile_analysis_data(self,
                                    tool: str,
                                    **kwargs
                                ) -> AnalysisResultsIterator:
        """
        Get mobile analysis data.
        All the mobile data will get collected every time from start of epoch.

        Args:
            tool (str): The analysis tool for formatting and returning a specific view into the information.
                        e.g. vulndetails - mobile vulns, sumdeviceid - mobile assets
        Returns:
            AnalysisResultsIterator
        """
        params = {
            "tool": tool,
            "limit": self.page_size
        }
        if self.query_id is not None:
            params.update({"query_id": self.query_id})

        return self._tsc.analysis.mobile(**params)

    def _get_plugin_data(self,
                            check_point_time_field: str,
                            **kwargs
                            ) -> PluginResultsIterator:
        """
        Wrapper to simplify getting plugin data
        Args:
            check_point_time_field (str): Checkpoint time field.
                e.g. vuln_last_run_date(for vulns), assets_last_run_date(for assets)
        Returns:
            PluginIterator
        """
        return self._tsc.plugins.list(
            fields=[
                "name", "description", "family", "type", "copyright", "version", "sourceFile", "dependencies", "requiredPorts",
                "requiredUDPPorts", "cpe", "srcPort", "dstPort", "protocol", "riskFactor", "solution", "seeAlso", "synopsis", "checkType",
                "exploitEase", "exploitAvailable", "exploitFrameworks", "cvssVector", "cvssVectorBF", "baseScore", "temporalScore",
                "stigSeverity", "pluginPubDate", "pluginModDate", "patchPubDate", "patchModDate", "vulnPubDate", "modifiedTime", "md5", "xrefs",
                "vprScore", "vprContext"
            ],
            limit=10000,
            since=self.check_point.get(check_point_time_field, self.start_time),
            sort_field="modifiedTime",
            sort_direction="desc"
        )

    def process_vulns(self) -> None:
        """
        Get all vulnerabilities
        """
        job = {
            'state': 'open/reopened',
            'export_type': 'vulns',
            'time_field': 'lastSeen',
            'check_point_time_field': 'vulns_open_lastSeen',
            'tool': 'vulndetails',
            'source': 'cumulative',
            'sourcetype': 'tenable:sc:vuln',
            'transform_func': self.vuln_event_transformer
        }
        is_first_run = False if self.check_point.get(job['check_point_time_field']) is not None else True
        job['iterator'] = self._get_analysis_data(**job)
        #Active Vulns
        self._process_job(**job)
        self.log_debug(f'func=process_vulns is_first_run={is_first_run}')
        if self.fixed_vulnerability or (not is_first_run):
            patched = {
                'time_field': 'lastMitigated',
                'check_point_time_field': 'vulns_fixed_lastMitigated',
                'source': 'patched',
                'state': 'fixed'
            }
            job.update(patched)
            job['iterator'] = self._get_analysis_data(**job)
            self._process_job(**job)

    def process_mobile_vulns(self) -> None:
        """
        Get all open mobile vulnerabilities
        NOTE: in the future we should look a deltas and fixed data
        """
        job = {
           'state': 'open/reopened',
           'export_type': 'mobile_vulns',
           'time_field': 'lastSeen',
           'check_point_time_field': 'vulns_mobile_lastSeen',
           'tool': 'vulndetails',
           'source': 'cumulative',
           'sourcetype': 'tenable:sc:mobile:vuln',
           'transform_func': self.vuln_event_transformer
       }
        job['iterator'] = self._get_mobile_analysis_data(**job)
        self._process_job(**job)

    def process_mobile_assets(self) -> None:
        """
        Process Mobile SC assets.
        NOTE: In the future we should try to make this do diffs. Today i just pulls everything.
        """
        job = {
            'state': 'all',
            'export_type': 'mobile_assets',
            'time_field': 'lastSeen',
            'check_point_time_field': 'assets_mobile_lastSeen',
            'tool': 'sumdeviceid',
            'sourcetype': 'tenable:sc:mobile:assets',
            'transform_func': self.asset_event_transformer
        }
        job['iterator'] = self._get_mobile_analysis_data(**job)
        self._process_job(**job)

    def process_assets(self) -> None:
        """
        Process TSC Assets.
        NOTE: This only pulls in cumulative assets. In the future this should do patched as well.
        """
        job = {
            'state': 'all',
            'export_type': 'assets',
            'time_field': 'lastSeen',
            'check_point_time_field': 'assets_lastSeen',
            'tool': 'sumip',
            'source': 'cumulative',
            'sourcetype': 'tenable:sc:assets',
            'transform_func': self.asset_event_transformer
        }
        job['iterator'] = self._get_analysis_data(**job)
        self._process_job(**job)

    def process_plugins(self) -> None:
        """
        Get all plugins
        """
        job = {
            'state': 'all',
            'export_type': 'plugins',
            'time_field': 'since',
            'check_point_time_field': 'plugin_since',
            'tool': 'none',
            'source': 'none',
            'sourcetype': 'tenable:sc:plugin',
            'transform_func': self.asset_event_transformer
        }
        if not self.sync_plugins:
            self.log_debug('func=process_plugins action=skipped process={} state=not_enabled'.format(job['export_type']))
            return None
        job['iterator'] =  self._get_plugin_data(**job)
        self._process_job(**job)

    def collect_events(self) -> None:
        """
        Collect vulnerabilities, assets, and plugins
        """
        self.log_info('action=started process=data_collection')
        if self.analysis_type == 'sc_mobile':
            self.process_mobile_assets()
            self.process_mobile_vulns()
        else:
            self.process_assets()
            self.process_vulns()
            self.process_plugins()

        if self.basic_auth:
            self._tsc.logout()
        self.log_info('action=completed process=data_collection')
