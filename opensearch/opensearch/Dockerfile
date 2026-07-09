ARG OPENSEARCH_VERSION

FROM docker.io/opensearchproject/opensearch:${OPENSEARCH_VERSION}

RUN \
    echo -e $'declare -a PLUGIN=( \n\
    "opensearch-alerting" \n\
    "opensearch-anomaly-detection" \n\
    "opensearch-asynchronous-search" \n\
    "opensearch-geospatial" \n\
    "opensearch-index-management" \n\
    "opensearch-job-scheduler" \n\
    "opensearch-ml" \n\
    "opensearch-performance-analyzer" \n\
    "opensearch-security" \n\
    "opensearch-reports-scheduler"); \n\
    for ((i=0; i<${#PLUGIN[@]}; i++)); do \n\
    /usr/share/opensearch/bin/opensearch-plugin install --batch ${PLUGIN[$i]} \n\
    done' | tee plugins_install.sh; chmod +x plugins_install.sh; \
    bash -c "./plugins_install.sh"
