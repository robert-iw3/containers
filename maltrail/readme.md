```sh
    for dev in $(ifconfig | grep mtu | grep -Eo '^\w+'); do ifconfig $dev promisc; done

    mkdir -p /var/log/maltrail/

    podman build -t maltrail .

    podman run -it --name maltrail \
        --privileged \
        -p 8337:8337/udp \
        -p 8338:8338 \
        -v /var/log/maltrail/:/var/log/maltrail/:Z \
        -v $(pwd)/maltrail.conf:/opt/maltrail/maltrail.conf:ro \
        -d maltrail
```