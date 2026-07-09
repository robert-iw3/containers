from utils.neo4j_utils import execute_query, clean_properties

class ClientProcessor:
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger

    def process(self, realm_name):
        self.logger.info("Processing clients...")
        clients = self._extract()
        if clients: self._load(clients, realm_name)
        self.logger.info("-> Finished processing clients.")
        return clients

    def _extract(self):
        self.logger.info("  Extracting from Keycloak...")
        try:
            clients = self.keycloak_admin.get_clients()
            self.logger.info("  -> Found %s client(s).", len(clients))
            return clients
        except Exception as e:
            self.logger.error("  Error while extracting clients: %s", e, exc_info=True)
            return []

    def _load(self, clients, realm_name):
        self.logger.info("  Loading into Neo4j...")
        for client in clients:
            client_id = client['id']
            properties = clean_properties(client, keys_to_ignore={'id', 'protocolMappers'})
            query = "MATCH (realm:Realm {name: $realm_name}) MERGE (c:Client {internal_id: $internal_id}) SET c += $properties MERGE (c)-[:IN_REALM]->(realm)"
            execute_query(self.neo4j_driver, self.logger, query, {"realm_name": realm_name, "internal_id": client_id, "properties": properties})
            self._process_mappers(client_id)

    def _process_mappers(self, client_id):
        try:
            mappers = self.keycloak_admin.get_mappers_from_client(client_id)
            for mapper in mappers:
                properties = clean_properties(mapper, keys_to_ignore={'id', 'name'})
                query = "MATCH (c:Client {internal_id: $client_id}) MERGE (m:ProtocolMapper {id: $id, name: $name}) SET m += $properties MERGE (c)-[:HAS_MAPPER]->(m)"
                execute_query(self.neo4j_driver, self.logger, query, {"client_id": client_id, "id": mapper['id'], "name": mapper['name'], "properties": properties})
        except Exception as e:
            self.logger.debug("  No mappers found for client %s or error: %s", client_id, e)