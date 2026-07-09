#!/bin/bash
########################################################################
#
# Hardening config's for rhel10 based distro's.
#
# Used openscap to produce remediation shell scripts.
#
########################################################################
set -eux

################################################################################################
echo "Remediating: 'xccdf_org.ssgproject.content_rule_account_disable_post_pw_expiration'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q shadow-utils; then


var_account_disable_post_pw_expiration="35"
function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/default/useradd' '^INACTIVE' "$var_account_disable_post_pw_expiration" 'CCE-80954-1' '%s=%s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_logon_fail_delay'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q shadow-utils; then

# Set variables
var_accounts_fail_delay="4"
function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/login.defs' '^FAIL_DELAY' "$var_accounts_fail_delay" 'CCE-84037-1' '%s %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_max_concurrent_login_sessions'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_accounts_max_concurrent_login_sessions="10"

if grep -q '^[^#]*\<maxlogins\>' /etc/security/limits.d/*.conf; then
	sed -i "/^[^#]*\<maxlogins\>/ s/maxlogins.*/maxlogins $var_accounts_max_concurrent_login_sessions/" /etc/security/limits.d/*.conf
elif grep -q '^[^#]*\<maxlogins\>' /etc/security/limits.conf; then
	sed -i "/^[^#]*\<maxlogins\>/ s/maxlogins.*/maxlogins $var_accounts_max_concurrent_login_sessions/" /etc/security/limits.conf
else
	echo "*	hard	maxlogins	$var_accounts_max_concurrent_login_sessions" >> /etc/security/limits.conf
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_maximum_age_login_defs'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q shadow-utils; then

var_accounts_maximum_age_login_defs="60"

grep -q ^PASS_MAX_DAYS /etc/login.defs && \
  sed -i "s/PASS_MAX_DAYS.*/PASS_MAX_DAYS     $var_accounts_maximum_age_login_defs/g" /etc/login.defs
if ! [ $? -eq 0 ]; then
    echo "PASS_MAX_DAYS      $var_accounts_maximum_age_login_defs" >> /etc/login.defs
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_minimum_age_login_defs'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q shadow-utils; then

var_accounts_minimum_age_login_defs="1"

grep -q ^PASS_MIN_DAYS /etc/login.defs && \
  sed -i "s/PASS_MIN_DAYS.*/PASS_MIN_DAYS     $var_accounts_minimum_age_login_defs/g" /etc/login.defs
if ! [ $? -eq 0 ]; then
    echo "PASS_MIN_DAYS      $var_accounts_minimum_age_login_defs" >> /etc/login.defs
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_minlen_login_defs'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q shadow-utils; then

var_accounts_password_minlen_login_defs="15"

grep -q ^PASS_MIN_LEN /etc/login.defs && \
sed -i "s/PASS_MIN_LEN.*/PASS_MIN_LEN\t$var_accounts_password_minlen_login_defs/g" /etc/login.defs
if ! [ $? -eq 0 ]
then
  echo -e "PASS_MIN_LEN\t$var_accounts_password_minlen_login_defs" >> /etc/login.defs
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_dcredit'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_dcredit="-1"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^dcredit' $var_password_pam_dcredit 'CCE-80653-9' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

if rpm --quiet -q pam; then

var_password_pam_dictcheck="1"

# Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
# Otherwise, regular sed command will do.
sed_command=('sed' '-i')
if test -L "/etc/security/pwquality.conf"; then
    sed_command+=('--follow-symlinks')
fi

# If the cce arg is empty, CCE is not assigned.
if [ -z "CCE-86233-4" ]; then
    cce="CCE"
else
    cce="CCE-86233-4"
fi

# Strip any search characters in the key arg so that the key can be replaced without
# adding any search characters to the config file.
stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "^dictcheck")

# shellcheck disable=SC2059
printf -v formatted_output "%s = %s" "$stripped_key" "$var_password_pam_dictcheck"

# If the key exists, change it. Otherwise, add it to the config_file.
# We search for the key string followed by a word boundary (matched by \>),
# so if we search for 'setting', 'setting2' won't match.
if LC_ALL=C grep -q -m 1 -i -e "^dictcheck\\>" "/etc/security/pwquality.conf"; then
    "${sed_command[@]}" "s/^dictcheck\\>.*/$formatted_output/gi" "/etc/security/pwquality.conf"
else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "/etc/security/pwquality.conf" >> "/etc/security/pwquality.conf"
    printf '%s\n' "$formatted_output" >> "/etc/security/pwquality.conf"
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_difok'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_difok="8"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^difok' $var_password_pam_difok 'CCE-80654-7' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_enforce_root'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

if [ -e "/etc/security/pwquality.conf" ] ; then

    LC_ALL=C sed -i "/^\s*enforce_for_root/Id" "/etc/security/pwquality.conf"
else
    touch "/etc/security/pwquality.conf"
fi
# make sure file has newline at the end
sed -i -e '$a\' "/etc/security/pwquality.conf"

cp "/etc/security/pwquality.conf" "/etc/security/pwquality.conf.bak"
# Insert at the end of the file
printf '%s\n' "" >> "/etc/security/pwquality.conf"
printf '%s\n' "# Per CCE-86356-3: Set enforce_for_root in /etc/security/pwquality.conf" >> "/etc/security/pwquality.conf"
printf '%s\n' "enforce_for_root" >> "/etc/security/pwquality.conf"
# Clean up after ourselves.
rm "/etc/security/pwquality.conf.bak"

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_lcredit'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_lcredit="-1"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^lcredit' $var_password_pam_lcredit 'CCE-80655-4' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_maxclassrepeat'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_maxclassrepeat="4"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^maxclassrepeat' $var_password_pam_maxclassrepeat 'CCE-81034-1' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_maxrepeat'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_maxrepeat="3"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^maxrepeat' $var_password_pam_maxrepeat 'CCE-82066-2' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_minclass'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_minclass="4"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^minclass' $var_password_pam_minclass 'CCE-82046-4' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_minlen'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_minlen="15"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^minlen' $var_password_pam_minlen 'CCE-80656-2' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_ocredit'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_ocredit="-1"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^ocredit' $var_password_pam_ocredit 'CCE-80663-8' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_pwhistory_remember_password_auth'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then


