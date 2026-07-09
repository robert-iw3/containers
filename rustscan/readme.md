## rustscan

```sh
.----. .-. .-. .----..---.  .----. .---.   .--.  .-. .-.
| {}  }| { } |{ {__ {_   _}{ {__  /  ___} / {} \ |  `| |
| .-. \| {_} |.-._} } | |  .-._} }\     }/  /\  \| |\  |
`-' `-'`-----'`----'  `-'  `----'  `---' `-'  `-'`-' `-'
The Modern Day Port Scanner.
________________________________________
: http://discord.skerritt.blog         :
: https://github.com/RustScan/RustScan :
 --------------------------------------
RustScan: Where scanning meets swagging. 😎
```

```sh
# build the image
sudo podman build -t rustscan .

# clear images/build content
sudo podman system prune -a

# example command to run the container
sudo podman run --rm -it --name rustscan \
   --net=host --cap-add=net_admin --cap-add=net_raw --cap-add=sys_nice \
   -d rustscan

# example command to run the container with a specific target subnet (e.g. local home ethernet cidr)
# full subnet scan
sudo podman exec rustscan rustscan --addresses 192.168.1.0/24 -t 500 -b 1500 -- -A

# If you want to scan ports in a random order (which will help with not setting off firewalls) run RustScan like this:
# select target and port range with randomization
sudo podman exec rustscan rustscan -a 192.168.1.0/24 --range 1-1000 --scan-order "Random"
```

IDS doesn't detect port scanning like nmap, fyi.