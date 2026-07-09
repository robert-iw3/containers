from utils.neo4j_utils import execute_query, clean_properties

class IdpProcessor:
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger
    def process(self, realm_name):
        self.logger.info("Processing identity providers (IDPs)...")
        idps = self._extract()
        if idps:
            self._load(idps, realm_name)
        self.logger.info("-> Finished processing IDPs.")
    def _extract(self):
        self.logger.info("  Extracting IDPs from Keycloak...")
        try:
            idps = self.keycloak_admin.get_idps()
            self.logger.info("  -> Found %s IDP(s).", len(idps))
            return idps
        except Exception as e:
            self.logger.error("  Error while extracting IDPs: %s", e, exc_info=True)
            return []
    def _load(self, idps, realm_name):
        self.logger.info("  Loading IDPs into Neo4j...")
        for idp in idps:
            idp_alias = idp['alias']
            properties = clean_properties(idp, keys_to_ignore={'internalId', 'alias'})
            query = "MATCH (r:Realm {name: $realm_name}) MERGE (i:IdentityProvider {internalId: $internal_id, alias: $alias}) SET i += $properties MERGE (i)-[:IN_REALM]->(r)"
            execute_query(self.neo4j_driver, self.logger, query, {"realm_name": realm_name, "internal_id": idp['internalId'], "alias": idp_alias, "properties": properties})
            self._process_mappers(idp_alias, idp['internalId'])

    def _process_mappers(self, idp_alias, idp_internal_id):
        try:
            mappers = self.keycloak_admin.get_idp_mappers(idp_alias)
            for mapper in mappers:
                properties = clean_properties(mapper, keys_to_ignore={'id', 'name'})
                query = "MATCH (i:IdentityProvider {internalId: $idp_id}) MERGE (m:IdpMapper {id: $id, name: $name}) SET m += $properties MERGE (i)-[:HAS_MAPPER]->(m)"
                execute_query(self.neo4j_driver, self.logger, query, {"idp_id": idp_internal_id, "id": mapper['id'], "name": mapper['name'], "properties": properties})
        except Exception as e:
            self.logger.error("  Error getting mappers for IDP %s: %s", idp_alias, e)