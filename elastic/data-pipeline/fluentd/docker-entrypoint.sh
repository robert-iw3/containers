#!/bin/sh

#source vars if file exists
DEFAULT=/etc/default/fluentd

if [ -r $DEFAULT ]; then
    set -o allexport
    . $DEFAULT
    set +o allexport
fi

# If the user has supplied only arguments append them to `fluentd` command
if [ "${1#-}" != "$1" ]; then
    set -- fluentd "$@"
fi

# If user does not supply config file or plugins, use the default
if [ "$1" = "fluentd" ]; then
    if ! echo $@ | grep -e ' \-c' -e ' \-\-config' ; then
       set -- "$@" --config /fluentd/etc/${FLUENTD_CONF}
    fi

    if ! echo $@ | grep -e ' \-p' -e ' \-\-plugin' ; then
       set -- "$@" --plugin /fluentd/plugins
    fi

    ## fluent-plugin-elastisearch specifics

    SIMPLE_SNIFFER=$( gem contents fluent-plugin-elasticsearch | grep elasticsearch_simple_sniffer.rb )
    if [ -n "$SIMPLE_SNIFFER" -a -f "$SIMPLE_SNIFFER" ] ; then
      set -- "$@" -r ${SIMPLE_SNIFFER}
    fi

fi

exec "$@"