var_password_pam_remember="5"

var_password_pam_remember_control_flag="required"



pamFile="/etc/pam.d/password-auth"
# control required is for rhel8, while requisite is for other distros
CONTROL=${var_password_pam_remember_control_flag}

if [ ! -f $pamFile ]; then
	continue
fi

# is 'password required|requisite pam_pwhistory.so' here?
if grep -q "^password.*pam_pwhistory.so.*" $pamFile; then
	# is the remember option set?
	option=$(sed -rn 's/^(.*pam_pwhistory\.so.*)(remember=[0-9]+)(.*)$/\2/p' $pamFile)
	if [[ -z $option ]]; then
		# option is not set, append to module
		sed -i --follow-symlinks "/pam_pwhistory.so/ s/$/ remember=$var_password_pam_remember/"
	else
		# option is set, replace value
		sed -r -i --follow-symlinks "s/^(.*pam_pwhistory\.so.*)(remember=[0-9]+)(.*)$/\1remember=$var_password_pam_remember\3/" $pamFile
	fi
	# ensure corect control is being used per os requirement
	if ! grep -q "^password.*$CONTROL.*pam_pwhistory.so.*" $pamFile; then
		#replace incorrect value
		sed -r -i --follow-symlinks "s/(^password.*)(required|requisite)(.*pam_pwhistory\.so.*)$/\1$CONTROL\3/" $pamFile
	fi
else
	# no 'password required|requisite pam_pwhistory.so', add it
	sed -i --follow-symlinks "/^password.*pam_unix.so.*/i password $CONTROL pam_pwhistory.so use_authtok remember=$var_password_pam_remember" $pamFile
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_pwhistory_remember_system_auth'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_remember="5"

var_password_pam_remember_control_flag="required"

pamFile="/etc/pam.d/system-auth"
# control required is for rhel8, while requisite is for other distros
CONTROL=${var_password_pam_remember_control_flag}

if [ ! -f $pamFile ]; then
	continue
fi

# is 'password required|requisite pam_pwhistory.so' here?
if grep -q "^password.*pam_pwhistory.so.*" $pamFile; then
	# is the remember option set?
	option=$(sed -rn 's/^(.*pam_pwhistory\.so.*)(remember=[0-9]+)(.*)$/\2/p' $pamFile)
	if [[ -z $option ]]; then
		# option is not set, append to module
		sed -i --follow-symlinks "/pam_pwhistory.so/ s/$/ remember=$var_password_pam_remember/"
	else
		# option is set, replace value
		sed -r -i --follow-symlinks "s/^(.*pam_pwhistory\.so.*)(remember=[0-9]+)(.*)$/\1remember=$var_password_pam_remember\3/" $pamFile
	fi
	# ensure corect control is being used per os requirement
	if ! grep -q "^password.*$CONTROL.*pam_pwhistory.so.*" $pamFile; then
		#replace incorrect value
		sed -r -i --follow-symlinks "s/(^password.*)(required|requisite)(.*pam_pwhistory\.so.*)$/\1$CONTROL\3/" $pamFile
	fi
else
	# no 'password required|requisite pam_pwhistory.so', add it
	sed -i --follow-symlinks "/^password.*pam_unix.so.*/i password $CONTROL pam_pwhistory.so use_authtok remember=$var_password_pam_remember" $pamFile
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_ucredit'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_password_pam_ucredit="-1"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/security/pwquality.conf' '^ucredit' $var_password_pam_ucredit 'CCE-80665-3' '%s = %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_password_pam_unix_remember'"

var_password_pam_unix_remember="5"

AUTH_FILES[0]="/etc/pam.d/system-auth"
AUTH_FILES[1]="/etc/pam.d/password-auth"

for pamFile in "${AUTH_FILES[@]}"
do
	if grep -q "remember=" $pamFile; then
		sed -i --follow-symlinks "s/\(^password.*sufficient.*pam_unix.so.*\)\(\(remember *= *\)[^ $]*\)/\1remember=$var_password_pam_unix_remember/" $pamFile
	else
		sed -i --follow-symlinks "/^password[[:space:]]\+sufficient[[:space:]]\+pam_unix.so/ s/$/ remember=$var_password_pam_unix_remember/" $pamFile
	fi
done

################################################################################################

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

AUTH_FILES=("/etc/pam.d/system-auth" "/etc/pam.d/password-auth")

for pam_file in "${AUTH_FILES[@]}"
do
    # is auth required pam_faillock.so preauth present?
    if ! grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*$' "$pam_file" ; then
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/i auth        required      pam_faillock.so preauth silent' "$pam_file"
    fi

    # is auth default pam_faillock.so authfail present?
    if ! grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*$' "$pam_file" ; then
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/a auth        [success=ok new_authtok_reqd=ok ignore=ignore default=bad] pam_faillock.so authfail' "$pam_file"
    fi

    if ! grep -qE '^\s*account\s+required\s+pam_faillock\.so.*$' "$pam_file" ; then
        sed -E -i --follow-symlinks '/^\s*account\s*required\s*pam_unix.so/i account     required      pam_faillock.so' "$pam_file"
    fi
done

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_passwords_pam_faillock_deny'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_accounts_passwords_pam_faillock_deny='3'


if [ -f /usr/sbin/authconfig ]; then
    authconfig --enablefaillock --update
elif [ -f /usr/bin/authselect ]; then
    if authselect check; then
        authselect enable-feature with-faillock
        authselect apply-changes
    else
        echo "
authselect integrity check failed. Remediation aborted!
This remediation could not be applied because the authselect profile is not intact.
It is not recommended to manually edit the PAM files when authselect is available
In cases where the default authselect profile does not cover a specific demand, a custom authselect profile is recommended."
        false
    fi
fi

FAILLOCK_CONF="/etc/security/faillock.conf"
if [ -f $FAILLOCK_CONF ]; then
    if $(grep -q '^\s*deny\s*=' $FAILLOCK_CONF); then
        sed -i --follow-symlinks "s/^\s*\(deny\s*\)=.*$/\1 = $var_accounts_passwords_pam_faillock_deny/g" $FAILLOCK_CONF
    else
        echo "deny = $var_accounts_passwords_pam_faillock_deny" >> $FAILLOCK_CONF
    fi
