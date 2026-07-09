#!/bin/sh
# SPDX-FileCopyrightText: 2024 Splunk, Inc.
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC1091
. "$(dirname "$0")"/common.sh

queryHaveCommand ntpdate
FOUND_NTPDATE=$?

queryHaveCommand sntp
FOUND_SNTP=$?

getServer ()
{
   if [ -f    /etc/ntp.conf ] ; then         # Linux; FreeBSD; AIX; Mac OS X maybe
		CONFIG=/etc/ntp.conf
	elif [ -f  /etc/inet/ntp.conf ] ; then    # Solaris
		CONFIG=/etc/inet/ntp.conf
	elif [ -f  /private/etc/ntp.conf ] ; then # Mac OS X
		CONFIG=/private/etc/ntp.conf
	else
		CONFIG=
	fi

	SERVER_DEFAULT='0.pool.ntp.org'
	if [ "$CONFIG" = "" ] ; then
		SERVER=$SERVER_DEFAULT
	else
		# shellcheck disable=SC2016
		SERVER=$($AWK '/^server / {print $2; exit}' "$CONFIG")
		SERVER=${SERVER:-$SERVER_DEFAULT}
	fi

}

#With ntpdate
if [ $FOUND_NTPDATE -eq 0 ] ; then
	echo "Found ntpdate command" >> "$TEE_DEST"
	getServer

	CMD2="ntpdate -q $SERVER"
	echo "CONFIG=$CONFIG, SERVER=$SERVER" >> "$TEE_DEST"

#With sntp
elif [ "$KERNEL" = "Darwin" ] && [ $FOUND_SNTP -eq 0 ] ; then # Mac OS 10.14.6 or higher version
 	echo "Found sntp command" >> "$TEE_DEST"
	getServer

	CMD2="sntp $SERVER"
	echo "CONFIG=$CONFIG, SERVER=$SERVER" >> "$TEE_DEST"

#With Chrony
else
	CMD2="chronyc -n sources"
fi

CMD1='date'

assertHaveCommand $CMD1
assertHaveCommand "$CMD2"

echo "Cmd1 = [$CMD1]" >> "$TEE_DEST"
$CMD1 | tee -a "$TEE_DEST"

echo "Cmd2 = [$CMD2]" >> "$TEE_DEST"
if [ "$KERNEL" = "Darwin" ] && [ $FOUND_SNTP -eq 0 ] ; then
  TMP_ERROR_FILTER_FILE=$SPLUNK_HOME/var/run/splunk/unix_time_error_tmpfile
  OUTPUT=$($CMD2 2>$TMP_ERROR_FILTER_FILE)

  if grep -q "Timeout" < $TMP_ERROR_FILTER_FILE; then
    LAST_LINE=$(echo "$OUTPUT" | tail -n 1)
    if [[ "$LAST_LINE" == *"$SERVER"* ]]; then
      echo "$LAST_LINE" | tee -a "$TEE_DEST"
    fi
    cat $TMP_ERROR_FILTER_FILE >> $TEE_DEST
    echo "$OUTPUT" >> "$TEE_DEST"
    rm $TMP_ERROR_FILTER_FILE 2>/dev/null
  elif grep -vq "Timeout" < $TMP_ERROR_FILTER_FILE; then
    cat $TMP_ERROR_FILTER_FILE >&2
    echo "$OUTPUT" >> "$TEE_DEST"
    rm $TMP_ERROR_FILTER_FILE 2>/dev/null
  else
    echo "$OUTPUT" | tee -a "$TEE_DEST"
  fi
else
	$CMD2 | tee -a "$TEE_DEST"
fi
