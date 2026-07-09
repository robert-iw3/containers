**Example:**

```sh
podman build -t pcap_capture .

podman run --rm -it \
    --cap-add net_admin \
    --net=host \
    -e IFACE="wlo1" \
    -e FILTER="tcp port 22" \
    -v ${PWD}/dump:/data:Z \
    -d pcap_capture
```
After the packages are captured, they can be evaluated using tcpdumps `-r`
option to read captured raw packages from a file.

