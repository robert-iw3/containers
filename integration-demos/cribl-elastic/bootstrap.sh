##!/bin/bash
#!/usr/bin/env bash
#This script will setup Elasticsearch and Cribl
#Requirements: jq, curl

#uncomment the next two lines to enable some debug logging
#exec 1>bootstrap_cribl_elasticsearch_log.txt 2>&1
#export PS4='+[`date "+%y-%m-%d %H:%M:%S"`][${BASH_SOURCE}:${LINENO}]: ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'; set -x;

#hack to add data to curl in variable form
generate_post_data () {
cat <<EOF
${1}
EOF
}

#quick function to create the api endpoint for a group based on the passed arguments
cribl_group_endpoint () {
  echo "api/v1/m/${1}${2}"
}

#send data in the correct form to the correct elasticsearch api endpoint
exec_es_curl () {
  output=$(generate_post_data "${2}")
  if [[ -n "${ES_ELASTIC_USER}" ]] && [[ -n "${ES_ELASTIC_PASSWORD}" ]]; then
    headers=(--user "${ES_ELASTIC_USER}:${ES_ELASTIC_PASSWORD}")
  else
    headers=(-H "Authorization: Bearer ${ES_ELASTIC_TOKEN}")
  fi
  curl -s -o /dev/null -XPUT "${ES_ELASTIC_URL}/${1}" -H "${cjson}" "${headers[@]}" --data-binary "${output}"
}

#send request to cribl through curl
exec_cribl_curl () {
  output=$(generate_post_data "${2}")
  status=$(curl -s -o /dev/null -w "%{http_code}" "${ES_CRIBL_URL}/${1}/${3}" -H "${ajson}" -H "${bearer}")
  #create if not found, else update
  if [[ "${status}" == "404" ]]; then
    headers=(-XPOST "${ES_CRIBL_URL}/${1}")
  else
    headers=(-XPATCH "${ES_CRIBL_URL}/${1}/${3}")
  fi
  curl -s -o /dev/null -H "${ajson}" -H "${cjson}" -H "${bearer}" "${headers[@]}" --data-binary "${output}"
}

#gets bearer token for either on-prem or cloud deployments. Needs to be run from the cribl cloud URL or cribl leader
cribl_get_auth_token () {
  cloudheaders=(--url "https://login.cribl.cloud/oauth/token" -d '{"grant_type": "client_credentials", "client_id": "'"${CRIBL_CLIENT_ID}"'", "client_secret": "'"${CRIBL_CLIENT_SECRET}"'", "audience": "https://api.cribl.cloud"}')
  onpremheaders=(--url "${ES_CRIBL_URL}/api/v1/auth/login" -d '{"username":"'"${CRIBL_USERNAME}"'","password":"'"${CRIBL_PASSWORD}"'"}')
  if [[ "${ES_CRIBL_URL}" == *.cribl.cloud ]]; then
    curl -s -XPOST ${cloudheaders[@]} -H "${cjson}" | jq -r .access_token
  else
    curl -s -XPOST ${onpremheaders[@]} -H "${cjson}" | jq -r .token
  fi
}

#elasticsearch API requests
es_requests () {
  exec_es_curl "${ES_ELASTIC_ROLE_CREATION_ENDPOINT}" "${ES_ELASTIC_ROLE_CREATION_DATA}"
  exec_es_curl "${ES_ELASTIC_USER_CREATION_ENDPOINT}" "${ES_ELASTIC_USER_CREATION_DATA}"
  exec_es_curl "${ES_ELASTIC_ILM_POLICY_ENDPOINT}" "${ES_ELASTIC_ILM_POLICY_DATA}"
  exec_es_curl "${ES_ELASTIC_COMPONENT_TEMPLATE_METRICS_ENDPOINT}" "$(cat ecm_metrics_component_template.json)"
  exec_es_curl "${ES_ELASTIC_INDEX_TEMPLATE_METRICS_ENDPOINT}" "${ES_ELASTIC_INDEX_TEMPLATE_METRICS_DATA}"
  exec_es_curl "${ES_ELASTIC_COMPONENT_TEMPLATE_LOGS_ENDPOINT}" "$(cat ecm_logs_component_template.json)"
  exec_es_curl "${ES_ELASTIC_INDEX_TEMPLATE_LOGS_ENDPOINT}" "${ES_ELASTIC_INDEX_TEMPLATE_LOGS_DATA}"
  exec_es_curl "${ES_ELASTIC_COMPONENT_TEMPLATE_DOWNSAMPLE_METRICS_ENDPOINT}" "${ES_ELASTIC_COMPONENT_TEMPLATE_DOWNSAMPLE_METRICS_DATA}"
  exec_es_curl "${ES_ELASTIC_INDEX_TEMPLATE_DOWNSAMPLE_METRICS_ENDPOINT}" "${ES_ELASTIC_INDEX_TEMPLATE_DOWNSAMPLE_METRICS_DATA}"
}

#cribl API requests
cribl_requests () {
  #creating some variables for readability
  bearer="Authorization: Bearer $(cribl_get_auth_token)"
  #for every group, create the input/output, and a pipeline to remove conflicts
  for group in ${ES_CRIBL_WORKERGROUP_NAME[*]}; do
    exec_cribl_curl $(cribl_group_endpoint "${group}" "${ES_CRIBL_API_PIPELINES_ENDPOINT}") "$(cat ecm_pipeline_config.json)" "cribl-internal_rm_conflicts"
    exec_cribl_curl $(cribl_group_endpoint "${group}" "${ES_CRIBL_API_OUTPUTS_ENDPOINT}") "${ES_CRIBL_API_OUTPUTS_DATA}" "${ES_CRIBL_ELASTIC_OUTPUT_ID}"
    exec_cribl_curl $(cribl_group_endpoint "${group}" "${ES_CRIBL_API_INPUTS_ENDPOINT}") "${ES_CRIBL_API_INPUTS_LOGS_DATA}" "${ES_CRIBL_LOGS_INPUT_ID}"
    exec_cribl_curl $(cribl_group_endpoint "${group}" "${ES_CRIBL_API_INPUTS_ENDPOINT}") "${ES_CRIBL_API_INPUTS_METRICS_DATA}" "${ES_CRIBL_METRICS_INPUT_ID}"
  done
}

#goat function that runs elasticsearch and cribl requests.
main () {
  #creating some variables for readability
  ajson="accept: application/json"
  cjson="Content-Type: application/json"
  echo "Starting to setup Elasticsearch"
  es_requests
  echo "Done. Now starting Cribl setup"
  cribl_requests
  echo "The script has completed. Don't forget to Commit & Deploy! Happy monitoring!"
}

#import .env
if [ "$-" = "${-%a*}" ]; then
    set -a
    . ./.env
    set +a
else
    . ./.env
fi

## let's goat
main
