## usage

ref: https://www.elastic.co/guide/en/elasticsearch/client/curator/current/index.html

```sh

# build/run container

podman build -t curator-opensearch .
podman run --rm -it --name curator-opensearch -d curator-opensearch

# execute commands to your opensearch cluster (examples): < replace with your environment >

# dry-run to see what will happen
podman exec curator-opensearch curator --dry-run --host <ip address> delete indices --time-unit days --older-than 45 --timestring '%Y%m%d'

# delete indices older than 45 days
podman exec curator-opensearch curator --host <ip address> delete indices --time-unit days --older-than 45 --timestring '%Y%m%d'

# snapshots
podman exec curator-opensearch curator --host <ip address> snapshot --repository <repository name> indices --all-indices

# delete snapshots older than 10 days
podman exec curator-opensearch curator --host <ip address> delete snapshots --repository <repository name> --older-than 10 --time-unit days

# optimize static indices
podman exec curator-opensearch curator --host <ip address> optimize indices --time-unit days --older-than 2 --timestring '%Y%m%d'

```
