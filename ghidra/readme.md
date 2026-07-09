<p align="center">
  <a href="https://github.com/blacktop/docker-ghidra"><img alt="Malice Logo" src="https://raw.githubusercontent.com/blacktop/docker-ghidra/master/ghidra.png" height="140" /></a>
</p>

##

```bash
podman build -t ghidra .

podman run --init -it --rm \
            --name ghidra \
            --cpus 2 \
            --memory 4g \
            --security-opt label=type:container_runtime_t \
            -e MAXMEM=4G \
            -e DISPLAY=$DISPLAY \
            -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR \
            -h $HOSTNAME \
            -v /tmp/.X11-unix:/tmp/.X11-unix \
            -v ./samples:/samples:Z \
            -v ./root:/root:Z \
            -v $HOME/.Xauthority:/root/.Xauthority \
            ghidra

```

## Credits

- NSA Research Directorate [https://github.com/NationalSecurityAgency/ghidra](https://github.com/NationalSecurityAgency/ghidra)

