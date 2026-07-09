##

```python

from pymilvus import connections, Role

_HOST = '127.0.0.1'
_PORT = '19530'
_ROOT = "root"
_ROOT_PASSWORD = "Milvus"
_ROLE_NAME = "test_role"
_PRIVILEGE_INSERT = "Insert"


def connect_to_milvus(db_name="default"):
    print(f"connect to milvus\n")
    connections.connect(host=_HOST, port=_PORT, user=_ROOT, password=_ROOT_PASSWORD, db_name=db_name)

connect_to_milvus()
role = Role(_ROLE_NAME)
role.create()

connect_to_milvus()
role.grant("Collection", "*", _PRIVILEGE_INSERT)
print(role.list_grants())
print(role.list_grant("Collection", "*"))
role.revoke("Global", "*", _PRIVILEGE_INSERT)

connect_to_milvus(db_name="foo")
role.grant("Collection", "*", _PRIVILEGE_INSERT)
print(role.list_grants())
print(role.list_grant("Collection", "*"))
role.revoke("Global", "*", _PRIVILEGE_INSERT)

db_name = "foo"
connect_to_milvus()
role.grant("Collection", "*", _PRIVILEGE_INSERT, db_name=db_name)
print(role.list_grants(db_name=db_name))
print(role.list_grant("Collection", "*", db_name=db_name))
role.revoke("Global", "*", _PRIVILEGE_INSERT, db_name=db_name)

```
