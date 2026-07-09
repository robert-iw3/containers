#!/bin/sh
# SPDX-FileCopyrightText: 2024 Splunk, Inc.
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC1091
. "$(dirname "$0")"/common.sh

HEADER='Datetime                        pctUser    pctNice  pctSystem  pctIowait    pctIdle    OSName                                   OS_version  IP_address        CPU'
HEADERIZE="BEGIN {print \"$HEADER\"}"
PRINTF='{printf "%-28s  %9s  %9s  %9s  %9s  %9s    %-35s %15s  %-16s  %-3s\n", datetime, pctUser, pctNice, pctSystem, pctIowait, pctIdle, OSName, OS_version, IP_address,cpu}'
FILL_DIMENSIONS='{length(IP_address) || IP_address = "?";length(OS_version) || OS_version = "?";length(OSName) || OSName = "?"}'

if [ "$KERNEL" = "Linux" ] ; then
    queryHaveCommand sar
    FOUND_SAR=$?
    queryHaveCommand mpstat
    FOUND_MPSTAT=$?
    if [ ! -f "/etc/os-release" ] ; then
        DEFINE="-v OSName=$(cat /etc/*release | head -n 1| awk -F" release " '{print $1}'| tr ' ' '_') -v OS_version=$(cat /etc/*release | head -n 1| awk -F" release " '{print $2}' | cut -d\. -f1) -v IP_address=$(hostname -I | cut -d\  -f1)"
    else
        DEFINE="-v OSName=$(cat /etc/*release | grep '\bNAME=' | cut -d '=' -f2 | tr ' ' '_' | cut -d\" -f2) -v OS_version=$(cat /etc/*release | grep '\bVERSION_ID=' | cut -d '=' -f2 | cut -d\" -f2) -v IP_address=$(hostname -I | cut -d\  -f1)"
    fi
    if [ $FOUND_SAR -eq 0 ] ; then
        CMD='sar -P ALL 2 5'
        # shellcheck disable=SC2016
        FORMAT='{datetime = strftime("%m/%d/%y_%H:%M:%S_%Z"); cpu=$(NF-6); pctUser=$(NF-5); pctNice=$(NF-4); pctSystem=$(NF-3); pctIowait=$(NF-2); pctIdle=$NF;OSName=OSName;OS_version=OS_version;IP_address=IP_address;}'
    elif [ $FOUND_MPSTAT -eq 0 ] ; then
        CMD='mpstat -P ALL 2 5'
        # shellcheck disable=SC2016
        FORMAT='{datetime = strftime("%m/%d/%y_%H:%M:%S_%Z"); cpu=$(NFIELDS-10); pctUser=$(NFIELDS-9); pctNice=$(NFIELDS-8); pctSystem=$(NFIELDS-7); pctIowait=$(NFIELDS-6); pctIdle=$NF;OSName=OSName;OS_version=OS_version;IP_address=IP_address;}'
    else
        failLackMultipleCommands sar mpstat
    fi
    # shellcheck disable=SC2016
    FILTER='($0 ~ /CPU/) { if($(NF-1) ~ /gnice/){  NFIELDS=NF; } else {NFIELDS=NF+1;} next} /Average|Linux|^$|%/ {next}'
