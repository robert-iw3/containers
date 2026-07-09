# [Splunk](https://splunkhostname/)

- [Deployment Apps](#deployment-apps)
- [Splunk Setup](#splunk-setup)
- [Server certificate](#server-certificate)
- [UF Client Certificate](#uf-client-certificate)
- [Could not create Splunk settings directory](#could-not-create-splunk-settings-directory)
- [OpenSSH Client Configuration](#openssh-client-configuration)

## Deployment Apps

- 1-deploymentserver: Configure the deployment clients (universal forwarders) to point to the deployment server using [deploymentclient.conf](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Deploymentclientconf).
- 1-indexserver: Configure the universal forwarders to send logs to indexing server(s) using [outputs.conf](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Outputsconf).
- 100_splunkcloud: Similar to 1-indexserver, but send logs to Splunk Cloud instead.

[prepare.py](./prepare.py) assumes the following folder structure:

```
.
├── deployment-apps
│   ├── 100_splunkcloud
│   ├── 1-deploymentserver
│   └── 1-indexserver
└── setup
    └── prepare.py
```

## Splunk Setup

Workstation:

1. Download the latest [Splunk Enterprise](https://www.splunk.com/en_us/download.html) with a Splunk.com account.
2. Copy splunk-cert.key, splunk-cert.pem & splunk-cert-web.pem to "[certs/](./certs/)" folder.
3. Run [prepare.py](./prepare.py).
4. `scp splunk-setup-all.tar.gz splunkhostname:/home/admin_user/splunk-setup-all.tar.gz`

Splunk Host:

1. (from your workstation) `ssh admin_user@splunkhostname`
2. `tar xzf splunk-setup-all.tar.gz`
3. `sh setup.sh`
4. `sudo sh setup-root.sh`
5. `sudo sh splunk-setup.sh`

## Server certificate

splunk-cert.crt: Server certificate
splunk-cert.key: Encrypted private key (stored in keepass)
[splunk-cert.pem](https://docs.splunk.com/Documentation/Splunk/latest/Security/HowtoprepareyoursignedcertificatesforSplunk#How_to_configure_a_certificate_chain) (Deployment server port 8089 & Indexing server port 9997): splunk-cert.crt + splunk-cert.key + splunk-cert-web.pem
splunk-cert-web.pem (Splunk Web port 443): splunk-cert.crt + enterprise_intermediate_cacert.crt + enterprise_root_cacert.crt

## UF Client Certificate

Recommends generating TLS certificates using OpenSSL 3.0+ which uses the more secure PKCS#8 (AES + HMAC + SHA256) by default, and avoid Splunk-bundled OpenSSL 1.0.2 which uses the traditional PKCS#1/SSLeay (AES + MD5) format by default even though it supports PKCS#8. Ideally, private key should be encrypted using AES + scrypt, but scrypt is only supported in OpenSSL 1.1.1+.

Generate root CA.

```
# create root CA private key
openssl ecparam -genkey -name secp384r1 | openssl pkey -outform PEM -out splunkuf-ca.key -aes256
# create CA
openssl req -new -x509 -key splunkuf-ca.key -out splunkuf-ca.crt -days 1000 -config splunkuf-ca_openssl.conf
# verify
openssl x509 -noout -text -in splunkuf-ca.crt
```

Generate client cert.

```
# create client private key
openssl ecparam -genkey -name secp384r1 | openssl pkey -outform PEM -out splunkuf.key -aes256
# generate CSR
openssl req -new -key splunkuf.key -out splunkuf.csr -config splunkuf_openssl.conf
# verify
openssl req -noout -text -in splunkuf.csr
# sign it with root CA
openssl x509 -req -days 365 -in splunkuf.csr -CA splunkuf-ca.crt -CAkey splunkuf-ca.key -out splunkuf.crt -sha384 -copy_extensions=copyall
# verify
openssl x509 -noout -text -in splunkuf.crt
# cert chain
cat splunkuf.crt splunkuf.key splunkuf-ca.crt > splunkuf.pem
```

## Splunk Cloud Client Certificate

splunkcloud_client.pem: client certificate + (host-specific private) intermediate CA + (host-specific private) root CA + public GlobalSign CA

## Could not create Splunk settings directory

When trying to reload deployment server, you [may get](https://community.splunk.com/t5/Deployment-Architecture/Could-not-create-Splunk-settings-directory-at-root-splunk/m-p/599622/highlight/true#M25677) `An error occurred: Could not create Splunk settings directory at '$HOME/.splunk'.`

```
mkdir -p "$HOME/.splunk"
sudo chown splunk:splunk "$HOME/.splunk"
# should run fine
sudo -E splunk reload deploy-server -timeout 300
```

The following message is expected, `WARNING: Server Certificate Hostname Validation is disabled. Please see server.conf/[sslConfig]/cliVerifyServerName for details.`. "[cliVerifyServerName](https://docs.splunk.com/Documentation/Splunk/latest/admin/serverconf#SSL.2FTLS_Configuration_details)" is disabled by default. If it is enabled, `splunk reload deploy-server` will fail because the server certificate's subject alternative name does not include 127.0.0.1. In order to use splunk CLI with "cliVerifyServerName", you would need `splunk reload deploy-server -uri https://splunkhostname:8089`

## OpenSSH Client Configuration

````powershell
# Windows
$strUserName = ((Get-CimInstance Win32_ComputerSystem).username -replace '^\w+\\(\D{5})\d{0,2}$', '$1').ToLower()
$sshConfig = "$home\.ssh\config"
$sshAlias = "Host splunk`n  HostName 123.123.123.123`n  User $($strUserName)@domain.example"
$knownHosts = "$home\.ssh\known_hosts"
$serverFingerprint = "123.123.123.123 $(get-content -path 'splunk_host_ed25519_key.pub')"

if ((test-path -path $sshConfig) -eq $false) {
  $sshfolder = split-path -path $sshConfig -Parent
  new-item -Path $sshfolder -ItemType Directory -force | out-null
  new-item -path $sshConfig -ItemType File -force | out-null
  if ((test-path -path $knownHosts) -eq $false) {
    new-item -path $sshConfig -ItemType File -force | out-null
  }
}

if ($null -eq (get-content -path $sshConfig) -or (get-content -raw -path $sshConfig | select-string -pattern $sshAlias -simplematch -Quiet) -ne $true) {
  add-content -path $sshConfig -value $sshAlias
}

if ($null -eq (get-content -path $knownHosts) -or (get-content -raw -path $knownHosts | select-string -pattern $serverFingerprint -simplematch -Quiet) -ne $true) {
  add-content -path $knownHosts -value $serverFingerprint
}

write-host "To SSH into splunkhostname, simply ``ssh splunk```n"
write-host "To copy a file to splunkhostname, ``scp local.zip splunk:/tmp/remote.zip`` or `n``scp local.zip splunk:/home/$($strUserName)@domain.example/remote.zip```n"
write-host "To download a file from splunkhostname, ``scp splunk:/home/$($strUserName)@domain.example/remote.zip local.zip``"
````

```sh
#!/bin/sh
# WSL/Linux
ssh_folder="$HOME/.ssh"
ssh_config="$ssh_folder/config"
known_hosts="$ssh_folder/known_hosts"
server_fingerprint="123.123.123.123 $(cat 'splunk_host_ed25519_key.pub')"

read -p 'Windows username (5-letter): ' win_user
win_user=$(echo "$win_user" | cut -c1-5 | tr '[:upper:]' '[:lower:]')
ssh_alias="Host splunk\n  HostName 123.123.123.123\n  User ${win_user}@domain.example"

grep -q "$ssh_alias" "$ssh_config" || not_exist="$?"
if [ -n "$not_exist" ]; then
  mkdir -p "$ssh_folder"
  chmod 700 "$ssh_folder"
  echo "$ssh_alias" >> "$ssh_config"
fi

not_exist=""

grep -q "$server_fingerprint" "$known_hosts" || not_exist="$?"
if [ -n "$not_exist" ]; then
  echo "$server_fingerprint" >> "$known_hosts"
fi

echo "To SSH into splunkhostname, simply \`ssh splunk\`\n"
echo "To copy a file to splunkhostname, \`scp local.zip splunk:/tmp/remote.zip\` or \n\`scp local.zip splunk:/home/${win_user}@domain.example/remote.zip\`\n"
echo "To download a file from splunkhostname, \`scp splunk:/home/${win_user}@domain.example/remote.zip local.zip\`"
```
