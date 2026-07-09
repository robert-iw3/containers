```python

from pymilvus import connections

_HOST = '127.0.0.1'
_PORT = '19530'

print(f"\nCreate connection...")
connections.connect(host=_HOST, port=_PORT, secure=True, client_pem_path="cert/client.pem",
                        client_key_path="cert/client.key",
                        ca_pem_path="cert/ca.pem", server_name="localhost")
print(f"\nList connections:")
print(connections.list_connections())

```
