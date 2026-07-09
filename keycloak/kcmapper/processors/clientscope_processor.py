from utils.neo4j_utils import execute_query, clean_properties

class ClientScopeProcessor:
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger
    def process(self, realm_name, clients):
        self.logger.info("Processing client scopes...")
        scopes = self._extract()
        if scopes:
            self._load(scopes, realm_name)
            self._process_client_scope_mappings(clients)
        self.logger.info("-> Finished processing client scopes.")
        return scopes
    def _extract(self):
        self.logger.info("  Extracting client scopes from Keycloak...")
        try:
            scopes = self.keycloak_admin.get_client_scopes()
            self.logger.info("  -> Found %s client scope(s).", len(scopes))
            return scopes
        except Exception as e:
            self.logger.error("  Error while extracting client scopes: %s", e, exc_info=True)
            return []
    def _load(self, scopes, realm_name):
        self.logger.info("  Loading client scopes into Neo4j...")
        for scope in scopes:
            properties = clean_properties(scope, keys_to_ignore={'id', 'name'})
            query = "MATCH (r:Realm {name: $realm_name}) MERGE (cs:ClientScope {id: $id, name: $name}) SET cs += $properties MERGE (cs)-[:IN_REALM]->(r)"
            execute_query(self.neo4j_driver, self.logger, query, {"realm_name": realm_name, "id": scope['id'], "name": scope['name'], "properties": properties})
            self._process_mappers(scope['id'])
    def _process_client_scope_mappings(self, clients):
        self.logger.info("  Processing default/optional scope mappings for clients...")
        for client in clients:
            try:
                default_scopes = self.keycloak_admin.get_client_default_client_scopes(client['id'])
                for scope in default_scopes:
                    query = "MATCH (c:Client {internal_id: $client_id}), (cs:ClientScope {id: $scope_id}) MERGE (c)-[:DEFAULT_SCOPE]->(cs)"
                    execute_query(self.neo4j_driver, self.logger, query, {"client_id": client['id'], "scope_id": scope['id']})
            except Exception as e:
                self.logger.error("  Error getting default scopes for client %s: %s", client['clientId'], e)
            try:
                optional_scopes = self.keycloak_admin.get_client_optional_client_scopes(client['id'])
                for scope in optional_scopes:
                    query = "MATCH (c:Client {internal_id: $client_id}), (cs:ClientScope {id: $scope_id}) MERGE (c)-[:OPTIONAL_SCOPE]->(cs)"
                    execute_query(self.neo4j_driver, self.logger, query, {"client_id": client['id'], "scope_id": scope['id']})
            except Exception as e:
                self.logger.error("  Error getting optional scopes for client %s: %s", client['clientId'], e)
    def _process_mappers(self, scope_id):
        try:
            mappers = self.keycloak_admin.get_mappers_from_client_scope(scope_id)
            for mapper in mappers:
                properties = clean_properties(mapper, keys_to_ignore={'id', 'name'})
                query = "MATCH (cs:ClientScope {id: $scope_id}) MERGE (m:ProtocolMapper {id: $id, name: $name}) SET m += $properties MERGE (cs)-[:HAS_MAPPER]->(m)"
                execute_query(self.neo4j_driver, self.logger, query, {"scope_id": scope_id, "id": mapper['id'], "name": mapper['name'], "properties": properties})
        except Exception as e:
            self.logger.error("  Error getting mappers for client scope %s: %s", scope_id, e)