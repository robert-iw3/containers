from utils.neo4j_utils import execute_query, clean_properties

class AuthenticationFlowProcessor:
    def __init__(self, keycloak_admin, neo4j_driver, logger):
        self.keycloak_admin = keycloak_admin
        self.neo4j_driver = neo4j_driver
        self.logger = logger
    def process(self, realm_name):
        self.logger.info("Processing authentication flows...")
        flows = self._extract()
        if flows:
            self._load(flows, realm_name)
        self.logger.info("-> Finished processing authentication flows.")
    def _extract(self):
        self.logger.info("  Extracting auth flows from Keycloak...")
        try:
            flows = self.keycloak_admin.get_authentication_flows()
            self.logger.info("  -> Found %s authentication flow(s).", len(flows))
            return flows
        except Exception as e:
            self.logger.error("  Error while extracting auth flows: %s", e, exc_info=True)
            return []
    def _load(self, flows, realm_name):
        self.logger.info("  Loading auth flows into Neo4j...")
        for flow in flows:
            properties = clean_properties(flow, keys_to_ignore={'id', 'alias', 'authenticationExecutions'})
            query = "MATCH (r:Realm {name: $realm_name}) MERGE (f:AuthenticationFlow {id: $id, alias: $alias}) SET f += $properties MERGE (f)-[:IN_REALM]->(r)"
            execute_query(self.neo4j_driver, self.logger, query, {"realm_name": realm_name, "id": flow['id'], "alias": flow['alias'], "properties": properties})
            if 'authenticationExecutions' in flow and flow['authenticationExecutions']:
                for execution in flow['authenticationExecutions']:
                    self._load_execution(execution, flow['id'])
    def _load_execution(self, execution, flow_id):
        execution_id = execution.get('id')
        if not execution_id:
            self.logger.debug("Skipping execution without an ID in flow %s: %s", flow_id, execution)
            return

        properties = clean_properties(execution, keys_to_ignore={'id', 'authenticator'})
        query = "MATCH (f:AuthenticationFlow {id: $flow_id}) MERGE (e:AuthenticationExecution {id: $id}) ON CREATE SET e.authenticator = $authenticator SET e += $properties MERGE (f)-[:HAS_EXECUTION]->(e)"
        execute_query(self.neo4j_driver, self.logger, query, {"flow_id": flow_id, "id": execution_id, "authenticator": execution.get('authenticator'), "properties": properties})