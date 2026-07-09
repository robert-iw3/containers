# File: elasticsearch_connector.py
#
# Copyright (c) 2016-2025 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
"""Code that implements calls made to the elasticsearch systems device"""

import imp
import json
import sys
import urllib.parse as urllib

import phantom.app as phantom
import requests
from bs4 import BeautifulSoup
from phantom.action_result import ActionResult
from phantom.base_connector import BaseConnector

import elasticsearch_parser
from elasticsearch_consts import *


MODULE_NAME = "custom_parser"
HANDLER_NAME = "handle_request"


class PhantomDebugWriter:
    def __init__(self, this):
        self.this = this

    def write(self, message):
        self.this.save_progress(message)


class RetVal(tuple):
    """Represent the Tuple as a return value."""

    def __new__(cls, val1, val2=None):
        """Recursive call for tuple."""
        return tuple.__new__(RetVal, (val1, val2))


class ElasticsearchConnector(BaseConnector):
    # actions supported by this script
    ACTION_ID_RUN_QUERY = "run_query"
    ACTION_ID_GET_CONFIG = "get_config"
    REQUIRED_INGESTION_FIELDS = ["ingest_index", "ingest_query"]

    def __init__(self):
        """ """

        self._host = None
        self._base_url = None
        self._headers = None
        self._auth_method = None
        self._username = None
        self._password = None

        # Call the BaseConnectors init first
        super().__init__()

    def initialize(self):
        """Called once for every action, all member initializations occur here"""

        config = self.get_config()

        # Get the Base URL from the asset config and so some cleanup
        self._base_url = config[ELASTICSEARCH_JSON_DEVICE_URL].rstrip("/")

        # The host member extracts the host from the URL, is used in creating status messages
        self._host = self._base_url[self._base_url.find("//") + 2 :]

        # The headers, initialize them here once and use them for all other REST calls
        self._headers = {"Accept": "application/json", "Content-Type": "application/json"}

        self._username = config.get(phantom.APP_JSON_USERNAME)
        self._password = config.get(phantom.APP_JSON_PASSWORD)

        if self._username and self._password:
            self._auth_method = True

        return phantom.APP_SUCCESS

    def _dump_error_log(self, error, message="Exception occurred."):
        self.error_print(message, dump_object=error)

    def _get_error_message_from_exception(self, e):
        """This method is used to get appropriate error message from the exception.
        :param e: Exception object
        :return: error message
        """

        error_code = None
        error_message = ELASTICSEARCH_ERROR_MESSAGE_UNAVAILABLE
        self._dump_error_log(e)
        try:
            if hasattr(e, "args"):
                if len(e.args) > 1:
                    error_code = e.args[0]
                    error_message = e.args[1]
                elif len(e.args) == 1:
                    error_message = e.args[0]
        except Exception as ex:
            self._dump_error_log(ex, "Error occurred while fetching exception information")

        if not error_code:
            error_text = f"Error Message: {error_message}"
        else:
            error_text = f"Error Code: {error_code}. Error Message: {error_message}"

        return error_text

    def _process_json_response(self, r, action_result):
        # Try a json parse
        # For the valid 201 response, we are getting application/json in the header and empty json response in the body
        try:
            resp_json = r.json() if r.text else {}
        except Exception as e:
            msg_string = ELASTICSEARCH_ERROR_JSON_PARSE.format(raw_text=r.text.replace("{", " ").replace("}", " "))
            error_message = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(phantom.APP_ERROR, msg_string, error_message))

        # Please specify the status codes here
        if 200 <= r.status_code < 399:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        # You should process the error returned in the json
        action_result.add_data(resp_json)

        details = json.dumps(resp_json).replace("{", "").replace("}", "")

        return action_result.set_status(
            phantom.APP_ERROR, ELASTICSEARCH_ERROR_FROM_SERVER.format(status=r.status_code, detail=details)
        ), resp_json

    def _process_html_response(self, response, action_result):
        # An html response, treat it like an error
        status_code = response.status_code

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove the script, style, footer and navigation part from the HTML message
            for element in soup(["script", "style", "footer", "nav"]):
                element.extract()

            error_text = soup.text
            split_lines = error_text.split("\n")
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = "\n".join(split_lines)
        except Exception:
            error_text = "Cannot parse error details"

        message = f"Status Code: {status_code}. Response from server:\n{error_text}\n"

        message = message.replace("{", "{{").replace("}", "}}")

        if len(message) > 500:
            message = "Error occurred while connecting to the Elastic server"

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_empty_response(self, response, action_result):
        if response.status_code in ELASTICSEARCH_EMPTY_RESPONSE_STATUS_CODES:
            return RetVal(phantom.APP_SUCCESS, {})

        return RetVal(
            action_result.set_status(phantom.APP_ERROR, f"Status code: {response.status_code}. Empty response and no information in the header"),
            None,
        )

    def _process_response(self, r, action_result):
        # store the r_text in debug data, it will get dumped in the logs if the action fails
        if hasattr(action_result, "add_debug_data"):
            if r is not None:
                action_result.add_debug_data({"r_text": r.text})
                action_result.add_debug_data({"r_headers": r.headers})
                action_result.add_debug_data({"r_status_code": r.status_code})
            else:
                action_result.add_debug_data({"r_text": "r is None"})

        # Process each 'Content-Type' of response separately
        # Process a json response

        if "json" in r.headers.get("Content-Type", ""):
            return self._process_json_response(r, action_result)

        # Process an HTML response, Do this no matter what the api talks.
        # There is a high chance of a PROXY in between phantom and the rest of
        # world, in case of errors, PROXY's return HTML, this function parses
        # the error and adds it to the action_result.
        if "html" in r.headers.get("Content-Type", ""):
            return self._process_html_response(r, action_result)

        # it's not content-type that is to be parsed, handle an empty response
        if not r.text:
            return self._process_empty_response(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {} Response from server: {}".format(
            r.status_code, r.text.replace("{", "{{").replace("}", "}}")
        )

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _make_rest_call(self, endpoint, action_result, headers=None, json=None, params=None, method="get"):
        """Function that makes the REST call to the device, generic function that can be called from various action
        handlers"""

        if not headers:
            headers = {}

        # Get the config
        config = self.get_config()

        # Create the headers
        headers.update(self._headers)

        resp_json = None

        # get or post or put, whatever the caller asked us to use, if not specified the default will be 'get'
        request_func = getattr(requests, method)

        # handle the error in case the caller specified a non-existant method
        if not request_func:
            return action_result.set_status(phantom.APP_ERROR, ELASTICSEARCH_ERROR_API_UNSUPPORTED_METHOD, method=method)

        if self._auth_method:
            self.save_progress("Using authentication")
        else:
            self.save_progress("Not using any authentication, since either the password or username not specified")

        # Make the call
        try:
            r = request_func(
                f"{self._base_url}{endpoint}",  # The complete url is made up of the base_url, and the endpoint
                auth=(self._username, self._password) if self._auth_method else None,
                json=json,  # data is passing as json string
                headers=headers,  # The headers to send in the HTTP call
                verify=config[phantom.APP_JSON_VERIFY],  # should cert verification be carried out?
                params=params,  # uri parameters if any
                timeout=ELASTICSEARCH_DEFAULT_TIMEOUT,
            )
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, ELASTICSEARCH_ERROR_SERVER_MESSAGE, error_message), resp_json

        return self._process_response(r, action_result)

    def _test_connectivity(self, param):
        """Function that handles the test connectivity action, it is much simpler than other action handlers."""

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        # Action result to represent the call
        action_result = self.add_action_result(ActionResult(dict(param)))

        # Progress message, since it is test connectivity, it pays to be verbose
        self.save_progress(ELASTICSEARCH_MESSAGE_CLUSTER_HEALTH)

        # Make the rest endpoint call
        ret_val, response = self._make_rest_call(ELASTICSEARCH_CLUSTER_HEALTH, action_result)

        # Process errors
        if phantom.is_fail(ret_val):
            # Dump error messages in the log
            self.debug_print(action_result.get_message())

            # Set the status of the complete connector result
            action_result.set_status(phantom.APP_ERROR, action_result.get_message())

            # Append the message to display
            self.save_progress(ELASTICSEARCH_ERROR_CONNECTIVITY_TEST)

            # return error
            return phantom.APP_ERROR

        self.save_progress(ELASTICSEARCH_SUCCESS_CONNECTIVITY_TEST)
        # Set the status of the connector result
        return action_result.set_status(phantom.APP_SUCCESS)

    def _run_query(self, param):
        """Action handler for the 'run query' action"""

        # This is an action that needs to be represented by the ActionResult object
        # So create one and add it to 'self' (i.e. add it to the BaseConnector)
        # When the action_result is created this way, the parameter is also passed.
        # Other things like the summary, data and status is set later on.
        action_result = self.add_action_result(ActionResult(dict(param)))

        # validate the query that we got
        query_json = None
        try:
            if param.get(ELASTICSEARCH_JSON_QUERY):
                query_json = json.loads(param.get(ELASTICSEARCH_JSON_QUERY))
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return action_result.set_status(phantom.APP_ERROR, f"Unable to load query json. Error: {error_message}")

        index = [ind.strip() for ind in param.get(ELASTICSEARCH_JSON_INDEX).split(",")]
        index = ",".join(set(filter(None, index)))
        if not index:
            return self._action_result.set_status(phantom.APP_ERROR, ELASTICSEARCH_ERROR_INVALID_ACTION_PARAM.format(key="index"))
        endpoint = ELASTICSEARCH_QUERY_SEARCH_WITH_INDEX.format(index)

        routing = param.get(ELASTICSEARCH_JSON_ROUTING)

        params = None
        if routing:
            params = {"routing": urllib.quote(routing)}

        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        # Make the rest endpoint call
        ret_val, response = self._make_rest_call(endpoint, action_result, json=query_json, params=params, method="post")

        # Process errors
        if phantom.is_fail(ret_val):
            # Dump error messages in the log
            self.debug_print(action_result.get_message())
            return action_result.get_status()

        action_result.update_summary(
            {
                ELASTICSEARCH_JSON_TOTAL_HITS: response.get("hits", {}).get("total", {}).get("value", 0),
                ELASTICSEARCH_JSON_TIMED_OUT: response.get("timed_out", False),
            }
        )

        action_result.add_data(response)

        # Set the Status
        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_config(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        # Connectivity
        self.save_progress(phantom.APP_PROG_CONNECTING_TO_ELLIPSES, self._host)

        # Make the rest endpoint call
        ret_val, response = self._make_rest_call(ELASTICSEARCH_GET_INDEXES, action_result)

        # Process errors
        if phantom.is_fail(ret_val):
            # Dump error messages in the log
            self.debug_print(action_result.get_message())
            return action_result.get_status()

        for indices in response:
            data = {
                "index": indices.get("index"),
                "health": indices.get("health"),
                "status": indices.get("status"),
                "document_count": indices.get("docs.count"),
                "store_size": indices.get("store.size"),
            }
            action_result.add_data(data)

        action_result.update_summary({"total_indices": len(response)})

        # Set the Status
        return action_result.set_status(phantom.APP_SUCCESS)

    def _save_container(self, container_dict):
        config = self.get_config()
        container = container_dict.get("container")
        container["label"] = config.get("ingest", {}).get("container_label")
        container["artifacts"] = container_dict.get("artifacts")

        return self.save_container(container)

    def _on_poll(self, param):
        container_count = param.get("container_count", 0)

        config = self.get_config()
        if not all(field in config for field in self.REQUIRED_INGESTION_FIELDS):
            return self.set_status(phantom.APP_ERROR, ELASTICSEARCH_ON_POLL_ERROR_MESSAGE)

        query_params = {ELASTICSEARCH_JSON_INDEX: config["ingest_index"], ELASTICSEARCH_JSON_QUERY: config["ingest_query"]}
        if "ingest_routing" in config:
            query_params[ELASTICSEARCH_JSON_ROUTING] = config["ingest_routing"]

        self.save_progress("Quering data for {} index".format(config["ingest_index"]))
        ret_val = self._run_query(query_params)
        if phantom.is_fail(ret_val):
            return ret_val

        action_results = self.get_action_results()
        parser = config.get("ingest_parser")
        for action_result in action_results:
            for data in action_result.get_data():
                saved_stdout = sys.stdout
                debug_out = PhantomDebugWriter(self)
                if parser:
                    parser_name = config["ingest_parser__filename"]
                    self.save_progress(f"Using specified parser: {parser_name}")
                    ingest_parser = imp.new_module("custom_parser")
                    try:
                        sys.stdout = debug_out
                        exec(parser, ingest_parser.__dict__)
                        ret_dict_list = ingest_parser.ingest_parser(data)
                    except Exception as e:
                        error_message = self._get_error_message_from_exception(e)
                        return action_result.set_status(phantom.APP_ERROR, f"Unable to execute ingest parser: {error_message}")
                    finally:
                        sys.stdout = saved_stdout
                else:
                    sys.stdout = debug_out
                    ret_dict_list = elasticsearch_parser.ingest_parser(data)
                    sys.stdout = saved_stdout

                if not ret_dict_list:
                    continue

                if container_count and self.is_poll_now() and container_count < len(ret_dict_list):
                    ret_dict_list = ret_dict_list[:container_count]

                for ret_dict in ret_dict_list:
                    self._save_container(ret_dict)

        return action_result.set_status(phantom.APP_SUCCESS)

    def handle_action(self, param):
        """Function that handles all the actions"""

        # Get the action that we are supposed to carry out, set it in the connection result object
        action = self.get_action_identifier()

        # Intialize it to success
        ret_val = phantom.APP_SUCCESS

        # Bunch if if..elif to process actions
        if action == self.ACTION_ID_RUN_QUERY:
            ret_val = self._run_query(param)
        elif action == self.ACTION_ID_GET_CONFIG:
            ret_val = self._get_config(param)
        elif action == phantom.ACTION_ID_TEST_ASSET_CONNECTIVITY:
            ret_val = self._test_connectivity(param)
        elif action == phantom.ACTION_ID_INGEST_ON_POLL:
            ret_val = self._on_poll(param)

        return ret_val


def main():
    import argparse

    argparser = argparse.ArgumentParser()

    argparser.add_argument("input_test_json", help="Input Test JSON file")
    argparser.add_argument("-u", "--username", help="username", required=False)
    argparser.add_argument("-p", "--password", help="password", required=False)
    argparser.add_argument("-v", "--verify", action="store_true", help="verify", required=False, default=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password
    verify = args.verify

    if username is not None and password is None:
        # User specified a username but not a password, so ask
        import getpass

        password = getpass.getpass("Password: ")

    if username and password:
        try:
            login_url = BaseConnector._get_phantom_base_url() + "login"

            print("Accessing the Login page")
            r = requests.get(login_url, verify=verify, timeout=ELASTICSEARCH_DEFAULT_TIMEOUT)
            csrftoken = r.cookies["csrftoken"]

            data = dict()
            data["username"] = username
            data["password"] = password
            data["csrfmiddlewaretoken"] = csrftoken

            headers = dict()
            headers["Cookie"] = "csrftoken=" + csrftoken
            headers["Referer"] = login_url

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=verify, data=data, headers=headers, timeout=ELASTICSEARCH_DEFAULT_TIMEOUT)
            session_id = r2.cookies["sessionid"]
        except Exception as e:
            print("Unable to get session id from the platform. Error: " + str(e))
            sys.exit(1)

    with open(args.input_test_json) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = ElasticsearchConnector()
        connector.print_progress_message = True

        if session_id is not None:
            in_json["user_session_token"] = session_id
            connector._set_csrf_info(csrftoken, headers["Referer"])

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print(json.dumps(json.loads(ret_val), indent=4))

    sys.exit(0)


if __name__ == "__main__":
    main()
