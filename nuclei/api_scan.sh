#!/bin/bash

# quick api recon scan
# use nmap to find hosts with potential exposed web servers and follow on with nuclei scans

DATE=$(date +"%Y%m%d")
MODE=http
TARGET=rest.vulnweb.com
TOKEN=
RESULT_DIR=./
IMAGE=alpine:3.23

mkdir -p ${RESULT_DIR}nuclei

#build Nuclei
# podman build -t nuclei .
podman network create nuclei

#get rid of build env
podman image prune -f; podman rmi ${IMAGE} -f

#run nuclei
podman run --rm --network nuclei -it --name nuclei -d nuclei

#update templates
podman exec nuclei nuclei -ut

#execute api spec scans
podman exec nuclei nuclei -ni -u ${MODE}://${TARGET} -t http/technologies/ -o /home/nuclei/nuclei-${MODE}-${TARGET}-${DATE}_http_tech.log
podman exec nuclei nuclei -ni -u ${MODE}://${TARGET} -t http/exposed-panels/ -silent -o /home/nuclei/nuclei-${MODE}-${TARGET}-${DATE}_panels.log
podman exec nuclei nuclei -ni -u ${MODE}://${TARGET} -t http/token-spray/ -var token=${TOKEN} -o /home/nuclei/nuclei-${MODE}-${TARGET}-${DATE}_token_spray.log

#execute full scan
podman exec nuclei nuclei -ni -u ${MODE}://${TARGET} -o /home/nuclei/nuclei-${MODE}-${TARGET}-${DATE}_full_scan.log

#get results
podman cp nuclei:/home/nuclei $RESULT_DIR/nuclei

<<comment

Type of info retrieved from scans:

[default-sql-dump] [http] [medium] http://rest.vulnweb.com/db.sql [paths="/db.sql"]
[phpinfo-files] [http] [low] http://rest.vulnweb.com/info.php ["7.1.26"] [paths="/info.php"]
[missing-sri] [http] [info] http://rest.vulnweb.com ["https://fonts.googleapis.com/css?family=Nunito:200,600"]
[waf-detect:apachegeneric] [http] [info] http://rest.vulnweb.com
[tech-detect:google-font-api] [http] [info] http://rest.vulnweb.com
[tech-detect:php] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:cross-origin-embedder-policy] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:cross-origin-resource-policy] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:strict-transport-security] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:permissions-policy] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:x-frame-options] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:referrer-policy] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:cross-origin-opener-policy] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:content-security-policy] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:x-content-type-options] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:x-permitted-cross-domain-policies] [http] [info] http://rest.vulnweb.com
[http-missing-security-headers:clear-site-data] [http] [info] http://rest.vulnweb.com
[options-method] [http] [info] http://rest.vulnweb.com ["GET"]
[apache-detect] [http] [info] http://rest.vulnweb.com ["Apache/2.4.25 (Debian)"]
[php-detect] [http] [info] http://rest.vulnweb.com ["7.1.26"]

comment
