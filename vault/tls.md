## Generate Root CA

```zsh
vault secrets enable pki
vault secrets tune -max-lease-ttl=87600h pki

vault write -field=certificate pki/root/generate/internal \
        common_name="consul.consul" \
        ttl=87600h > CA_cert.crt


vault write pki/config/urls \
        issuing_certificates="http://127.0.0.1:8200/v1/pki/ca" \
        crl_distribution_points="http://127.0.0.1:8200/v1/pki/crl"

```

## Generating certs for consul with vault

```zsh

mkdir -p /opt/consul/agent-certs

vault write pki_int/issue/consul-consul common_name="server.consul.consul" ttl="24h" | tee consul_certs.txt

grep -Pzo "(?s)(?<=certificate)[^\-]*.*?END CERTIFICATE[^\n]*\n" consul_certs.txt | sed 's/^\s*-/-/g' > /opt/consul/agent-certs/agent.crt

grep -Pzo "(?s)(?<=issuing_ca)[^\-]*.*?END CERTIFICATE[^\n]*\n" consul_certs.txt | sed 's/^\s*-/-/g' > /opt/consul/agent-certs/ca.crt

grep -Pzo "(?s)(?<=private_key)[^\-]*.*?END RSA PRIVATE KEY[^\n]*\n" consul_certs.txt | sed 's/^\s*-/-/g' > /opt/consul/agent-certs/agent.key

chown -R consul:consul /opt/consul/agent-certs