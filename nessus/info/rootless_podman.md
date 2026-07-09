##

```sh

# https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md

sudo dnf install slirp4netns -y
sudo echo "user.max_user_namespaces=<   >" > /etc/sysctl.d/userns.conf
sudo sysctl -p /etc/sysctl.d/userns.conf
sudo useradd -m -c "Tenable Nessus" nessus
sudo passwd nessus

sudo tee /etc/sysctl.d/99-traefik-podman.conf<<EOF
[main]
summary=traefik, http redirect and api dashboard access
[sysctl]
net.ipv4.ip_unprivileged_port_start=80
EOF

sudo sysctl -p /etc/sysctl.d/99-traefik-podman.conf

cat /etc/subuid

podman --runtime crun

```

As a non-root container user, container images are stored under your home directory (for instance,
$HOME/.local/share/containers/storage), instead of /var/lib/containers. This directory scheme ensures
that you have enough storage for your home directory.

Users running rootless containers are given special permission to run on the host system using a range of
user and group IDs. Otherwise, they have no root privileges to the operating system on the host.

A container running as root in a rootless account can turn on privileged features within its own namespace.
But that doesn't provide any special privileges to access protected features on the host (beyond having extra UIDs and GIDs).

[![Rootless](https://img.youtube.com/vi/N4ki5Sffy-E/0.jpg)](https://www.youtube.com/watch?v=N4ki5Sffy-E)
