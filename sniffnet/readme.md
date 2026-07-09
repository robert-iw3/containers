## sniffnet

<div align="center">
<img alt="" title="Overview page" src="https://raw.githubusercontent.com/GyulyVGC/sniffnet/main/resources/repository/pages/overview.png" width="95%"/>
<img alt="" title="Inspect page" src="https://raw.githubusercontent.com/GyulyVGC/sniffnet/main/resources/repository/pages/inspect.png" width="47%"/>
<img alt="" title="Notifications page" src="https://raw.githubusercontent.com/GyulyVGC/sniffnet/main/resources/repository/pages/notifications.png" width="47%"/>
<img alt="" title="Custom theme" src="https://raw.githubusercontent.com/GyulyVGC/sniffnet/main/resources/repository/pages/catppuccin.png" width="47%"/>
<img alt="" title="Thumbnail mode" src="https://raw.githubusercontent.com/GyulyVGC/sniffnet/main/resources/repository/pages/thumbnail.png" width="47%"/>
</div>

##

```sh

sudo podman build -t sniffnet .

# x11

xhost +local:podman

sudo podman run -it --name sniffnet \
    --security-opt label=type:container_runtime_t \
    --net=host \
    -e DISPLAY=$DISPLAY \
    -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e RUST_BACKTRACE=full \
    -e ICED_BACKEND=tiny-skia \
    --cap-add=net_admin \
    --cap-add=net_raw \
    --cap-add=sys_nice \
    sniffnet

# wayland
sudo podman run -it --name sniffnet \
    --security-opt label=type:container_runtime_t \
    --net=host \
    -v $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY:/tmp/$WAYLAND_DISPLAY \
    -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY \
    -e XDG_RUNTIME_DIR=/tmp \
    -e RUST_BACKTRACE=full \
    -e ICED_BACKEND=tiny-skia \
    --cap-add=net_admin \
    --cap-add=net_raw \
    --cap-add=sys_nice \
    sniffnet
```

