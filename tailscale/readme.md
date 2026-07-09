## tailscale client container

Sign up:

https://login.tailscale.com/start

Set up auth key:

[auth-key](img/tailscale-auth-key.png)

### Python Usage Instructions
---

1. Prepare Environment:

Ensure `TS_AUTHKEY` is set in the environment or added to `.env` manually (obtain from Tailscale admin console).

Install required tools based on the orchestrator:

Docker: `docker`, `docker-compose`

Podman: `podman`, `podman-compose`

Kubernetes: `kubectl`

Ansible: `ansible-playbook`

```bash
python3 deploy_tailscale.py --orchestrator <docker|podman|kubernetes|ansible> --subnet <subnet_cidr> --namespace <namespace> --compose-file <compose_file>
```

2. Examples:

Docker: `python3 deploy_tailscale.py --orchestrator docker --subnet 192.168.1.0/24`

Kubernetes: `python3 deploy_tailscale.py --orchestrator kubernetes --subnet 192.168.1.0/24 --namespace tailscale`

Ansible: `python3 deploy_tailscale.py --orchestrator ansible --subnet 192.168.1.0/24`

3. Verify Deployment:

Docker/Podman: Check container status with `docker ps` or `podman ps`.

Kubernetes: Verify pod status with `kubectl get pods -n <namespace>`.

Ansible: Check logs for playbook execution status.

In the Tailscale admin console, locate the tailscale-exit-node device, enable the exit node, and approve subnet routes.

4. Integrate with Other Services:

For Docker/Podman, use the provided docker-compose-authentik.yml with network_mode: service:tailscale-server to route traffic through Tailscale.

For Kubernetes, deploy other pods in the same namespace and configure them to route traffic via the Tailscale pod’s IP or use a sidecar pattern.

For Ansible, modify the inventory to deploy on remote hosts or integrate with existing playbooks for other services.

5. Test Connectivity:

Enable the exit node on another Tailscale client and verify internet traffic routes through the container’s external IP.

### Manual Setup:
---

```yaml
# update "docker-compose.yml"
environment:
    - TS_AUTHKEY=tskey-auth-INSERT_YOUR_KEY_HERE
```
##

```sh
# switch dns (optional)
sudo mv /etc/resolv.conf /etc/resolv.conf.bak
sudo touch /etc/resolv.conf
echo -ne 'nameserver 9.9.9.9\nnameserver 149.112.112.112' | sudo tee -a /etc/resolv.conf

# setup forwarding
echo 'net.ipv4.ip_forward = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf

# enable tun
sudo modprobe tun

# new zone, enable masquerade, default to drop
sudo firewall-cmd --permanent --new-zone=tailscale
sudo firewall-cmd --reload
sudo firewall-cmd --zone=tailscale --permanent --add-masquerade
sudo firewall-cmd --zone=tailscale --permanent --set-target=DROP

# add tun interface to active zone with the interface going to the internet
sudo firewall-cmd --zone=tailscale --add-interface=tailscale0 --permanent

# add required ports
sudo firewall-cmd --zone=tailscale --add-port=443/tcp --permanent
sudo firewall-cmd --zone=tailscale --add-port=41641/udp --permanent
sudo firewall-cmd --zone=tailscale --add-port=3478/udp --permanent
sudo firewall-cmd --reload
```
##

```sh
sudo podman-compose up -d
```

You should now see your system connected as a client.

Setup routes, configure as exit node, and now services can utilize this client to get out to the internet.

## acl builder

https://tailscale.com/kb/1192/acl-samples

```sh
cd tailscale-acl-builder/
# as user, not root
podman build -t tailscale-acl-builder .
podman run -p 8080:8080 --name tailscale-acl-builder -d tailscale-acl-builder
```
localhost:8080

[example](img/acl_builder_example.png)

> [!NOTE]
>
> Tailscale now secures access to resources using grants, a next-generation access control policy syntax.
> Grants provide all original ACL functionality plus additional capabilities.

https://tailscale.com/kb/1542/grants-migration
