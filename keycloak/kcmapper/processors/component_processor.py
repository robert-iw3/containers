from utils.neo4j_utils import execute_query, clean_properties

class ComponentProcessor:
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger
    def process(self, realm_name):
        self.logger.info("Processing components (User Storage, etc.)...")
        components = self._extract()
        if components:
            self._load(components, realm_name)
        self.logger.info("-> Finished processing components.")
    def _extract(self):
        self.logger.info("  Extracting components from Keycloak...")
        try:
            components = self.keycloak_admin.get_components()
            self.logger.info("  -> Found %s component(s).", len(components))
            return components
        except Exception as e:
            self.logger.error("  Error while extracting components: %s", e, exc_info=True)
            return []
    def _load(self, components, realm_name):
        self.logger.info("  Loading components into Neo4j...")
        for component in components:
            comp_id = component.get('id')
            if not comp_id:
                self.logger.warning("Skipping component without an ID: %s", component)
                continue

            comp_name = component.get('name', f"Unnamed Component ({comp_id[:8]})")
            properties = clean_properties(component, keys_to_ignore={'id'})

            query = """
                MATCH (r:Realm {name: $realm_name})
                MERGE (c:Component {id: $id})
                ON CREATE SET c.name = $name
                SET c += $properties
                MERGE (c)-[:IN_REALM]->(r)
            """
            execute_query(self.neo4j_driver, self.logger, query, {
                "realm_name": realm_name,
                "id": comp_id,
                "name": comp_name,
                "properties": properties
            })
