#!/bin/sh -e

state_providers_file=${NIFI_HOME}/conf/state-management.xml
property_xpath='/stateManagement/cluster-provider/property'

edit_property() {
  property_name=$1
  property_value=$2

  if [ -n "${property_value}" ]; then
    xmlstarlet ed --inplace -u "${property_xpath}[@name='${property_name}']" -v "${property_value}" "${state_providers_file}"
  fi
}

edit_property 'Connect String'     "${NIFI_ZK_CONNECT_STRING}"
edit_property "Root Node"                   "${NIFI_ZK_ROOT_NODE}"

edit_property 'ConfigMap Name Prefix'     "${NIFI_KUBERNETES_CONFIGMAP_NAME_PREFIX}"