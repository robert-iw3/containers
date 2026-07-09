packer {
  required_plugins {
    amazon = {
      version = ">= 1.3.1"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "nomad_version" {
  type    = string
  default = "2.0.3"
}

variable "consul_version" {
  type    = string
  default = "2.0.1"
}

variable "vault_version" {
  type    = string
  default = "2.0.2"
}

source "amazon-ebs" "nomad-podman" {
  ami_name      = "nomad-consul-vault-ubuntu-${formatdate("YYYYMMDDhhmmss", timestamp())}"
  instance_type = "t3.medium"
  region        = var.aws_region
  source_ami_filter {
    filters = {
      name                = "ubuntu/images/hvm-ssd/ubuntu-noble-24.04-amd64-server-*"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["099720109477"]
  }
  ssh_username = "ubuntu"
}

build {
  sources = ["source.amazon-ebs.nomad-podman"]

  provisioner "shell" {
    environment_vars = [
      "NOMAD_VERSION=${var.nomad_version}",
      "CONSUL_VERSION=${var.consul_version}",
      "VAULT_VERSION=${var.vault_version}",
    ]
    inline = [
      "sudo apt-get update",
      "sudo apt-get install -y unzip curl chrony podman crun slirp4netns cni-plugins logrotate",
      "sudo useradd -r -s /sbin/nologin -M nomad",
      "sudo useradd -r -s /sbin/nologin -M consul",
      "sudo useradd -r -s /sbin/nologin -M vault",
      "sudo mkdir -p /etc/nomad.d /opt/nomad/data /var/log/nomad",
      "sudo mkdir -p /etc/consul.d /opt/consul/data /var/log/consul",
      "sudo mkdir -p /etc/vault.d /opt/vault/data /var/log/vault",
      "sudo chown -R nomad:nomad /etc/nomad.d /opt/nomad/data /var/log/nomad",
      "sudo chown -R consul:consul /etc/consul.d /opt/consul/data /var/log/consul",
      "sudo chown -R vault:vault /etc/vault.d /opt/vault/data /var/log/vault",
      "sudo chmod 0700 /etc/nomad.d /opt/nomad/data /etc/consul.d /opt/consul/data /etc/vault.d /opt/vault/data",
      "sudo chmod 0750 /var/log/nomad /var/log/consul /var/log/vault",
      "sudo mkdir -p /home/nomad/.config/containers",
      "sudo bash -c 'cat <<EOF > /home/nomad/.config/containers/storage.conf\n[storage]\ndriver = \"overlay\"\nrunroot = \"/run/user/1000\"\ngraphroot = \"/home/nomad/.local/share/containers/storage\"\n[network]\nnetwork_backend = \"cni\"\nEOF'",
      "sudo mkdir -p /home/nomad/.config/cni/net.d",
      "sudo bash -c 'cat <<EOF > /home/nomad/.config/cni/net.d/99-nomad.conflist\n{\n  \"cniVersion\": \"0.4.0\",\n  \"name\": \"nomad\",\n  \"plugins\": [\n    {\n      \"type\": \"bridge\",\n      \"bridge\": \"nomad0\",\n      \"isGateway\": true,\n      \"ipMasq\": true,\n      \"ipam\": {\n        \"type\": \"host-local\",\n        \"subnet\": \"10.88.0.0/16\",\n        \"routes\": [\n          { \"dst\": \"0.0.0.0/0\" }\n        ]\n      }\n    }\n  ]\n}\nEOF'",
      "sudo chown -R nomad:nomad /home/nomad/.config",
      "sudo chmod -R 0600 /home/nomad/.config",

      "cd /tmp && curl -fsSLO https://releases.hashicorp.com/nomad/$${NOMAD_VERSION}/nomad_$${NOMAD_VERSION}_linux_amd64.zip",
      "cd /tmp && curl -fsSLO https://releases.hashicorp.com/nomad/$${NOMAD_VERSION}/nomad_$${NOMAD_VERSION}_SHA256SUMS",
      "cd /tmp && grep \"nomad_$${NOMAD_VERSION}_linux_amd64.zip\" nomad_$${NOMAD_VERSION}_SHA256SUMS | sha256sum -c -",
      "sudo unzip /tmp/nomad_$${NOMAD_VERSION}_linux_amd64.zip -d /usr/local/bin",
      "sudo chmod 0750 /usr/local/bin/nomad",
      "sudo chown nomad:nomad /usr/local/bin/nomad",
      "sudo /usr/local/bin/nomad --version | grep \"$${NOMAD_VERSION}\" || exit 1",

      "cd /tmp && curl -fsSLO https://releases.hashicorp.com/consul/$${CONSUL_VERSION}/consul_$${CONSUL_VERSION}_linux_amd64.zip",
      "cd /tmp && curl -fsSLO https://releases.hashicorp.com/consul/$${CONSUL_VERSION}/consul_$${CONSUL_VERSION}_SHA256SUMS",
      "cd /tmp && grep \"consul_$${CONSUL_VERSION}_linux_amd64.zip\" consul_$${CONSUL_VERSION}_SHA256SUMS | sha256sum -c -",
      "sudo unzip /tmp/consul_$${CONSUL_VERSION}_linux_amd64.zip -d /usr/local/bin",
      "sudo chmod 0750 /usr/local/bin/consul",
      "sudo chown consul:consul /usr/local/bin/consul",
      "sudo /usr/local/bin/consul --version | grep \"$${CONSUL_VERSION}\" || exit 1",

      "cd /tmp && curl -fsSLO https://releases.hashicorp.com/vault/$${VAULT_VERSION}/vault_$${VAULT_VERSION}_linux_amd64.zip",
      "cd /tmp && curl -fsSLO https://releases.hashicorp.com/vault/$${VAULT_VERSION}/vault_$${VAULT_VERSION}_SHA256SUMS",
      "cd /tmp && grep \"vault_$${VAULT_VERSION}_linux_amd64.zip\" vault_$${VAULT_VERSION}_SHA256SUMS | sha256sum -c -",
      "sudo unzip /tmp/vault_$${VAULT_VERSION}_linux_amd64.zip -d /usr/local/bin",
      "sudo chmod 0750 /usr/local/bin/vault",
      "sudo chown vault:vault /usr/local/bin/vault",
      "sudo /usr/local/bin/vault --version | grep \"$${VAULT_VERSION}\" || exit 1",

      "sudo sysctl -w vm.max_map_count=262144",
      "sudo sysctl -w net.core.somaxconn=1024",
      "sudo sysctl -w user.max_user_namespaces=28633",
      "sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80",
      "sudo bash -c 'echo nomad:100000:65536 > /etc/subuid'",
      "sudo bash -c 'echo nomad:100000:65536 > /etc/subgid'",
      "rm -f /tmp/*.zip /tmp/*_SHA256SUMS"
    ]
  }
}
