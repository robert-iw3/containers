```yaml

connector.class=io.confluent.connect.syslog.SyslogSourceConnector
kafka.topic=syslog-tcp
syslog.listener=tcpssl
syslog.port=5514
syslog.ssl.provider=openssl
syslog.listen.address=<kafka container ip>
syslog.ssl.cert.chain.path=/path/to/.pem
syslog.ssl.key.path=/path/to/privatekey.pem
syslog.ssl.key.password=' '
syslog.ssl.self.signed.certificate.enable=false
name=tcpsyslog
tasks.max=1
syslog.reverse.dns.remote.ip=true

```
