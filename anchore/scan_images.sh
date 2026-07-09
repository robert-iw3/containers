#!/bin/bash

OFFLOAD_DIR=./

declare -a D_IMAGE=(
"some_repo/user/thisimage1:tag"
"some_repo/user/thisimage2:tag"
"some_repo/user/thisimage3:tag")
declare -a R_NAME=(
"thisimage1"
"thisimage2"
"thisimage3")

podman build -t anchore .
podman image prune -f
podman run --rm -it --name anchore -d anchore

for ((i=0; i<${#D_IMAGE[@]}; i++)); do
podman exec -it anchore syft ${D_IMAGE[$i]} --scope all-layers -o syft-json=./${R_NAME[$i]}_SBOM.json
done
for ((i=0; i<${#D_IMAGE[@]}; i++)); do
podman exec -it anchore syft ${D_IMAGE[$i]} --scope all-layers -o syft-table=./${R_NAME[$i]}_SBOM.csv
done

for ((i=0; i<${#D_IMAGE[@]}; i++)); do
podman exec -it anchore grype ${D_IMAGE[$i]} -o json --file ./${R_NAME[$i]}_vulnerabilities.json
done
for ((i=0; i<${#D_IMAGE[@]}; i++)); do
podman exec -it anchore grype ${D_IMAGE[$i]} -o table --file ./${R_NAME[$i]}_vulnerabilities.csv
done

#get results
podman cp anchore:/home/anchore ${OFFLOAD_DIR}
podman rmi -f anchore
