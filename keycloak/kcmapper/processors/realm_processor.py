from utils.neo4j_utils import execute_query, clean_properties

class RealmProcessor:
    """Handles extraction and loading of Realms."""
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger

    def process(self):
        """Main processing method for realms."""
        self.logger.info("Processing realms...")
        realms = self._extract()
        if realms:
            self._load(realms)
            self.logger.info("-> Finished processing realms.")
        return realms

    def _extract(self):
        self.logger.info("  Extracting from Keycloak...")
        try:
            realms = self.keycloak_admin.get_realms()
            self.logger.info("  -> Found %s realm(s).", len(realms))
            return realms
        except Exception as e:
            self.logger.error("  Error while extracting realms: %s", e, exc_info=True)
            return []

    def _load(self, realms):
        self.logger.info("  Loading into Neo4j...")
        for realm in realms:
            realm_name = realm['realm']
            properties = clean_properties(realm, keys_to_ignore={'realm'})
            query = "MERGE (r:Realm {name: $realm_name}) SET r += $properties"
            params = {
                "realm_name": realm_name,
                "properties": properties
            }
            execute_query(self.neo4j_driver, self.logger, query, params)