elif [ "$KERNEL" = "SunOS" ] ; then
    CMD='mpstat -p 2 5'
    DEFINE="-v OSName=$(uname -s) -v OS_version=$(uname -r) -v IP_address=$(ifconfig -a | grep 'inet ' | grep -v 127.0.0.1 | cut -d\  -f2 | head -n 1)"
    FORMAT='

    function get_cpu_count(){
        command = "psrinfo -p";  # Use this for Solaris
        command | getline cpu_count;
        close(command);
        return cpu_count;
    }

    BEGIN {
        cpu_processed = 0;
        user_sum = system_sum = iowait_sum = idle_sum = 0;
        # Dynamically set CPU count
        cpu_count = get_cpu_count();
        last_cpu = cpu_count-1;
    }

    function get_current_time() {
        command = "date +\"%m/%d/%y_%H:%M:%S_%Z\"";
        command | getline datetime;
        close(command);
        return datetime;
    }{
        datetime=get_current_time();
        cpu=$1;
        pctUser=$(NF-4);
        pctNice="0";
        pctSystem=$(NF-3);
        pctIowait=$(NF-2);
        pctIdle=$(NF-1);

        user_sum += pctUser;
        system_sum += pctSystem;
        iowait_sum += pctIowait;
        idle_sum += pctIdle;
        cpu_processed++;
    }
    '
    FILTER='($0 ~ /CPU/) { if($(NF-1) ~ /gnice/){  NFIELDS=NF; } else {NFIELDS=NF+1;} next} /Average|Linux|^$|%/ {next}'
    PRINTF='
    {
    if (cpu ~ /0/) {
        print header;
        {printf "%-28s  %9s  %9s  %9s  %9s  %9s    %-35s %15s  %-16s  %-3s\n", datetime, pctUser, pctNice, pctSystem, pctIowait, pctIdle, OSName, OS_version, IP_address,cpu}
    } else if (cpu ~ last_cpu) {
        {printf "%-28s  %9s  %9s  %9s  %9s  %9s    %-35s %15s  %-16s  %-3s\n", datetime, pctUser, pctNice, pctSystem, pctIowait, pctIdle, OSName, OS_version, IP_address,cpu}
        printf "%-28s  %9s  %9s  %9s  %9s  %9s    %-35s %15s  %-16s  %-3s\n", datetime, user_sum / cpu_count, pctNice, system_sum / cpu_count, iowait_sum / cpu_count, idle_sum / cpu_count, OSName, OS_version, IP_address, "all";
        cpu_processed = 0;
        user_sum = system_sum = iowait_sum = idle_sum = 0;
    }else{
        {printf "%-28s  %9s  %9s  %9s  %9s  %9s    %-35s %15s  %-16s  %-3s\n", datetime, pctUser, pctNice, pctSystem, pctIowait, pctIdle, OSName, OS_version, IP_address,cpu}
    }
    }'
    $CMD | tee "$TEE_DEST" | $AWK $DEFINE "$FILTER $FORMAT $FILL_DIMENSIONS $PRINTF" header="$HEADER"
    echo "Cmd = [$CMD];  | $AWK $DEFINE '$FILTER $FORMAT $FILL_DIMENSIONS $PRINTF' header=\"$HEADER\"" >>"$TEE_DEST"
    exit
elif [ "$KERNEL" = "AIX" ] ; then
    queryHaveCommand mpstat
    queryHaveCommand lparstat
    FOUND_MPSTAT=$?
    FOUND_LPARSTAT=$?
    DEFINE="-v OSName=$(uname -s) -v OSVersion=$(oslevel -r |  cut -d'-' -f1) -v IP_address=$(ifconfig -a | grep 'inet ' | grep -v 127.0.0.1 | cut -d\  -f2 | head -n 1)"
    if [ $FOUND_MPSTAT -eq 0 ] && [ $FOUND_LPARSTAT -eq 0 ] ; then
        # Get extra fields from lparstat
        COUNT=$(lparstat | grep " app" | wc -l)
        if [ $COUNT -gt 0 ] ; then
            # Fetch value from "app" column of lparstat output
            FETCH_APP_COL_NUM='BEGIN {app_col_num = 8}
            {
                if($0 ~ /System configuration|^$/) {next}
                if($0 ~ / app/)
                {
                    for(i=1; i<=NF; i++)
                    {
                        if($i == "app")
                        {
                            app_col_num = i;
                            break;
                        }
                    }
                    print app_col_num;
                    exit 0;
                }
            }'
            APP_COL_NUM=$(lparstat | awk "$FETCH_APP_COL_NUM")
            CPUPool=$(lparstat | tail -1 | awk -v APP_COL_NUM=$APP_COL_NUM -F " " '{print $APP_COL_NUM}')
        else
            CPUPool=0
        fi
        # Fetch other required fields from lparstat output
        OnlineVirtualCPUs=$(lparstat -i | grep "Online Virtual CPUs" | awk -F " " '{print $NF}')
        EntitledCapacity=$(lparstat -i | grep "Entitled Capacity  " | awk -F " " '{print $NF}')
        DEFINE_LPARSTAT_FIELDS="-v CPUPool=$CPUPool -v OnlineVirtualCPUs=$OnlineVirtualCPUs -v EntitledCapacity=$EntitledCapacity"

        # Get cpu stats using mpstat command and manipulate the output for adding extra fields
        CMD='mpstat -a 2 5'
        # shellcheck disable=SC2016

        FORMAT='
        function get_current_time() {
            # Use "date" to fetch the current time and store it in a variable
            command = "date +\"%m/%d/%y_%H:%M:%S_%Z\"";
            command | getline datetime;
            close(command);
            return datetime;
        }
        $1 ~ /^-+$/ { next }
        BEGIN {flag = 0}
        {
            if($0 ~ /System configuration|^$/) {next}
            if($0 ~ /cpu / && flag == 1) {next}
            if(flag == 1)
            {
                for(i=NF+8; i>=8; i--)
                {
                    $i = $(i-7);
                }
                # Prepend Datetime, OSName, OS_version, IP_address values
                $1 = get_current_time();
                $2 = OSName;
                $3 = OSVersion/1000;
                $4 = IP_address;
                # Prepend lparstat field values
                if($0 ~ /ALL/)
                {
                    $5 = CPUPool;
                    $6 = OnlineVirtualCPUs;
                    $7 = EntitledCapacity;
                }
                else
                {
                    $5 = "-";
                    $6 = "-";
                    $7 = "-";
                }
            }
            if($0 ~ /cpu /)
            {
                for(i=NF+8; i>=8; i--)
                {
                    $i = $(i-7);
                }
                # Prepend Datetime, OSName, OS_version, IP_address headers
                $1 = "Datetime";
                $2 = "OSName";
                $3 = "OS_version";
                $4 = "IP_address";
                # Prepend lparstat field headers
                $5 = "CPUPool";
                $6 = "OnlineVirtualCPUs";
                $7 = "EntitledCapacity";
                flag = 1;
            }
            printf $1;
            for(i=2; i<=NF; i++)
            {
                printf "%17s ", $i;
            }
            print "";
        }'
    fi
    $CMD | tee "$TEE_DEST" | $AWK $DEFINE $DEFINE_LPARSTAT_FIELDS "$FORMAT $FILL_DIMENSIONS"
    echo "Cmd = [$CMD];  | $AWK $DEFINE $DEFINE_LPARSTAT_FIELDS '$FORMAT $FILL_DIMENSIONS'" >>"$TEE_DEST"
    exit
