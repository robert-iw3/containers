# File: elasticsearch_parser.py
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
def ingest_parser(data):
    results = []
    if not isinstance(data, dict):
        return results

    hits = data.get("hits", {}).get("hits", [])
    for hit in hits:
        container = {}
        artifacts = []

        # anything printed to stdout will be added to the phantom debug logs
        print("Found hit {}. Building container".format(hit["_id"]))

        container["run_automation"] = False
        container["source_data_identifier"] = hit["_id"]
        container["name"] = "Elasticsearch: {} {}".format(hit["_index"], hit["_id"])

        artifacts.append(
            {
                # always True since there is only one
                "run_automation": True,
                "label": "event",
                "name": "elasticsearch event",
                "cef": hit.get("_source"),
                "source_data_identifier": hit["_id"],
            }
        )

        results.append({"container": container, "artifacts": artifacts})

    return results
