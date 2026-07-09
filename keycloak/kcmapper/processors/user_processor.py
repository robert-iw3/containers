from utils.neo4j_utils import execute_query, clean_properties

class UserProcessor:
    """Handles extraction and loading of Users, their group memberships and role mappings."""
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger

    def process(self, realm_name, clients):
        """Main processing method for users."""
        self.logger.info("Processing users...")
        users = self._extract_users()
        if users:
            self._load_users(users, realm_name, clients)
            self.logger.info("-> Finished processing users.")
        return users

    def _extract_users(self):
        self.logger.info("  Extracting users from Keycloak...")
        try:
            users = self.keycloak_admin.get_users()
            self.logger.info("  -> Found %s user(s).", len(users))
            return users
        except Exception as e:
            self.logger.error("  Error while extracting users: %s", e, exc_info=True)
            return []

    def _load_users(self, users, realm_name, clients):
        self.logger.info("  Loading users, groups and roles into Neo4j...")
        for user in users:
            user_id = user['id']
            properties = clean_properties(user, keys_to_ignore={'id'})

            # Load user node and link it to the realm
            query = (
                "MATCH (r:Realm {name: $realm_name}) "
                "MERGE (u:User {id: $user_id}) "
                "SET u += $properties "
                "MERGE (u)-[:IN_REALM]->(r)"
            )
            execute_query(self.neo4j_driver, self.logger, query, {
                "realm_name": realm_name,
                "user_id": user_id,
                "properties": properties
            })

            # Get and load group memberships
            self._process_user_group_mappings(user_id)

            # Get and load role mappings
            self._process_user_role_mappings(user_id, realm_name, clients)

    def _process_user_group_mappings(self, user_id):
        try:
            user_groups = self.keycloak_admin.get_user_groups(user_id=user_id)
            for group in user_groups:
                group_id = group['id']
                query = "MATCH (u:User {id: $user_id}), (g:Group {id: $group_id}) MERGE (u)-[:MEMBER_OF]->(g)"
                execute_query(self.neo4j_driver, self.logger, query, {"user_id": user_id, "group_id": group_id})
        except Exception as e:
            self.logger.error("  Error extracting groups for user %s: %s", user_id, e)

    def _process_user_role_mappings(self, user_id, realm_name, clients):
        try:
            direct_realm_roles = self.keycloak_admin.get_realm_roles_of_user(user_id=user_id)
            for role in direct_realm_roles:
                query = """
                    MATCH (u:User {id: $user_id})
                    MATCH (r:RealmRole {name: $role_name, realm: $realm_name})
                    MERGE (u)-[:HAS_ROLE]->(r)
                """
                execute_query(self.neo4j_driver, self.logger, query, {"user_id": user_id, "role_name": role['name'], "realm_name": realm_name})
        except Exception as e:
            self.logger.error("  Error processing realm roles for user %s: %s", user_id, e)

        for client in clients:
            client_internal_id = client['id']
            try:
                direct_client_roles = self.keycloak_admin.get_client_roles_of_user(user_id=user_id, client_id=client_internal_id)
                for role in direct_client_roles:
                    query = """
                        MATCH (u:User {id: $user_id})
                        MATCH (r:ClientRole {name: $role_name, client: $client_internal_id})
                        MERGE (u)-[:HAS_ROLE]->(r)
                    """
                    execute_query(self.neo4j_driver, self.logger, query, {"user_id": user_id, "role_name": role['name'], "client_internal_id": client_internal_id})
            except Exception as e:
                self.logger.error("  Error processing client roles for user %s and client %s: %s", user_id, client_internal_id, e)