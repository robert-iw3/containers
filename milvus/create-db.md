```python

from pymilvus import connections, db

conn = connections.connect(host="127.0.0.1", port=19530)

database = db.create_database("myawesomevectordb")

```

```python

db.using_database("myawesomevectordb")

conn = connections.connect(
    host="127.0.0.1",
    port="19530",
    db_name="default"
)

db.list_database()

```
