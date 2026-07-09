# File: elasticsearch_consts.py
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
ELASTICSEARCH_JSON_DEVICE_URL = "url"
ELASTICSEARCH_JSON_QUERY = "query"
ELASTICSEARCH_JSON_INDEX = "index"
ELASTICSEARCH_JSON_TYPE = "type"
ELASTICSEARCH_JSON_ROUTING = "routing"
ELASTICSEARCH_JSON_TOTAL_HITS = "total_hits"
ELASTICSEARCH_JSON_TIMED_OUT = "timed_out"
ELASTICSEARCH_EMPTY_RESPONSE_STATUS_CODES = [200, 204]

# endpoints
ELASTICSEARCH_CLUSTER_HEALTH = "/_cluster/health"
ELASTICSEARCH_GET_INDEXES = "/_cat/indices"
ELASTICSEARCH_QUERY_SEARCH_WITH_INDEX = "/{0}/_search"

ELASTICSEARCH_ERROR_CONNECTIVITY_TEST = "Test Connectivity Failed"
ELASTICSEARCH_SUCCESS_CONNECTIVITY_TEST = "Test Connectivity Passed"
ELASTICSEARCH_ERROR_SERVER_MESSAGE = "Connection failed"
ELASTICSEARCH_ERROR_FROM_SERVER = "API failed, Status code: {status}, Detail: {detail}"
ELASTICSEARCH_MESSAGE_CLUSTER_HEALTH = "Querying cluster health to check connectivity"
ELASTICSEARCH_ERROR_API_UNSUPPORTED_METHOD = "Unsupported method"
ELASTICSEARCH_USING_BASE_URL = "Using url: {base_url}"
ELASTICSEARCH_ERROR_JSON_PARSE = "Unable to parse reply as a Json, raw string reply: '{raw_text}'"
ELASTICSEARCH_ERROR_MESSAGE_UNAVAILABLE = "Error message unavailable. Please check the asset configuration and|or action parameters"
ELASTICSEARCH_ON_POLL_ERROR_MESSAGE = "Ingestion requires a configured index and query."
ELASTICSEARCH_ERROR_INVALID_ACTION_PARAM = "Please provide a valid value in the '{key}' parameter"
ELASTICSEARCH_DEFAULT_TIMEOUT = 60