else
    AUTH_FILES=("/etc/pam.d/system-auth" "/etc/pam.d/password-auth")

for pam_file in "${AUTH_FILES[@]}"
do
    # is auth required pam_faillock.so preauth present?
    if grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*$' "$pam_file" ; then
        # is the option set?
        if grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*'"deny"'=([0-9]*).*$' "$pam_file" ; then
            # just change the value of option to a correct value
            sed -i --follow-symlinks 's/\(^auth.*required.*pam_faillock.so.*preauth.*silent.*\)\('"deny"' *= *\).*/\1\2'"$var_accounts_passwords_pam_faillock_deny"'/' "$pam_file"
        # the option is not set.
        else
            # append the option
            sed -i --follow-symlinks '/^auth.*required.*pam_faillock.so.*preauth.*silent.*/ s/$/ '"deny"'='"$var_accounts_passwords_pam_faillock_deny"'/' "$pam_file"
        fi
    # auth required pam_faillock.so preauth is not present, insert the whole line
    else
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/i auth        required      pam_faillock.so preauth silent '"deny"'='"$var_accounts_passwords_pam_faillock_deny" "$pam_file"
    fi
    # is auth default pam_faillock.so authfail present?
    if grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*$' "$pam_file" ; then
        # is the option set?
        if grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*'"deny"'=([0-9]*).*$' "$pam_file" ; then
            # just change the value of option to a correct value
            sed -i --follow-symlinks 's/\(^auth.*[default=die].*pam_faillock.so.*authfail.*\)\('"deny"' *= *\).*/\1\2'"$var_accounts_passwords_pam_faillock_deny"'/' "$pam_file"
        # the option is not set.
        else
            # append the option
            sed -i --follow-symlinks '/^auth.*[default=die].*pam_faillock.so.*authfail.*/ s/$/ '"deny"'='"$var_accounts_passwords_pam_faillock_deny"'/' "$pam_file"
        fi
    # auth default pam_faillock.so authfail is not present, insert the whole line
    else
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/a auth        [default=die] pam_faillock.so authfail '"deny"'='"$var_accounts_passwords_pam_faillock_deny" "$pam_file"
    fi
    if ! grep -qE '^\s*account\s+required\s+pam_faillock\.so.*$' "$pam_file" ; then
        sed -E -i --follow-symlinks '/^\s*account\s*required\s*pam_unix.so/i account     required      pam_faillock.so' "$pam_file"
    fi
done
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_passwords_pam_faillock_deny_root'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

if [ -f /usr/sbin/authconfig ]; then
    authconfig --enablefaillock --update
elif [ -f /usr/bin/authselect ]; then
    if authselect check; then
        authselect enable-feature with-faillock
        authselect apply-changes
    else
        echo "
authselect integrity check failed. Remediation aborted!
This remediation could not be applied because the authselect profile is not intact.
It is not recommended to manually edit the PAM files when authselect is available
In cases where the default authselect profile does not cover a specific demand, a custom authselect profile is recommended."
        false
    fi
fi

FAILLOCK_CONF="/etc/security/faillock.conf"
if [ -f $FAILLOCK_CONF ]; then
    if [ ! $(grep -q '^\s*even_deny_root' $FAILLOCK_CONF) ]; then
        echo "even_deny_root" >> $FAILLOCK_CONF
    fi
else
    SYSTEM_AUTH="/etc/pam.d/system-auth"
    PASSWORD_AUTH="/etc/pam.d/password-auth"
    for file in $SYSTEM_AUTH $PASSWORD_AUTH; do
        if ! grep -q "^auth.*pam_faillock.so \(preauth silent\|authfail\).*even_deny_root" $file; then
			sed -i --follow-symlinks 's/\(pam_faillock.so \(preauth silent\|authfail\).*\)$/\1 even_deny_root/g' $file
		fi
    done
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_passwords_pam_faillock_interval'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_accounts_passwords_pam_faillock_fail_interval='900'


if [ -f /usr/sbin/authconfig ]; then
    authconfig --enablefaillock --update
elif [ -f /usr/bin/authselect ]; then
    if authselect check; then
        authselect enable-feature with-faillock
        authselect apply-changes
    else
        echo "
authselect integrity check failed. Remediation aborted!
This remediation could not be applied because the authselect profile is not intact.
It is not recommended to manually edit the PAM files when authselect is available
In cases where the default authselect profile does not cover a specific demand, a custom authselect profile is recommended."
        false
    fi
fi

FAILLOCK_CONF="/etc/security/faillock.conf"
if [ -f $FAILLOCK_CONF ]; then
    if $(grep -q '^\s*fail_interval\s*=' $FAILLOCK_CONF); then
        sed -i --follow-symlinks "s/^\s*\(fail_interval\s*\)=.*$/\1 = $var_accounts_passwords_pam_faillock_fail_interval/g" $FAILLOCK_CONF
    else
        echo "fail_interval = $var_accounts_passwords_pam_faillock_fail_interval" >> $FAILLOCK_CONF
    fi
else
    AUTH_FILES=("/etc/pam.d/system-auth" "/etc/pam.d/password-auth")

