#!/bin/sh
# SPDX-FileCopyrightText: 2024 Splunk, Inc.
# SPDX-License-Identifier: Apache-2.0

# shellcheck disable=SC1091
. "$(dirname "$0")"/common.sh

PRINTF='END {printf "%s %s %s %s %s %s %s %s %s\n", DATE, MACH_HW_NAME, MACH_ARCH_NAME, OS_REL, OS_NAME, OS_VER, KERNEL_NAME, KERNEL_VERSION, KERNEL_RELEASE}'


if [ "$KERNEL" = "Linux" ] || [ "$KERNEL" = "SunOS" ] || [ "$KERNEL" = "FreeBSD" ] ; then
	assertHaveCommand date
	assertHaveCommand uname
	VERSION=$(grep "^VERSION=" /etc/*-release | cut -d= -f2 | sed 's/^["]*//;s/["]*$//' | paste -sd " " -)
	NAME=$(grep "^NAME=" /etc/*-release | cut -d= -f2 | sed 's/^["]*//;s/["]*$//' | paste -sd " " -)
	VERSION_ID=$(grep "^VERSION_ID=" /etc/*-release | cut -d= -f2 | sed 's/^["]*//;s/["]*$//' | paste -sd " " -)
	CMD="eval date ; eval uname -m ; echo \"$VERSION\" ; echo \"$NAME\" ; echo \"$VERSION_ID\" ; eval uname -p ; eval uname -s ; eval uname -v ; eval uname -r"
elif [ "$KERNEL" = "Darwin" ] ; then
  # Darwin-macos uses sw_vers for os version, name and release switch.
	assertHaveCommand date
	assertHaveCommand uname
	VERSION=$(sw_vers -BuildVersion)
	NAME=$(sw_vers -productName)
	VERSION_ID=$(sw_vers -ProductVersion)
	CMD="eval date ; eval uname -m ; echo \"$VERSION_ID ($VERSION)\" ; echo \"$NAME\" ; echo \"$VERSION_ID\" ; eval uname -p ; eval uname -s ; eval uname -v ; eval uname -r"
elif [ "$KERNEL" = "HP-UX" ] ; then
	# HP-UX lacks -p switch.
	assertHaveCommand date
	assertHaveCommand uname
	CMD='eval date ; eval uname -m ; eval uname -r ; eval uname -s ; eval uname -v'
elif [ "$KERNEL" = "AIX" ] ; then
	# AIX uses oslevel for version and release switch.
	assertHaveCommand date
	assertHaveCommand uname
	CMD='eval date ; eval uname -m ; eval oslevel -r ; eval uname -s ; eval oslevel ; eval uname -m ; eval uname -s ; eval uname -v; eval uname -r'
fi

# Get the date.
# shellcheck disable=SC2016
PARSE_0='NR==1 {DATE=$0}'
# shellcheck disable=SC2016
PARSE_1='NR==2 {MACH_HW_NAME="machine_hardware_name=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_2='NR==3 {OS_REL="os_release=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_3='NR==4 {OS_NAME="os_name=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_4='NR==5 {OS_VER="os_version=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_5='NR==6 {MACH_ARCH_NAME="machine_architecture_name=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_6='NR==7 {KERNEL_NAME="kernel_name=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_7='NR==8 {KERNEL_VERSION="kernel_version=\"" $0 "\""}'
# shellcheck disable=SC2016
PARSE_8='NR==9 {KERNEL_RELEASE="kernel_release=\"" $0 "\""}'

MASSAGE="$PARSE_0 $PARSE_1 $PARSE_2 $PARSE_3 $PARSE_4 $PARSE_5 $PARSE_6 $PARSE_7 $PARSE_8"

$CMD | tee "$TEE_DEST" | $AWK "$MASSAGE $PRINTF"
echo "Cmd = [$CMD];  | $AWK '$MASSAGE $PRINTF'" >> "$TEE_DEST"
