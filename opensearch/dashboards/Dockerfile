ARG DASHBOARDS_VERSION

FROM docker.io/opensearchproject/opensearch-dashboards:${DASHBOARDS_VERSION}

RUN \
    echo -e $'declare -a PLUGIN=( \n\
    "alerting-dashboards-plugin" \n\
    "anomaly-detection-dashboards-plugin" \n\
    "dashboards-search-relevance" \n\
    "index-management-dashboards-plugin" \n\
    "dashboards-notifications" \n\
    "dashboards-observability" \n\
    "query-workbench" \n\
    "dashboards-reporting" \n\
    "security-analytics-dashboards-plugin" \n\
    "security-dashboards-plugin"); \n\
    for ((i=0; i<${#PLUGIN[@]}; i++)); do \n\
    /usr/share/opensearch/bin/opensearch-plugin install ${PLUGIN[$i]} \n\
    done' | tee plugins_install.sh; chmod +x plugins_install.sh; \
    bash -c "./plugins_install.sh"