for pam_file in "${AUTH_FILES[@]}"
do
    # is auth required pam_faillock.so preauth present?
    if grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*$' "$pam_file" ; then
        # is the option set?
        if grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*'"fail_interval"'=([0-9]*).*$' "$pam_file" ; then
            # just change the value of option to a correct value
            sed -i --follow-symlinks 's/\(^auth.*required.*pam_faillock.so.*preauth.*silent.*\)\('"fail_interval"' *= *\).*/\1\2'"$var_accounts_passwords_pam_faillock_fail_interval"'/' "$pam_file"
        # the option is not set.
        else
            # append the option
            sed -i --follow-symlinks '/^auth.*required.*pam_faillock.so.*preauth.*silent.*/ s/$/ '"fail_interval"'='"$var_accounts_passwords_pam_faillock_fail_interval"'/' "$pam_file"
        fi
    # auth required pam_faillock.so preauth is not present, insert the whole line
    else
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/i auth        required      pam_faillock.so preauth silent '"fail_interval"'='"$var_accounts_passwords_pam_faillock_fail_interval" "$pam_file"
    fi
    # is auth default pam_faillock.so authfail present?
    if grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*$' "$pam_file" ; then
        # is the option set?
        if grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*'"fail_interval"'=([0-9]*).*$' "$pam_file" ; then
            # just change the value of option to a correct value
            sed -i --follow-symlinks 's/\(^auth.*[default=die].*pam_faillock.so.*authfail.*\)\('"fail_interval"' *= *\).*/\1\2'"$var_accounts_passwords_pam_faillock_fail_interval"'/' "$pam_file"
        # the option is not set.
        else
            # append the option
            sed -i --follow-symlinks '/^auth.*[default=die].*pam_faillock.so.*authfail.*/ s/$/ '"fail_interval"'='"$var_accounts_passwords_pam_faillock_fail_interval"'/' "$pam_file"
        fi
    # auth default pam_faillock.so authfail is not present, insert the whole line
    else
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/a auth        [default=die] pam_faillock.so authfail '"fail_interval"'='"$var_accounts_passwords_pam_faillock_fail_interval" "$pam_file"
    fi
    if ! grep -qE '^\s*account\s+required\s+pam_faillock\.so.*$' "$pam_file" ; then
        sed -E -i --follow-symlinks '/^\s*account\s*required\s*pam_unix.so/i account     required      pam_faillock.so' "$pam_file"
    fi
done
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_passwords_pam_faillock_unlock_time'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

var_accounts_passwords_pam_faillock_unlock_time='0'

if [ -f /usr/sbin/authconfig ]; then
    authconfig --enablefaillock --update
elif [ -f /usr/bin/authselect ]; then
    if authselect check; then
        authselect enable-feature with-faillock
        authselect apply-changes
    else
        echo "
authselect integrity check failed. Remediation aborted!
This remediation could not be applied because the authselect profile is not intact.
It is not recommended to manually edit the PAM files when authselect is available
In cases where the default authselect profile does not cover a specific demand, a custom authselect profile is recommended."
        false
    fi
fi

FAILLOCK_CONF="/etc/security/faillock.conf"
if [ -f $FAILLOCK_CONF ]; then
    if $(grep -q '^\s*unlock_time\s*=' $FAILLOCK_CONF); then
        sed -i --follow-symlinks "s/^\s*\(unlock_time\s*\)=.*$/\1 = $var_accounts_passwords_pam_faillock_unlock_time/g" $FAILLOCK_CONF
    else
        echo "unlock_time = $var_accounts_passwords_pam_faillock_unlock_time" >> $FAILLOCK_CONF
    fi
else
    AUTH_FILES=("/etc/pam.d/system-auth" "/etc/pam.d/password-auth")

for pam_file in "${AUTH_FILES[@]}"
do
    # is auth required pam_faillock.so preauth present?
    if grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*$' "$pam_file" ; then
        # is the option set?
        if grep -qE '^\s*auth\s+required\s+pam_faillock\.so\s+preauth.*'"unlock_time"'=([0-9]*).*$' "$pam_file" ; then
            # just change the value of option to a correct value
            sed -i --follow-symlinks 's/\(^auth.*required.*pam_faillock.so.*preauth.*silent.*\)\('"unlock_time"' *= *\).*/\1\2'"$var_accounts_passwords_pam_faillock_unlock_time"'/' "$pam_file"
        # the option is not set.
        else
            # append the option
            sed -i --follow-symlinks '/^auth.*required.*pam_faillock.so.*preauth.*silent.*/ s/$/ '"unlock_time"'='"$var_accounts_passwords_pam_faillock_unlock_time"'/' "$pam_file"
        fi
    # auth required pam_faillock.so preauth is not present, insert the whole line
    else
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/i auth        required      pam_faillock.so preauth silent '"unlock_time"'='"$var_accounts_passwords_pam_faillock_unlock_time" "$pam_file"
    fi
    # is auth default pam_faillock.so authfail present?
    if grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*$' "$pam_file" ; then
        # is the option set?
        if grep -qE '^\s*auth\s+(\[default=die\])\s+pam_faillock\.so\s+authfail.*'"unlock_time"'=([0-9]*).*$' "$pam_file" ; then
            # just change the value of option to a correct value
            sed -i --follow-symlinks 's/\(^auth.*[default=die].*pam_faillock.so.*authfail.*\)\('"unlock_time"' *= *\).*/\1\2'"$var_accounts_passwords_pam_faillock_unlock_time"'/' "$pam_file"
        # the option is not set.
        else
            # append the option
            sed -i --follow-symlinks '/^auth.*[default=die].*pam_faillock.so.*authfail.*/ s/$/ '"unlock_time"'='"$var_accounts_passwords_pam_faillock_unlock_time"'/' "$pam_file"
        fi
    # auth default pam_faillock.so authfail is not present, insert the whole line
    else
        sed -i --follow-symlinks '/^auth.*sufficient.*pam_unix.so.*/a auth        [default=die] pam_faillock.so authfail '"unlock_time"'='"$var_accounts_passwords_pam_faillock_unlock_time" "$pam_file"
    fi
    if ! grep -qE '^\s*account\s+required\s+pam_faillock\.so.*$' "$pam_file" ; then
        sed -E -i --follow-symlinks '/^\s*account\s*required\s*pam_unix.so/i account     required      pam_faillock.so' "$pam_file"
    fi
done
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_umask_etc_bashrc'"

var_accounts_user_umask="077"

grep -q umask /etc/bashrc && \
  sed -i "s/umask.*/umask $var_accounts_user_umask/g" /etc/bashrc
if ! [ $? -eq 0 ]; then
    echo "umask $var_accounts_user_umask" >> /etc/bashrc
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_umask_etc_csh_cshrc'"

var_accounts_user_umask='077'