elif [ "$KERNEL" = "Darwin" ] ; then
    HEADER='Datetime                        pctUser  pctSystem    pctIdle    OSName                                   OS_version  IP_address        CPU'
    HEADERIZE="BEGIN {print \"$HEADER\"}"
    PRINTF='{printf "%-28s  %9s  %9s  %9s    %-35s %15s  %-16s  %-3s\n", datetime, pctUser, pctSystem, pctIdle, OSName, OS_version, IP_address, cpu}'
    # top command here is used to get a single instance of cpu metrics
    CMD='top -l 5 -s 2'
    assertHaveCommand "$CMD"
    # FILTER here skips all the rows that doesn't match "CPU".
    # shellcheck disable=SC2016
    FILTER='($1 !~ "CPU") {next;}'

    DEFINE="-v OSName=$(uname -s) -v OS_version=$(uname -r) -v IP_address=$(ifconfig -a | grep 'inet ' | grep -v 127.0.0.1 | cut -d\  -f2 | head -n 1)"
    # FORMAT here removes '%'in the end of the metrics.
    # shellcheck disable=SC2016
    FORMAT='
    function get_current_time() {
        # Use "date" to fetch the current time and store it in a variable
        command = "date +\"%m/%d/%y_%H:%M:%S_%Z\"";
        command | getline datetime;
        close(command);
        return datetime;
    }
    function remove_char(string, char_to_remove) {
        sub(char_to_remove, "", string);
        return string;
    }
    {
        datetime=get_current_time();
        cpu="all";
        pctUser = remove_char($3, "%");
        pctSystem = remove_char($5, "%");
        pctIdle = remove_char($7, "%");
        OSName=OSName;
        OS_version=OS_version;
        IP_address=IP_address;
    }'
elif [ "$KERNEL" = "FreeBSD" ] ; then
    formatted_date=$(date +"%m/%d/%y_%H:%M:%S_%Z")
    CMD='eval top -P -d2 c; top -d2 c'
    assertHaveCommand "$CMD"
    # shellcheck disable=SC2016
    FILTER='($1 !~ "CPU") { next; }'
    # shellcheck disable=SC2016
    DEFINE="-v OSName=$(uname -s) -v OS_version=$(uname -r) -v IP_address=$(ifconfig -a | grep 'inet ' | grep -v 127.0.0.1 | cut -d\  -f2 | head -n 1)"
    # shellcheck disable=SC2016
    FORMAT='function remove_char(string, char_to_remove) {
				sub(char_to_remove, "", string);
				return string;
			}
            {
             datetime="'"$formatted_date"'";
            }
			{
				if ($1 == "CPU:") {
					cpu = "all";
				} else {
					cpu = remove_char($2, ":");
				}
			}
			{
				pctUser = remove_char($(NF-9), "%");
				pctNice = remove_char($(NF-7), "%");
				pctSystem = remove_char($(NF-5), "%");
				pctIdle = remove_char($(NF-1), "%");
				pctIowait = "0.0";
                OSName=OSName;
                OS_version=OS_version;
                IP_address=IP_address;
			}'
fi
# shellcheck disable=SC2086
$CMD | tee "$TEE_DEST" | $AWK $DEFINE "$HEADERIZE $FILTER $FORMAT $FILL_DIMENSIONS $PRINTF" header="$HEADER"
echo "Cmd = [$CMD];  | $AWK $DEFINE '$HEADERIZE $FILTER $FORMAT $FILL_DIMENSIONS $PRINTF' header=\"$HEADER\"" >>"$TEE_DEST"
