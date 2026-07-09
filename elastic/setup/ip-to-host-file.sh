#!/bin/sh

#
# Retrieve the argument and create a name for a tmp file
#
processfile=$1
tmpfile=${1}.tmp

#
# for all running podman containers
#
for service in `podman ps -q`; do
   #
   # Extract the servicename and ipaddress
   #
   servicename=`podman inspect --format '{{ .Name }}' $service `
   ipaddress=`podman inspect --format '{{ .NetworkSettings.IPAddress }}' $service`

   #
   # if there is a service name and ipaddress
   #
   if [ ! -z $ipaddress ] &&  [ ! -z $servicename ] ;
   then
        # get rid of the first character - this is '/'

        servicename=${servicename:1}

        # remove the service name from the process file, and add it again
        grep -v $servicename $processfile > $tmpfile
        echo -e $ipaddress 't' $servicename  >> $tmpfile
        mv $tmpfile $processfile
   fi
done

# ip-to-host-file.sh /etc/hosts