grep -q umask /etc/csh.cshrc && \
  sed -i "s/umask.*/umask $var_accounts_user_umask/g" /etc/csh.cshrc
if ! [ $? -eq 0 ]; then
    echo "umask $var_accounts_user_umask" >> /etc/csh.cshrc
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_umask_etc_login_defs'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q shadow-utils; then

var_accounts_user_umask="077"

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/login.defs' '^UMASK' "$var_accounts_user_umask" 'CCE-82888-9' '%s %s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_accounts_umask_etc_profile'"

var_accounts_user_umask='077'

grep -q umask /etc/profile && \
  sed -i "s/umask.*/umask $var_accounts_user_umask/g" /etc/profile
if ! [ $? -eq 0 ]; then
    echo "umask $var_accounts_user_umask" >> /etc/profile
fi

################################################################################################

(>&2 echo "Remediating: 'xccdf_org.ssgproject.content_rule_banner_etc_issue'")

login_banner_text="(^You[\s\n]+are[\s\n]+accessing[\s\n]+a[\s\n]+Super[\s\n]+Cool[\s\n]+Container[\s\n]+![\s\n]$)"

# There was a regular-expression matching various banners, needs to be expanded
expanded=$(echo "$login_banner_text" | sed 's/(\\\\\x27)\*/\\\x27/g;s/(\\\x27)\*//g;s/(\^\(.*\)\$|.*$/\1/g;s/\[\\s\\n\][+*]/ /g;s/\\//g;s/[^-]- /\n\n-/g;s/(n)\**//g')
formatted=$(echo "$expanded" | fold -sw 80)

cat <<EOF >/etc/issue
$formatted
EOF

printf "\n" >> /etc/issue

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_configure_usbguard_auditbackend'"

if [ -e "/etc/usbguard/usbguard-daemon.conf" ] ; then

    LC_ALL=C sed -i "/^\s*AuditBackend=/d" "/etc/usbguard/usbguard-daemon.conf"
else
    touch "/etc/usbguard/usbguard-daemon.conf"
fi
cp "/etc/usbguard/usbguard-daemon.conf" "/etc/usbguard/usbguard-daemon.conf.bak"
# Insert at the end of the file
printf '%s\n' "AuditBackend=LinuxAudit" >> "/etc/usbguard/usbguard-daemon.conf"
# Clean up after ourselves.
rm "/etc/usbguard/usbguard-daemon.conf.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_coredump_disable_backtraces'"

if [ -e "/etc/systemd/coredump.conf" ] ; then

    LC_ALL=C sed -i "/^\s*ProcessSizeMax\s*=\s*/Id" "/etc/systemd/coredump.conf"
else
    touch "/etc/systemd/coredump.conf"
fi
cp "/etc/systemd/coredump.conf" "/etc/systemd/coredump.conf.bak"
# Insert at the end of the file
printf '%s\n' "ProcessSizeMax=0" >> "/etc/systemd/coredump.conf"
# Clean up after ourselves.
rm "/etc/systemd/coredump.conf.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_coredump_disable_storage'"

if [ -e "/etc/systemd/coredump.conf" ] ; then

    LC_ALL=C sed -i "/^\s*Storage\s*=\s*/Id" "/etc/systemd/coredump.conf"
else
    touch "/etc/systemd/coredump.conf"
fi
cp "/etc/systemd/coredump.conf" "/etc/systemd/coredump.conf.bak"
# Insert at the end of the file
printf '%s\n' "Storage=none" >> "/etc/systemd/coredump.conf"
# Clean up after ourselves.
rm "/etc/systemd/coredump.conf.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_disable_ctrlaltdel_burstaction'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q systemd; then

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/systemd/system.conf' '^CtrlAltDelBurstAction=' 'none' 'CCE-80784-2' '%s=%s'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_disable_users_coredumps'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

SECURITY_LIMITS_FILE="/etc/security/limits.conf"

if grep -qE '\*\s+hard\s+core' $SECURITY_LIMITS_FILE; then
        sed -ri 's/(hard\s+core\s+)[[:digit:]]+/\1 0/' $SECURITY_LIMITS_FILE
else
        echo "*     hard   core    0" >> $SECURITY_LIMITS_FILE
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_display_login_attempts'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

