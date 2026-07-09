#!/bin/sh

# Run this in the splunk host as a normal user

PROFILES="$HOME/.profile $HOME/.bash_profile $HOME/.zprofile"

for PROFILE in $PROFILES; do
  if [ -f "$PROFILE" ]; then
    HAS_SPLUNK=$(grep -i "splunk" "$PROFILE" || [ $? = 1 ])

    if [ -z "$HAS_SPLUNK" ]; then
      cat "profile" >> "$PROFILE"
    fi
  fi
done

# $SPLUNK_HOME
. "profile"
