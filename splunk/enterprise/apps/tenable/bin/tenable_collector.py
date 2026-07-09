import time
from datetime import datetime, timezone
import json
import traceback
import sys
from typing import Union
import arrow
import tenable_utility as utility
import splunk.rest as rest
from solnlib import conf_manager
from tenable.io.exports.iterator import ExportsIterator, TioExportsError
from tenable.io.plugins import PluginIterator
from tenable.io.audit_log import AuditLogIterator
from tenable.sc.analysis import AnalysisResultsIterator
from splunklib import modularinput as smi
from solnlib.modular_input import checkpointer
import import_declare_test
import tenable_consts
try:
    from urllib.parse import quote_plus
except Exception:
    from urllib import quote_plus

TIME_PATTERN = "%Y-%m-%dT%H:%M:%SZ"


class TenableCollector(object):
    """
    Base class for tenable io and sc collectors.
    This class sets the common input params for io and sc.
    Along with that it also waits on kvstore to be in ready state,
    because the add-on uses it for maintaining the time checkpoints.
    """

    SEVERITY_ID_MAP = {
        0: "informational",
        1: "low",
        2: "medium",
        3: "high",
        4: "critical"
    }
    SEVERITIES = ["info", "low", "medium", "high", "critical"]


    def __init__(self, logger: object,
                        ew: object,
                        input_args,
                        session_key,
                        analysis_type: Union[str,None]=None
                    ) -> None:
        """
        Args:
            helper (object): object of BaseModInput class
            ew (object): object of event writer class
            analysis_type (str, optional): type of analysis e.g. vuln or mobile.
                                    Defaults to None.
        """
        self.logger = logger
        self.event_writer = ew
        self.session_key = session_key
        self.get_argus = input_args
        self.app_name = 'TA-tenable'
        self.build = utility.get_app_version(self.app_name)
        self.analysis_type = analysis_type
        self._wait_for_kvstore()
        self._set_input_data()
        self.current_time = int(time.time())
        self.curr_time = datetime.utcnow()
        self.current_time_formatted = self.curr_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    def log_info(self, message: str) -> None:
        """
        Wrapper to log INFO messages
        Args:
            message (str): message to append and log
        """

        self.logger.info(f'product={self.PRODUCT} input={self.input_name} {message} log_level=info')

    def log_error(self, message: str) -> None:
        """
        Wrapper to log ERROR messages
        Args:
            message (str): message to append and log
        """
        self.logger.error(f'product={self.PRODUCT} input={self.input_name} {message} log_level=error')

    def log_debug(self, message: str) -> None:
        """
        Wrapper to log DEBUG messages
        Args:
            message (str): message to append and log
        """
        self.logger.debug(f'product={self.PRODUCT} input={self.input_name} {message} log_level=debug')

    def log_warning(self, message: str) -> None:
        """
        Wrapper to log WARNING messages
        Args:
            message (str): message to append and log
        """
        self.logger.warning(f'product={self.PRODUCT} input={self.input_name} {message} log_level=warning')

    def get_check_point_using_rest(self, key, session_key=None):
        """Return given key named checkpoint from KV Store."""
        url = "/servicesNS/nobody/TA-tenable/storage/collections/data/TA_tenable_checkpointer/{key}?output_mode=json".format(
            key=quote_plus(key)
        )
        args = {}
        try:
            response, content = rest.simpleRequest(
                url, sessionKey=session_key, getargs=args, method="GET", raiseAllErrors=True
            )
        except Exception as ex:
            if "[HTTP 404]" in str(ex):
                # Key doesn't exists
                return None
            self.log_error(f'Error fetching checkpoint using rest call. Error: {str(ex)}')
            raise Exception(f'Error fetching checkpoint using rest call. Error: {str(ex)}')
        content = json.loads(content.decode())
        return json.loads(content.get("state"))

    def get_checkpoint(self) -> None:
        """
        Get checkpoint for self.check_point name. Assigned by each class
        """
        if not self.check_point_name:
            msg = 'Couldnt get check_point_name for class.'
            self.log_error(f'message={msg}')
            raise Exception(msg)
        checkpoint_collection = checkpointer.KVStoreCheckpointer(
            self.check_point_name, self.session_key, 'TA-tenable'
        )
        self.check_point = checkpoint_collection.get(self.check_point_name) or self.get_check_point_using_rest(self.check_point_name, self.session_key) or {}
        self.log_debug(f'func=get_checkpoint with name={self.check_point_name} value={self.check_point}')

    def save_checkpoint(self) -> None:
        """
        Save checkpoint data
        """
        checkpoint_collection = checkpointer.KVStoreCheckpointer(
            self.check_point_name, self.session_key, 'TA-tenable'
        )
        checkpoint_collection.update(self.check_point_name, self.check_point)
        self.log_debug(f'func=save_checkpoint name={self.check_point_name} value={self.check_point}')

    def _check_fix_plugin_output(self, plugin_output: str) -> str:
        """
        shorten plugin output field if it is to large
        """
        event_length = len(str(plugin_output))
        if event_length > self.max_event_size:
            plugin_output = (
                    f"Removed the original pluginText as it was {event_length} "
                    "characters. Currently max_event_size is set to: "
                    f"{self.max_event_size}"
            )
        return plugin_output

    def _wait_for_kvstore(self) -> None:
        """
        Wait for KV store to initialize.
        KV store is reuqiured aand used for maintaining time checkpoints.

        Raises:
            Exception: when kv store is not in ready state
        """
        def get_status():
            try:
                _, content = rest.simpleRequest("/services/kvstore/status",
                                                sessionKey=self.session_key,
                                                method="GET",
                                                getargs={"output_mode": "json"},
                                                raiseAllErrors=True)
            except ConnectionRefusedError:
                return 'connection_refused'
            data = json.loads(content)["entry"]
            return data[0]["content"]["current"].get("status")

        counter = 0
        status = get_status()
        while status != "ready":
            if status in ['starting', 'connection_refused']:
                counter += 1
                if counter < 3:
                    time.sleep(30)
                    status = get_status()
                    continue
            msg = f'KV store is not availabe. state={status}'
            self.log_error(f'message={msg}')
            raise Exception(msg)

    def _start_job(self, export_type: str,
                                func: str,
                                func_params,
                                state: str,
                                **kwargs
                            ) -> Union[ExportsIterator, PluginIterator, AuditLogIterator]:
        """
        Generic job starter

        Args:
            export_type (str): vulns, assets, or plugins
            func (str): pytenable function to call
            func_params (dict): parameters to pass to pytenable function
            state: state of data we are importing (all/open/deleted/etc.)

        Returns:
            Union[ExportsIterator, PluginIterator]
        """
        self.log_info(f'action=started process={export_type} state={state}')
        if isinstance(func_params, dict):
            return func(**func_params)
        elif isinstance(func_params, tuple):
            return func(func_params)

    def write_event(self,
                        event: dict,
                        sourcetype: str,
                        time_filter: str,
                        transform_func: str,
                    ) -> None:
        """
        Index the event into the splunk into given sourcetype.
        Events are transformed first before ingesting into the splunk.

        Args:
            event (dict): event to index
            sourcetype (str): sourcetype in which to index the events
            time_filter (str): time field value using which to save the checkpoint time
            transform_func (function): time field value using which to save the checkpoint time
        Returns:
            None
        """
        event, event_time = transform_func(event, time_filter)
        parsed_event = json.dumps(event, ensure_ascii=False)
        event = smi.Event(
                            data=parsed_event,
                            time=event_time,
                            index=self.index,
                            sourcetype=sourcetype,
                            unbroken=True
                        )
        self.event_writer.write_event(event)

    def _process_job(self, iterator: Union[ExportsIterator, PluginIterator, AnalysisResultsIterator, AuditLogIterator],
                            export_type: str,
                            sourcetype: str,
                            time_field: str,
                            state: str,
                            check_point_time_field: str,
                            transform_func: str,
                            **kwargs
                        ) -> None:
        """
        Process a job template and write events to splunk

        Args:
            iterator (Union[ExportsIterator, PluginIterator]): the iterator from pytenable that containes results
            export_type (str): vulns, assets, or plugins
            sourcetype (str): sourcetype of the event
                e.g. tenable:io:vuln, tenable:io:assets, tenable:io:plugin, tenable:io:compliance
            time_field (str): time field filter based on export
            state (str): state of data we are importing (all/open/deleted/etc.)
            check_point_time_field (str): time field to store this job checkpoint
            transform_func (str): function the event writer will call on each event before writing it

        Returns:
            Union[ExportsIterator, PluginIterator]
        """
        job_details = [f'{k}={v}' for k, v in kwargs.items()]
        self.log_debug('func=_process_job {}'.format(' '.join(job_details)))

        try:
            for i in iterator:
                self.write_event(i, sourcetype, time_field, transform_func)
        except TioExportsError as e:
            self.log_error(f'action=error process={export_type} state={state} msg={str(e)}')
        else:
            export_id = iterator.uuid if hasattr(iterator, 'uuid') else 'not_applicable'
            if iterator.count > 0:
                self.check_point[check_point_time_field] = self.current_time
                self.save_checkpoint()
            self.log_info(f"action=completed process={export_type} state={state} count={iterator.count} export_uuid={export_id}")

    def process_jobs(self, jobs: list) -> None:
        """
        Main processor to loop through data download jobs after they are all created.
        """
        self.log_debug(f'action=jobs jobs={jobs}')
        for job in jobs:
            if job is not None:
                self._process_job(**job)


    def _set_input_data(self) -> None:
        """
        Set common input form fields for data collection.
        """
        self.input_name = self.get_argus.get("name").split("//")[-1]
        self.interval = self.get_argus.get("interval")
        self.index = self.get_argus.get("index")
        self._account = self.get_credentials(self.session_key, self.get_argus.get("global_account"))

        self.start_time = self.get_argus.get("start_time") if self.get_argus.get(
            "start_time") else "1970-01-01T00:00:00Z"
        self.start_time_date = self.start_time
        self.start_time = arrow.get(self.start_time).int_timestamp

        self.fixed_vulnerability = self.get_argus.get('fixed_vulnerability')
        self.fixed_vulnerability =  utility.is_true(self.fixed_vulnerability)

        self.sync_plugins = self.get_argus.get('sync_plugins')
        self.sync_plugins = utility.is_true(self.sync_plugins)

        self.max_event_size = int(self.get_argus.get("max_event_size")) if self.get_argus.get(
            "max_event_size") else 67108864
        self.proxies = utility.get_proxy_settings(global_account_dict=self._account)
        self.log_debug(f'func=init')  # noqa: F541

    def get_credentials(self, session_key, account_name):
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
            )  # noqa: E501

            account_conf_file = cfm.get_conf(tenable_consts.ta_accounts_conf)
            service_account_json = account_conf_file.get(account_name)
        except Exception:
            self.log_error("message=account_error |"
                           " Failed to fetch Tenable Account details from configuration.\n"
                           "{}".format(traceback.format_exc()))  # noqa: F821
            sys.exit(1)  # noqa: F821
        return service_account_json

    def __del__(self):
        self.log_debug('func=delete')
