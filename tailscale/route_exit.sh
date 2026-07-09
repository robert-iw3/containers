#!/usr/bin/env bash
echo 'net.ipv4.ip_forward = 1' | tee -a /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1' | tee -a /etc/sysctl.d/99-tailscale.conf
sysctl -p /etc/sysctl.d/99-tailscale.conf

mv /etc/resolv.conf /etc/resolv.conf.bak
touch /etc/resolv.conf
echo -ne 'nameserver 9.9.9.9\nnameserver 149.112.112.112' | tee -a /etc/resolv.conf

modprobe tun
# new zone, enable masquerade, default to drop
firewall-cmd --permanent --new-zone=tailscale
firewall-cmd --reload
firewall-cmd --zone=tailscale --permanent --add-masquerade
firewall-cmd --zone=tailscale --permanent --set-target=DROP

# add tun interface to active zone with the interface going to the internet
firewall-cmd --zone=tailscale --add-interface=tailscale0 --permanent

# add required ports
firewall-cmd --zone=tailscale --add-port=443/tcp --permanent
firewall-cmd --zone=tailscale --add-port=41641/udp --permanent
firewall-cmd --zone=tailscale --add-port=3478/udp --permanent
firewall-cmd --reload

<<comment
This script sets up routing and NAT for Tailscale, allowing traffic to be routed through a specific exit node.
iptables -t nat -A PREROUTING -d 192.168.1.1 -p tcp -j DNAT --to-destination 100.88.0.0/16
iptables -t nat -A POSTROUTING -s 100.88.0.0/16 -p tcp -j SNAT --to-source 192.168.1.1
ip route add 100.88.0.0/16 via 192.168.1.1
comment