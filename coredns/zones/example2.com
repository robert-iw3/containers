$ORIGIN example2.com.
@         IN  SOA dns.example2.com. 2502011720 7200 3600 1209600 3600

dns       IN  A   127.0.0.1
example2    IN  A   127.0.0.1