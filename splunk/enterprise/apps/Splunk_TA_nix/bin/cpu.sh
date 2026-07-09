#!/bin/sh
# SPDX-FileCopyrightText: 2024 Splunk, Inc.
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC1091
. "$(dirname "$0")"/common.sh

HEADER='Datetime                     CPU    pctUser    pctNice  pctSystem  pctIowait    pctIdle'
HEADERIZE="BEGIN {print \"$HEADER\"}"
PRINTF='{printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, cpu, pctUser, pctNice, pctSystem, pctIowait, pctIdle}'

if [ "$KERNEL" = "Linux" ] ; then
    queryHaveCommand sar
    FOUND_SAR=$?
    queryHaveCommand mpstat
    FOUND_MPSTAT=$?
    if [ $FOUND_SAR -eq 0 ] ; then
        CMD='sar -P ALL 2 5'
        # shellcheck disable=SC2016
        FORMAT='{datetime = strftime("%m/%d/%y_%H:%M:%S_%Z"); cpu=$(NF-6); pctUser=$(NF-5); pctNice=$(NF-4); pctSystem=$(NF-3); pctIowait=$(NF-2); pctIdle=$NF}'
    elif [ $FOUND_MPSTAT -eq 0 ] ; then
        CMD='mpstat -P ALL 2 5'
        # shellcheck disable=SC2016
        FORMAT='{datetime = strftime("%m/%d/%y_%H:%M:%S_%Z"); cpu=$(NFIELDS-10); pctUser=$(NFIELDS-9); pctNice=$(NFIELDS-8); pctSystem=$(NFIELDS-7); pctIowait=$(NFIELDS-6); pctIdle=$NF}'
    else
        failLackMultipleCommands sar mpstat
    fi
    # shellcheck disable=SC2016
    FILTER='($0 ~ /CPU/) { if($(NF-1) ~ /gnice/){  NFIELDS=NF; } else {NFIELDS=NF+1;} next} /Average|Linux|^$|%/ {next}'

    PRINTF='{
    if ($0 ~ /all/) {
        print header;
        printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, cpu, pctUser, pctNice, pctSystem, pctIowait, pctIdle;
    } else {
        printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, cpu, pctUser, pctNice, pctSystem, pctIowait, pctIdle;
    }
    }'
    $CMD | tee "$TEE_DEST" | $AWK "$FILTER $FORMAT $PRINTF"  header="$HEADER"
    echo "Cmd = [$CMD];  | $AWK '$FILTER $FORMAT $PRINTF' header=\"$HEADER\"" >> "$TEE_DEST"
    exit
elif [ "$KERNEL" = "SunOS" ] ; then
    CMD='mpstat -p 2 5'
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
        printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, cpu, pctUser, pctNice, pctSystem, pctIowait, pctIdle;
    } else if (cpu ~ last_cpu) {
        printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, cpu, pctUser, pctNice, pctSystem, pctIowait, pctIdle;
        printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, "all", user_sum / cpu_count, pctNice, system_sum / cpu_count, iowait_sum / cpu_count, idle_sum / cpu_count;
        cpu_processed = 0;
        user_sum = system_sum = iowait_sum = idle_sum = 0;
    }else{
        printf "%-28s %-3s  %9s  %9s  %9s  %9s  %9s\n", datetime, cpu, pctUser, pctNice, pctSystem, pctIowait, pctIdle;
    }
    }'
    $CMD | tee "$TEE_DEST" | $AWK "$FILTER $FORMAT $PRINTF"  header="$HEADER"
    echo "Cmd = [$CMD];  | $AWK '$FILTER $FORMAT $PRINTF' header=\"$HEADER\"" >> "$TEE_DEST"
    exit

elif [ "$KERNEL" = "AIX" ] ; then
    queryHaveCommand mpstat
    queryHaveCommand lparstat
    FOUND_MPSTAT=$?
    FOUND_LPARSTAT=$?
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
        DEFINE="-v CPUPool=$CPUPool -v OnlineVirtualCPUs=$OnlineVirtualCPUs -v EntitledCapacity=$EntitledCapacity"

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
        BEGIN {
            flag = 0;
            header = "";
        }
        {
            if($0 ~ /System configuration|^$/) {next}
            if($1 ~ /^-+$/ && header != "") {
                print header;
                next;
            }
            if($0 ~ /cpu / && flag == 1) {next}
            if(flag == 1)
            {
                # Prepend extra field values from lparstat
                for(i=NF+5; i>=5; i--)
                {
                    $i = $(i-4);
                }
                if($0 ~ /ALL/)
                {
                    $1 = get_current_time();
                    $2 = CPUPool;
                    $3 = OnlineVirtualCPUs;
                    $4 = EntitledCapacity;
                }
                else
                {
                    $1 = get_current_time();
                    $2 = "-";
                    $3 = "-";
                    $4 = "-";
                }
            }
            if($0 ~ /cpu /)
            {
                # Prepend extra field headers from lparstat
                for(i=NF+5; i>=5; i--)
                {
                    $i = $(i-4);
                }
                $1 = "Datetime";
                $2 = "CPUPool";
                $3 = "OnlineVirtualCPUs";
                $4 = "EntitledCapacity";
                flag = 1;

                header = $1;
                for (i = 2; i <= NF; i++) {
                    header = header sprintf("%21s ", $i);
                }
            }
            printf $1;
            for(i=2; i<=NF; i++)
            {
                printf "%21s ", $i;
            }
            print "";
        }'
    fi
    $CMD | tee "$TEE_DEST" | $AWK $DEFINE "$FORMAT"
    echo "Cmd = [$CMD];  | $AWK $DEFINE '$FORMAT'" >> "$TEE_DEST"
    exit
elif [ "$KERNEL" = "Darwin" ] ; then
    HEADER='Datetime                     CPU    pctUser  pctSystem    pctIdle'
    HEADERIZE="BEGIN {print \"$HEADER\"}"
    PRINTF='{printf "%-28s %-3s  %9s  %9s  %9s \n", datetime, cpu, pctUser, pctSystem, pctIdle}'
    # top command here is used to get a single instance of cpu metrics
    CMD='top -l 5 -s 2'
    assertHaveCommand "$CMD"
    # FILTER here skips all the rows that doesn't match "CPU".
    # shellcheck disable=SC2016
    FILTER='($1 !~ "CPU") {next;}'
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
        }'
    PRINTF='{
        print header;
        printf "%-28s %-3s  %9s  %9s  %9s \n", datetime, cpu, pctUser, pctSystem, pctIdle;
    }'

    $CMD | tee "$TEE_DEST" | $AWK "$FILTER $FORMAT $PRINTF" header="$HEADER"
    echo "Cmd = [$CMD]; | $AWK '$FILTER $FORMAT $PRINTF' header=\"$HEADER\"" >> "$TEE_DEST"
    exit
elif [ "$KERNEL" = "FreeBSD" ] ; then
    formatted_date=$(date +"%m/%d/%y_%H:%M:%S_%Z")
    CMD='eval top -P -d2 c; top -d2 c'
    assertHaveCommand "$CMD"
    # shellcheck disable=SC2016
    FILTER='($1 !~ "CPU") { next; }'
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
			}'
fi

$CMD | tee "$TEE_DEST" | $AWK "$HEADERIZE $FILTER $FORMAT $PRINTF"  header="$HEADER"
echo "Cmd = [$CMD];  | $AWK '$HEADERIZE $FILTER $FORMAT $PRINTF' header=\"$HEADER\"" >> "$TEE_DEST"
