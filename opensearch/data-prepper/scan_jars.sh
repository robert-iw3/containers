#!/bin/bash

SNYK_CLI_BINARY_NAME=snyk-cli
SNYK_CLI_BINARY_LOCATION=https://github.com/snyk/cli/releases/latest/download/
REMOTE_REPO_URL=opensearch-data-prepper_jars

detected_jars=""
undetected_jars=""
detected_count=0
undetected_count=0

[[ -z "$REMOTE_REPO_URL" ]] && { echo "REMOTE_REPO_URL is empty. Please enter REMOTE_REPO_URL (line 6) and re-run script." ; exit 1; }

#Download Snyk binary specific to OS (MacOS or Linux)
case "$(uname -s)" in
   Darwin)
     curl -L -O $SNYK_CLI_BINARY_LOCATION/snyk-macos
     mv snyk-macos snyk-cli
     ;;
   Linux)
     curl -L -O $SNYK_CLI_BINARY_LOCATION/snyk-linux
     mv snyk-linux snyk-cli
     ;;
esac

chmod +x $SNYK_CLI_BINARY_NAME

#Loop through folders recursively to find all .jar files
#NOTE: will ERROR on files with whitespace in name or contained in directories with whitespace in name
for file in $(find . -type f -name '*.jar' | uniq)
do
echo ""
echo "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
echo $file
echo "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="

#Execute Snyk monitor for each .jar
if (./$SNYK_CLI_BINARY_NAME monitor --scan-unmanaged --file=$file --project-name=$file --remote-repo-url=$REMOTE_REPO_URL) then
  detected_jars+=$file'\n'
  let detected_count++
else
  undetected_jars+=$file'\n'
  let undetected_count++
fi

done

#Output metrics to the console
echo ""
echo ""
echo ""
echo "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
echo "Detected jars ($detected_count) - does not include transitive dependencies:"
echo ""
printf $detected_jars
echo ""
echo ""
echo ""
echo "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
echo "Undetected jars ($undetected_count) - not found on Maven Central:"
echo ""
printf $undetected_jars
