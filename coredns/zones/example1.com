$ORIGIN example1.com.
@         IN  SOA dns.example1.com. 2502011720 7200 3600 1209600 3600

dns       IN  A   127.0.0.1
example1    IN  A   127.0.0.1