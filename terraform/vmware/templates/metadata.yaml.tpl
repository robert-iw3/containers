instance-id: ${hostname}
local-hostname: ${hostname}
network:
  version: 2
  ethernets:
    primary:
      match:
        name: "en*"
      addresses:
        - ${ip}/${prefix_length}
      routes:
        - to: default
          via: ${gateway}
      nameservers:
        addresses:
%{ for dns in dns_servers ~}
          - ${dns}
%{ endfor ~}
