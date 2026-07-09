#!/bin/sh
# SPDX-FileCopyrightText: 2024 Splunk, Inc.
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC1091
. "$(dirname "$0")"/common.sh

HEADER='USERNAME                        FROM                            LATEST                          DURATION'
HEADERIZE="BEGIN {print \"$HEADER\"}"
PRINTF='{printf "%-30s  %-30.30s  %-30.30s  %-s\n", username, from, latest, duration}'

if [ "$KERNEL" = "Linux" ] ; then
	CMD='last -iw'
	# shellcheck disable=SC2016
	FILTER='{if ($0 == "") exit; if ($1 ~ /reboot|shutdown/ || $1 in users) next; users[$1]=1}'
	# shellcheck disable=SC2016
  # Extracts duration values from the 10th column of the `last` command output.
  # If the session is `still running` or `still logged in`, "N/A" is set as the default value.
  # This approach is applied to all supported kernels in the script.
  FORMAT='{
    username = $1;
    from = (NF>=10) ? $3 : "<console>";
    latest = (NF >= 10 && ($7 == "gone" || $8 == "gone" || $9 == "gone")) ? $(NF-7) " " $(NF-6) " " $(NF-5) " " $(NF-4) : $(NF-6) " " $(NF-5) " " $(NF-4) " " $(NF-3);
    duration = (NF >= 10 && $10 != "still" && $10 != "logged" && $10 != "running" && $10 != "in" && $10 != "" && $10 != "gone" && $10 != "no" && $10 != "logout") ? $10 : "N/A";
  }'
elif [ "$KERNEL" = "SunOS" ] ; then
	CMD='last -n 999'
	# shellcheck disable=SC2016
	FILTER='{if ($0 == "") exit; if ($1 ~ /reboot|shutdown/ || $1 in users) next; users[$1]=1}'
	# shellcheck disable=SC2016
	FORMAT='{
	  username = $1;
	  from = (NF>=10) ? $3 : "<console>";
	  latest = (NF >= 10 && ($7 == "gone" || $8 == "gone" || $9 == "gone")) ? $(NF-7) " " $(NF-6) " " $(NF-5) " " $(NF-4) : $(NF-6) " " $(NF-5) " " $(NF-4) " " $(NF-3);
	  duration = (NF >= 10 && $10 != "still" && $10 != "logged" && $10 != "running" && $10 != "in" && $10 != "" && $10 != "gone" && $10 != "no" && $10 != "logout") ? $10 : "N/A";
  }'
elif [ "$KERNEL" = "AIX" ] ; then
	failUnsupportedScript
elif [ "$KERNEL" = "Darwin" ] ; then
	CMD='last -99'
	# shellcheck disable=SC2016
	FILTER='{if ($0 == "") exit; if ($1 ~ /reboot|shutdown/ || $1 in users) next; users[$1]=1}'
	# shellcheck disable=SC2016
  FORMAT='{
    username = $1;
    from = ($0 !~ /                /) ? $3 : "<console>";
    latest = (NF >= 10 && ($7 == "gone" || $8 == "gone" || $9 == "gone")) ? $(NF-7) " " $(NF-6) " " $(NF-5) " " $(NF-4) : $(NF-6) " " $(NF-5) " " $(NF-4) " " $(NF-3);
    duration = (NF >= 10 && $10 != "still" && $10 != "logged" && $10 != "running" && $10 != "in" && $10 != "" && $10 != "gone" && $10 != "no" && $10 != "logout") ? $10 : "N/A";
  }'
elif [ "$KERNEL" = "HP-UX" ] ; then
    CMD='lastb -Rx'
	# shellcheck disable=SC2016
    FORMAT='{username = $1; from = ($2=="console") ? $2 : $3; latest = $(NF-3) " " $(NF-2)" " $(NF-1)}'
	# shellcheck disable=SC2016
    FILTER='{if ($1 == "BTMPS_FILE") next; if (NF==0) next; if (NF<=6) next;}'
elif [ "$KERNEL" = "FreeBSD" ] ; then
  CMD='last -w'
	# shellcheck disable=SC2016
	FILTER='{if ($0 == "") exit; if ($1 ~ /reboot|shutdown/ || $1 in users) next; users[$1]=1}'
	# shellcheck disable=SC2016
  FORMAT='{
    username = $1;
    from = (NF>=10) ? $3 : "<console>";
    latest = (NF >= 10 && ($7 == "gone" || $8 == "gone" || $9 == "gone")) ? $(NF-7) " " $(NF-6) " " $(NF-5) " " $(NF-4) : $(NF-6) " " $(NF-5) " " $(NF-4) " " $(NF-3);
    duration = (NF >= 10 && $10 != "still" && $10 != "logged" && $10 != "running" && $10 != "in" && $10 != "" && $10 != "gone" && $10 != "no" && $10 != "logout") ? $10 : "N/A";
  }'
fi

assertHaveCommand $CMD

out=$($CMD | tee "$TEE_DEST" | $AWK "$HEADERIZE $FILTER $FORMAT $PRINTF"  header="$HEADER")
lines=$(echo "$out" | wc -l)
if [ "$lines" -gt 1 ]; then
	echo "$out"
	echo "Cmd = [$CMD];  | $AWK '$HEADERIZE $FILTER $FORMAT $PRINTF' header=\"$HEADER\"" >> "$TEE_DEST"
else
	echo "No data is present" >> "$TEE_DEST"
fi