function ensure_pam_module_options {
	if [ $# -lt 7 ] || [ $# -gt 8 ] ; then
                echo "$0 requires seven or eight arguments" >&2
                exit 1
        fi
	local _pamFile="$1" _type="$2" _control="$3" _module="$4" _option="$5" _valueRegex="$6" _defaultValue="$7"
	local _remove_argument=""
	if [ $# -eq 8 ] ; then
        	_remove_argument="$8"
		# convert it to lowercase
		_remove_argument=${_remove_argument,,}
	fi

	# make sure that we have a line like this in ${_pamFile} (additional options are left as-is):
	# ${_type} ${_control} ${_module} ${_option}=${_valueRegex}

	if ! [ -e "$_pamFile" ] ; then
		echo "$_pamFile doesn't exist" >&2
		exit 1
	fi

	# if remove argument only
	if [ "${_remove_argument}" = "yes" -o "${_remove_argument}" = "true" ] ; then
		sed --follow-symlinks -i -E -e "s/^(\\s*${_type}\\s+\\S+\\s+${_module}(\\s.+)?)\\s${_option}(=\\S+)?/\\1/" "${_pamFile}"
		exit 0
	fi

	# non-empty values need to be preceded by an equals sign
	[ -n "${_valueRegex}" ] && _valueRegex="=${_valueRegex}"
	# add an equals sign to non-empty values
	[ -n "${_defaultValue}" ] && _defaultValue="=${_defaultValue}"

	# fix 'type' if it's wrong
	if grep -q -P "^\\s*(?"'!'"${_type}\\s)[[:alnum:]]+\\s+[[:alnum:]]+\\s+${_module}" < "${_pamFile}" ; then
		sed --follow-symlinks -i -E -e "s/^(\\s*)[[:alnum:]]+(\\s+[[:alnum:]]+\\s+${_module})/\\1${_type}\\2/" "${_pamFile}"
	fi

	# fix 'control' if it's wrong
	if grep -q -P "^\\s*${_type}\\s+(?"'!'"${_control})[[:alnum:]]+\\s+${_module}" < "${_pamFile}" ; then
		sed --follow-symlinks -i -E -e "s/^(\\s*${_type}\\s+)[[:alnum:]]+(\\s+${_module})/\\1${_control}\\2/" "${_pamFile}"
	fi

	# fix the value for 'option' if one exists but does not match '_valueRegex'
    if grep -q -P "^\\s*${_type}\\s+${_control}\\s+${_module}(\\s.+)?\\s+${_option}(?"'!'"${_valueRegex}(\\s|\$))" < "${_pamFile}" ; then
		sed --follow-symlinks -i -E -e "s/^(\\s*${_type}\\s+${_control}\\s+${_module}(\\s.+)?\\s)${_option}=[^[:space:]]*/\\1${_option}${_defaultValue}/" "${_pamFile}"

    # add 'option=default' if option is not set
	elif grep -q -E "^\\s*${_type}\\s+${_control}\\s+${_module}" < "${_pamFile}" &&
         grep    -E "^\\s*${_type}\\s+${_control}\\s+${_module}" < "${_pamFile}" | grep -q -E -v "\\s${_option}(=|\\s|\$)" ; then

		sed --follow-symlinks -i -E -e "s/^(\\s*${_type}\\s+${_control}\\s+${_module}[^\\n]*)/\\1 ${_option}${_defaultValue}/" "${_pamFile}"
	# add a new entry if none exists
	elif ! grep -q -P "^\\s*${_type}\\s+${_control}\\s+${_module}(\\s.+)?\\s+${_option}${_valueRegex}(\\s|\$)" < "${_pamFile}" ; then
		echo "${_type} ${_control} ${_module} ${_option}${_defaultValue}" >> "${_pamFile}"
	fi
}
ensure_pam_module_options '/etc/pam.d/postlogin' 'session' 'required' 'pam_lastlog.so' 'showfailed' "" ""

# remove 'silent' option
sed -i --follow-symlinks -E -e 's/^([^#]+pam_lastlog\.so[^#]*)\ssilent/\1/' '/etc/pam.d/postlogin'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_ensure_gpgcheck_local_packages'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q dnf; then

function replace_or_append {
  local default_format='%s = %s' case_insensitive_mode=yes sed_case_insensitive_option='' grep_case_insensitive_option=''
  local config_file=$1
  local key=$2
  local value=$3
  local cce=$4
  local format=$5

  if [ "$case_insensitive_mode" = yes ]; then
    sed_case_insensitive_option="i"
    grep_case_insensitive_option="-i"
  fi
  [ -n "$format" ] || format="$default_format"
  # Check sanity of the input
  [ $# -ge "3" ] || { echo "Usage: replace_or_append <config_file_location> <key_to_search> <new_value> [<CCE number or literal '@CCENUM@' if unknown>] [printf-like format, default is '$default_format']" >&2; exit 1; }

  # Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
  # Otherwise, regular sed command will do.
  sed_command=('sed' '-i')
  if test -L "$config_file"; then
    sed_command+=('--follow-symlinks')
  fi

  # Test that the cce arg is not empty or does not equal @CCENUM@.
  # If @CCENUM@ exists, it means that there is no CCE assigned.
  if [ -n "$cce" ] && [ "$cce" != '@CCENUM@' ]; then
    cce="${cce}"
  else
    cce="CCE"
  fi

  # Strip any search characters in the key arg so that the key can be replaced without
  # adding any search characters to the config file.
  stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "$key")

  # shellcheck disable=SC2059
  printf -v formatted_output "$format" "$stripped_key" "$value"

  # If the key exists, change it. Otherwise, add it to the config_file.
  # We search for the key string followed by a word boundary (matched by \>),
  # so if we search for 'setting', 'setting2' won't match.
  if LC_ALL=C grep -q -m 1 $grep_case_insensitive_option -e "${key}\\>" "$config_file"; then
    "${sed_command[@]}" "s/${key}\\>.*/$formatted_output/g$sed_case_insensitive_option" "$config_file"
  else
    # \n is precaution for case where file ends without trailing newline
    printf '\n# Per %s: Set %s in %s\n' "$cce" "$formatted_output" "$config_file" >> "$config_file"
    printf '%s\n' "$formatted_output" >> "$config_file"
  fi
}
replace_or_append '/etc/dnf.conf' '^localpkg_gpgcheck' '1' 'CCE-80791-7'

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_harden_sshd_ciphers_openssh_conf_crypto_policy'"

sshd_approved_ciphers='aes256-ctr,aes192-ctr,aes128-ctr'

if [ -e "/etc/crypto-policies/back-ends/openssh.config" ] ; then

    LC_ALL=C sed --follow-symlinks -i "/^.*Ciphers\s\+/d" "/etc/crypto-policies/back-ends/openssh.config"
else
    touch "/etc/crypto-policies/back-ends/openssh.config"
fi
# make sure file has newline at the end
sed --follow-symlinks -i -e '$a\' "/etc/crypto-policies/back-ends/openssh.config"

cp "/etc/crypto-policies/back-ends/openssh.config" "/etc/crypto-policies/back-ends/openssh.config.bak"
# Insert at the end of the file
printf '%s\n' "Ciphers ${sshd_approved_ciphers}" >> "/etc/crypto-policies/back-ends/openssh.config"
# Clean up after ourselves.
rm "/etc/crypto-policies/back-ends/openssh.config.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_harden_sshd_ciphers_opensshserver_conf_crypto_policy'"

sshd_approved_ciphers='aes256-ctr,aes192-ctr,aes128-ctr'

CONF_FILE=/etc/crypto-policies/back-ends/opensshserver.config
correct_value="-oCiphers=${sshd_approved_ciphers}"

# Test if file exists
test -f ${CONF_FILE} || touch ${CONF_FILE}

# Ensure CRYPTO_POLICY is not commented out
sed --follow-symlinks -i 's/#CRYPTO_POLICY=/CRYPTO_POLICY=/' ${CONF_FILE}

grep -q "'${correct_value}'" ${CONF_FILE}

if [[ $? -ne 0 ]]; then
    # We need to get the existing value, using PCRE to maintain same regex
    existing_value=$(grep -Po '(-oCiphers=\S+)' ${CONF_FILE})

    if [[ ! -z ${existing_value} ]]; then
        # replace existing_value with correct_value
        sed --follow-symlinks -i "s/${existing_value}/${correct_value}/g" ${CONF_FILE}
    else
        # ***NOTE*** #
        # This probably means this file is not here or it's been modified
        # unintentionally.
        # ********** #
        # echo correct_value to end
        echo "CRYPTO_POLICY='${correct_value}'" >> ${CONF_FILE}
    fi
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_harden_sshd_macs_openssh_conf_crypto_policy'"

sshd_approved_macs='hmac-sha2-512,hmac-sha2-256'

if [ -e "/etc/crypto-policies/back-ends/openssh.config" ] ; then

    LC_ALL=C sed --follow-symlinks -i "/^.*MACs\s\+/d" "/etc/crypto-policies/back-ends/openssh.config"
else
    touch "/etc/crypto-policies/back-ends/openssh.config"
fi
# make sure file has newline at the end
sed --follow-symlinks -i -e '$a\' "/etc/crypto-policies/back-ends/openssh.config"

cp "/etc/crypto-policies/back-ends/openssh.config" "/etc/crypto-policies/back-ends/openssh.config.bak"
# Insert at the end of the file
printf '%s\n' "MACs ${sshd_approved_macs}" >> "/etc/crypto-policies/back-ends/openssh.config"
# Clean up after ourselves.
rm "/etc/crypto-policies/back-ends/openssh.config.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_harden_sshd_macs_opensshserver_conf_crypto_policy'"

sshd_approved_macs='hmac-sha2-512,hmac-sha2-256'

CONF_FILE=/etc/crypto-policies/back-ends/opensshserver.config
correct_value="-oMACs=${sshd_approved_macs}"

# Test if file exists
test -f ${CONF_FILE} || touch ${CONF_FILE}

# Ensure CRYPTO_POLICY is not commented out
sed --follow-symlinks -i 's/#CRYPTO_POLICY=/CRYPTO_POLICY=/' ${CONF_FILE}

grep -q "'${correct_value}'" ${CONF_FILE}

if [[ $? -ne 0 ]]; then
    # We need to get the existing value, using PCRE to maintain same regex
    existing_value=$(grep -Po '(-oMACs=\S+)' ${CONF_FILE})

    if [[ ! -z ${existing_value} ]]; then
        # replace existing_value with correct_value
        sed --follow-symlinks -i "s/${existing_value}/${correct_value}/g" ${CONF_FILE}
    else
        # ***NOTE*** #
        # This probably means this file is not here or it's been modified
        # unintentionally.
        # ********** #
        # echo correct_value to end
        echo "CRYPTO_POLICY='${correct_value}'" >> ${CONF_FILE}
    fi
fi

################################################################################################

touch /etc/modprobe.d/blacklist.conf
echo "install atm /bin/true" >> /etc/modprobe.d/blacklist.conf
echo "blacklist atm" >> /etc/modprobe.d/blacklist.conf

echo "install can /bin/true" >> /etc/modprobe.d/blacklist.conf
echo "blacklist can" >> /etc/modprobe.d/blacklist.conf

echo "install cramfs /bin/true" >> /etc/modprobe.d/blacklist.conf
echo "blacklist cramfs" >> /etc/modprobe.d/blacklist.conf

echo "install firewire-core /bin/true" >> /etc/modprobe.d/blacklist.conf
echo "blacklist firewire-core" >> /etc/modprobe.d/blacklist.conf

echo "install sctp /bin/true" >> /etc/modprobe.d/blacklist.conf
echo "blacklist sctp" >> /etc/modprobe.d/blacklist.conf

echo "install tipc /bin/true" >> /etc/modprobe.d/blacklist.conf
echo "blacklist tipc" >> /etc/modprobe.d/blacklist.conf

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_no_empty_passwords'"
sed --follow-symlinks -i 's/\<nullok\>//g' /etc/pam.d/system-auth
sed --follow-symlinks -i 's/\<nullok\>//g' /etc/pam.d/password-auth

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_openssl_use_strong_entropy'"

tee -a /etc/profile.d/openssl-rand.sh <<\EOF
# provide a default -rand /dev/random option to openssl commands that
# support it

# written inefficiently for maximum shell compatibility
openssl()
(
  openssl_bin=/usr/bin/openssl

  case "$*" in
    # if user specified -rand, honor it
    *\ -rand\ *|*\ -help*) exec $openssl_bin "$@" ;;
  esac

  cmds=`$openssl_bin list -digest-commands -cipher-commands | tr '\n' ' '`
  for i in `$openssl_bin list -commands`; do
    if $openssl_bin list -options "$i" | grep -q '^rand '; then
      cmds=" $i $cmds"
    fi
  done

  case "$cmds" in
    *\ "$1"\ *)
      cmd="$1"; shift
      exec $openssl_bin "$cmd" -rand /dev/random "$@" ;;
  esac

  exec $openssl_bin "$@"
)
EOF

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_package_crypto-policies_installed'"

