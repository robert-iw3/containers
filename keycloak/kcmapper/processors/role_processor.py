from utils.neo4j_utils import execute_query, clean_properties

class RoleProcessor:
    """Handles extraction and loading of Realm and Client Roles."""
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger

    def process(self, clients, realm_name):
        """Main processing method for all roles in a given realm."""
        self.logger.info("Processing roles...")

        # 1. Extract all roles (realm and client)
        self.logger.info("  Extracting all role definitions...")
        realm_roles = self.keycloak_admin.get_realm_roles(brief_representation=False)
        self.logger.info("  -> Found %s realm role(s).", len(realm_roles))

        all_client_roles = []
        for client in clients:
            try:
                client_roles = self.keycloak_admin.get_client_roles(client_id=client['id'], brief_representation=False)
                all_client_roles.extend(client_roles)
            except Exception as e:
                self.logger.error("  Error extracting roles for client %s: %s", client['clientId'], e)
        self.logger.info("  -> Found %s client role(s) across all clients.", len(all_client_roles))

        # 2. Load all role nodes and link to their containers
        self.logger.info("  Loading role nodes into Neo4j...")
        self._load_realm_role_nodes(realm_roles, realm_name)
        self._load_client_role_nodes(all_client_roles)

        # 3. Create composite relationships now that all roles exist
        self.logger.info("  Processing composite relationships...")
        all_roles = realm_roles + all_client_roles
        self._process_composite_roles(all_roles, realm_name)

        self.logger.info("-> Finished processing roles.")

    def _load_realm_role_nodes(self, roles, realm_name):
        for role in roles:
            properties = clean_properties(role, keys_to_ignore={'id', 'name', 'composites', 'realm', 'clientRole', 'containerId'})
            query = """
                MATCH (realm:Realm {name: $realm_name})
                MERGE (r:Role {id: $id})
                ON CREATE SET r.name = $name
                SET r:RealmRole, r.realm = $realm_name, r += $properties
                MERGE (r)-[:BELONGS_TO_REALM]->(realm)
            """
            execute_query(self.neo4j_driver, self.logger, query, {
                "id": role['id'],
                "name": role['name'],
                "realm_name": realm_name,
                "properties": properties
            })

    def _load_client_role_nodes(self, roles):
        for role in roles:
            properties = clean_properties(role, keys_to_ignore={'id', 'name', 'composites', 'clientRole', 'containerId'})
            query = """
                MATCH (c:Client {internal_id: $client_id})
                MERGE (r:Role {id: $id})
                ON CREATE SET r.name = $name
                SET r:ClientRole, r.client = $client_id, r += $properties
                MERGE (r)-[:BELONGS_TO_CLIENT]->(c)
            """
            execute_query(self.neo4j_driver, self.logger, query, {
                "id": role['id'],
                "name": role['name'],
                "client_id": role['containerId'],
                "properties": properties
            })

    def _process_composite_roles(self, roles, realm_name):
        """Creates COMPOSED_OF relationships for a list of roles."""
        for role in roles:
            if not role.get('composite'):
                continue

            parent_match_query = "MATCH (parent:Role {id: $parent_id})"

            try:
                # Use the specific API call based on whether the parent is a client or realm role
                if role.get('clientRole'):
                    child_roles = self.keycloak_admin.get_role_client_level_children(client_id=role['containerId'], role_id=role['id'])
                else:
                    child_roles = self.keycloak_admin.get_composite_realm_roles_of_role(role_name=role['name'])

                for child_role in child_roles:
                    # The child can also be either a RealmRole or a ClientRole
                    child_match_query = "MATCH (child:Role {id: $child_id})"

                    # Build the final query
                    query = f"""
                        {parent_match_query}
                        {child_match_query}
                        MERGE (parent)-[:COMPOSED_OF]->(child)
                    """

                    execute_query(self.neo4j_driver, self.logger, query, {"parent_id": role['id'], "child_id": child_role['id']})
            except Exception as e:
                self.logger.error("Error processing composite roles for role %s (%s): %s", role['name'], role['id'], e)