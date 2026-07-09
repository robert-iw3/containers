```python

from pymilvus import utility

utility.create_user(user, password, using="default")

utility.update_password(user, old_password, new_password, using="default")

utility.list_usernames(using="default")

utility.list_user(username, include_role_info, using="default")

utility.list_users(include_role_info, using="default")

```

```python

from pymilvus import Role, utility

role_name = "roleA"
role = Role(role_name, using=_CONNECTION)
role.create()

role.is_exist("roleA")

utility.list_roles(include_user_info, using="default")

role.grant("Collection", "*", "Search")

role.list_grant("Collection","CollectionA")

role.list_grants()

role.add_user(username)

role.get_users()

```
