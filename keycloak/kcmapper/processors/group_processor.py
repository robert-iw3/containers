from utils.neo4j_utils import execute_query, clean_properties

class GroupProcessor:
    """Handles extraction and loading of Groups and their hierarchy."""
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger

    def process(self, realm_name, clients):
        """Main processing method for groups."""
        self.logger.info("Processing groups...")
        groups = self._extract()
        if groups:
            self._load(groups, realm_name, clients)
            self.logger.info("-> Finished processing groups.")
        return groups

    def _extract(self):
        self.logger.info("  Extracting from Keycloak...")
        try:
            groups = self.keycloak_admin.get_groups()
            self.logger.info("  -> Found %s top-level group(s).", len(groups))
            return groups
        except Exception as e:
            self.logger.error("  Error while extracting groups: %s", e, exc_info=True)
            return []

    def _load(self, groups, realm_name, clients):
        self.logger.info("  Loading into Neo4j...")
        for group in groups:
            self._load_group_recursive(group, realm_name, None, clients)

    def _load_group_recursive(self, group, realm_name, parent_id, clients):
        group_id = group['id']

        # Create the group node with its properties
        properties = clean_properties(group, keys_to_ignore={'id', 'subGroups', 'roleMappings'})
        query_create_group = "MERGE (g:Group {id: $group_id}) SET g += $properties"
        execute_query(self.neo4j_driver, self.logger, query_create_group, {
            "group_id": group_id, "properties": properties
        })

        # Link to parent OR to realm, but not both
        if parent_id:
            # It's a subgroup, link it to its parent
            query_link_parent = "MATCH (parent:Group {id: $parent_id}), (child:Group {id: $child_id}) MERGE (child)-[:IS_SUBGROUP_OF]->(parent)"
            execute_query(self.neo4j_driver, self.logger, query_link_parent, {"parent_id": parent_id, "child_id": group_id})
        else:
            # It's a top-level group, link it to the realm
            query_link_realm = "MATCH (realm:Realm {name: $realm_name}), (g:Group {id: $group_id}) MERGE (g)-[:IN_REALM]->(realm)"
            execute_query(self.neo4j_driver, self.logger, query_link_realm, {
                "realm_name": realm_name, "group_id": group_id
            })

        # Process ONLY direct role mappings for the current group
        self._process_group_role_mappings(group_id, realm_name, clients)

        # Use the subGroups from the original list traversal to continue recursion
        if 'subGroups' in group and group['subGroups']:
            for subgroup in group['subGroups']:
                self._load_group_recursive(subgroup, realm_name, parent_id=group_id, clients=clients)

    def _process_group_role_mappings(self, group_id, realm_name, clients):
        # Process realm roles for the group
        try:
            realm_roles = self.keycloak_admin.get_group_realm_roles(group_id=group_id)
            for role in realm_roles:
                query = """
                    MATCH (g:Group {id: $group_id})
                    MATCH (r:RealmRole {name: $role_name, realm: $realm_name})
                    MERGE (g)-[:HAS_ROLE]->(r)
                """
                execute_query(self.neo4j_driver, self.logger, query, {"group_id": group_id, "role_name": role['name'], "realm_name": realm_name})
        except Exception as e:
            self.logger.error("  Error extracting realm roles for group %s: %s", group_id, e)

        # Process client roles for the group
        for client in clients:
            client_internal_id = client['id']
            try:
                client_roles = self.keycloak_admin.get_group_client_roles(group_id=group_id, client_id=client_internal_id)
                for role in client_roles:
                    query = """
                        MATCH (g:Group {id: $group_id})
                        MATCH (r:ClientRole {name: $role_name, client: $client_internal_id})
                        MERGE (g)-[:HAS_ROLE]->(r)
                    """
                    execute_query(self.neo4j_driver, self.logger, query, {
                        "group_id": group_id,
                        "role_name": role['name'],
                        "client_internal_id": client_internal_id
                    })
            except Exception as e:
                self.logger.error("  Error extracting client roles for group %s and client %s: %s", group_id, client_internal_id, e)