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
            -v ${XAUTHORITY:-$HOME/.Xauthority}:/root/.Xauthority \
            ghidra

```

On a Wayland desktop the X cookie is **not** at `~/.Xauthority` — mutter's Xwayland writes it
under `$XDG_RUNTIME_DIR` with a random suffix, which is why the command above reads `$XAUTHORITY`
rather than a fixed path. Mounting the wrong file leaves the container unable to authenticate to
the display, and Java reports that as a headless environment — which sends you looking at the
host's X server instead of at the mount.

## Headless use

`analyzeHeadless` works as well as the GUI, which is what makes batch import possible:

```bash
podman run --rm \
  -v ./samples:/samples:Z \
  -v ./root:/root:Z \
  --entrypoint /ghidra/support/analyzeHeadless \
  ghidra /project myproject -import /samples/thing.bin \
         -processor x86:LE:64:default \
         -loader BinaryLoader -loader-baseAddr 0x400000
```

Two things this image has to get right for that to run at all, both easy to miss because the
interactive path tolerates them:

- **A JDK, not a JRE.** Ghidra's launcher rejects a JRE-only install and falls back to
  prompting for a JDK path. With no TTY it aborts with `Unable to prompt user for JDK path`,
  which reads as a terminal problem rather than a Java one.
- **A writable `$HOME`.** The launcher saves the resolved JDK path under the user's home and
  treats a home it cannot write to as *no JDK found* — producing the same prompt error. Running
  as root with `-v ./root:/root` satisfies this by accident; a non-root user, a read-only home,
  or a tmpfs mounted over it does not.

`JAVA_HOME_OVERRIDE` is pinned in `support/launch.properties` so the search never happens, and
the build runs a real headless import so a broken launcher fails the build rather than the first
analysis.

The GUI is asserted separately, because a headless import proves nothing about it — it never
touches AWT. The runtime stage needs the X client libraries (which arrive with the JDK) **and**
`fontconfig` with at least one font, which does not: without it Swing fails to initialise its
font subsystem and `client` mode dies on launch while every other check stays green.

## Credits

- NSA Research Directorate [https://github.com/NationalSecurityAgency/ghidra](https://github.com/NationalSecurityAgency/ghidra)