if ! rpm -q --quiet "crypto-policies" ; then
    dnf install -y "crypto-policies"
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_package_crypto-policies_installed'"

if ! rpm -q --quiet "crypto-policies" ; then
    dnf install -y "crypto-policies"
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_package_iptables_installed'"

if ! rpm -q --quiet "iptables" ; then
    dnf install -y "iptables"
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_package_rng-tools_installed'"


if ! rpm -q --quiet "rng-tools" ; then
    dnf install -y "rng-tools"
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_package_sudo_installed'"

if ! rpm -q --quiet "sudo" ; then
    dnf install -y "sudo"
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_package_usbguard_installed'"

if ! rpm -q --quiet "usbguard" ; then
    dnf install -y "usbguard"
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_sudo_require_reauthentication'"

var_sudo_timestamp_timeout="0"

if /usr/sbin/visudo -qcf /etc/sudoers; then
    cp /etc/sudoers /etc/sudoers.bak
    if ! grep -P '^[\s]*Defaults.*\btimestamp_timeout=[-]?\w+\b\b.*$' /etc/sudoers; then
        # sudoers file doesn't define Option timestamp_timeout
        echo "Defaults timestamp_timeout=${var_sudo_timestamp_timeout}" >> /etc/sudoers
    else
        # sudoers file defines Option timestamp_timeout, remediate if appropriate value is not set
        if ! grep -P "^[\s]*Defaults.*\btimestamp_timeout=${var_sudo_timestamp_timeout}\b.*$" /etc/sudoers; then

            sed -Ei "s/(^[\s]*Defaults.*\btimestamp_timeout=)[-]?\w+(\b.*$)/\1${var_sudo_timestamp_timeout}\2/" /etc/sudoers
        fi
    fi

    # Check validity of sudoers and cleanup bak
    if /usr/sbin/visudo -qcf /etc/sudoers; then
        rm -f /etc/sudoers.bak
    else
        echo "Fail to validate remediated /etc/sudoers, reverting to original file."
        mv /etc/sudoers.bak /etc/sudoers
        false
    fi
else
    echo "Skipping remediation, /etc/sudoers failed to validate"
    false
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_sudoers_validate_passwd'"

if [ -e "/etc/sudoers" ] ; then

    LC_ALL=C sed -i "/Defaults !targetpw/d" "/etc/sudoers"
else
    touch "/etc/sudoers"
fi
cp "/etc/sudoers" "/etc/sudoers.bak"
# Insert at the end of the file
printf '%s\n' "Defaults !targetpw" >> "/etc/sudoers"
# Clean up after ourselves.
rm "/etc/sudoers.bak"
if [ -e "/etc/sudoers" ] ; then

    LC_ALL=C sed -i "/Defaults !rootpw/d" "/etc/sudoers"
else
    touch "/etc/sudoers"
fi
cp "/etc/sudoers" "/etc/sudoers.bak"
# Insert at the end of the file
printf '%s\n' "Defaults !rootpw" >> "/etc/sudoers"
# Clean up after ourselves.
rm "/etc/sudoers.bak"
if [ -e "/etc/sudoers" ] ; then

    LC_ALL=C sed -i "/Defaults !runaspw/d" "/etc/sudoers"
else
    touch "/etc/sudoers"
fi
cp "/etc/sudoers" "/etc/sudoers.bak"
# Insert at the end of the file
printf '%s\n' "Defaults !runaspw" >> "/etc/sudoers"
# Clean up after ourselves.
rm "/etc/sudoers.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_ensure_gpgcheck_local_packages'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q dnf; then

# Test if the config_file is a symbolic link. If so, use --follow-symlinks with sed.
# Otherwise, regular sed command will do.
sed_command=('sed' '-i')
if test -L "/etc/dnf/dnf.conf"; then
    sed_command+=('--follow-symlinks')
fi

# Strip any search characters in the key arg so that the key can be replaced without
# adding any search characters to the config file.
stripped_key=$(sed 's/[\^=\$,;+]*//g' <<< "^localpkg_gpgcheck")

# shellcheck disable=SC2059
printf -v formatted_output "%s = %s" "$stripped_key" "1"

# If the key exists, change it. Otherwise, add it to the config_file.
# We search for the key string followed by a word boundary (matched by \>),
# so if we search for 'setting', 'setting2' won't match.
if LC_ALL=C grep -q -m 1 -i -e "^localpkg_gpgcheck\\>" "/etc/dnf/dnf.conf"; then
    escaped_formatted_output=$(sed -e 's|/|\\/|g' <<< "$formatted_output")
    "${sed_command[@]}" "s/^localpkg_gpgcheck\\>.*/$escaped_formatted_output/gi" "/etc/dnf.conf"
else
    # \n is precaution for case where file ends without trailing newline

    printf '%s\n' "$formatted_output" >> "/etc/dnf/dnf.conf"
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_coredump_disable_backtraces'"

if [ -e "/etc/systemd/coredump.conf" ] ; then

    LC_ALL=C sed -i "/^\s*ProcessSizeMax\s*=\s*/Id" "/etc/systemd/coredump.conf"
else
    touch "/etc/systemd/coredump.conf"
fi
# make sure file has newline at the end
sed -i -e '$a\' "/etc/systemd/coredump.conf"

cp "/etc/systemd/coredump.conf" "/etc/systemd/coredump.conf.bak"
# Insert at the end of the file
printf '%s\n' "ProcessSizeMax=0" >> "/etc/systemd/coredump.conf"
# Clean up after ourselves.
rm "/etc/systemd/coredump.conf.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_coredump_disable_storage'"

if [ -e "/etc/systemd/coredump.conf" ] ; then

    LC_ALL=C sed -i "/^\s*Storage\s*=\s*/Id" "/etc/systemd/coredump.conf"
else
    touch "/etc/systemd/coredump.conf"
fi
# make sure file has newline at the end
sed -i -e '$a\' "/etc/systemd/coredump.conf"

cp "/etc/systemd/coredump.conf" "/etc/systemd/coredump.conf.bak"
# Insert at the end of the file
printf '%s\n' "Storage=none" >> "/etc/systemd/coredump.conf"
# Clean up after ourselves.
rm "/etc/systemd/coredump.conf.bak"

################################################################################################

echo "Remediating: 'xccdf_org.ssgproject.content_rule_disable_users_coredumps'"

# Remediation is applicable only in certain platforms
if rpm --quiet -q pam; then

SECURITY_LIMITS_FILE="/etc/security/limits.conf"

if grep -qE '^\s*\*\s+hard\s+core' $SECURITY_LIMITS_FILE; then
        sed -ri 's/(hard\s+core\s+)[[:digit:]]+/\1 0/' $SECURITY_LIMITS_FILE
else
        echo "*     hard   core    0" >> $SECURITY_LIMITS_FILE
fi

if ls /etc/security/limits.d/*.conf > /dev/null; then
        sed -ri '/^\s*\*\s+hard\s+core/d' /etc/security/limits.d/*.conf
fi

else
    >&2 echo 'Remediation is not applicable, nothing was done'
fi