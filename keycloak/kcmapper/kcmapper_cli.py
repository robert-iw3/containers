import argparse
import sys
import os
import logging
from dotenv import load_dotenv

from keycloak import KeycloakAdmin
from neo4j import GraphDatabase, exceptions as neo4j_exceptions
from webapp.server import web_app
from utils.neo4j_utils import clean_database
from processors.realm_processor import RealmProcessor
from processors.client_processor import ClientProcessor
from processors.role_processor import RoleProcessor
from processors.group_processor import GroupProcessor
from processors.user_processor import UserProcessor
from processors.clientscope_processor import ClientScopeProcessor
from processors.authenticationflow_processor import AuthenticationFlowProcessor
from processors.idp_processor import IdpProcessor
from processors.component_processor import ComponentProcessor

def setup_logging(log_level, log_file):
    """Configures the logging system."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("keycloak_exporter")
    logger.setLevel(level)
    if logger.hasHandlers(): logger.handlers.clear()

    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if log_file:
        fh = logging.FileHandler(log_file, mode='w')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

def run_export(args, logger):
    """Orchestrates the entire extraction and loading process."""
    neo4j_driver = None
    try:
        neo4j_driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
        neo4j_driver.verify_connectivity()
        logger.info("Successfully connected to Neo4j.")

        if args.clean:
            clean_database(neo4j_driver, logger)

        logger.info("Starting Keycloak data extraction...")
        keycloak_admin = KeycloakAdmin(
            server_url=args.keycloak_url,
            username=args.keycloak_user,
            password=args.keycloak_password,
            realm_name=args.keycloak_realm,
            client_id=args.keycloak_client_id,
            verify=True,
            client_secret_key=args.keycloak_secret,
            totp=args.keycloak_totp,
            cert=args.keycloak_cert_path
        )
        logger.info("Successfully connected to Keycloak (realm '%s').", args.keycloak_realm)

        # Instantiate all processors
        realm_processor = RealmProcessor(keycloak_admin, neo4j_driver, logger)
        client_processor = ClientProcessor(keycloak_admin, neo4j_driver, logger)
        role_processor = RoleProcessor(keycloak_admin, neo4j_driver, logger)
        group_processor = GroupProcessor(keycloak_admin, neo4j_driver, logger)
        user_processor = UserProcessor(keycloak_admin, neo4j_driver, logger)
        clientscope_processor = ClientScopeProcessor(keycloak_admin, neo4j_driver, logger)
        authflow_processor = AuthenticationFlowProcessor(keycloak_admin, neo4j_driver, logger)
        idp_processor = IdpProcessor(keycloak_admin, neo4j_driver, logger)
        component_processor = ComponentProcessor(keycloak_admin, neo4j_driver, logger)

        realms = realm_processor.process()
        if not realms:
            logger.warning("No realms found or an error occurred. Stopping script.")
            return

        for realm in realms:
            realm_name = realm['realm']
            logger.info("--- Processing realm: %s ---", realm_name)
            keycloak_admin.change_current_realm(realm_name)

            clients = client_processor.process(realm_name)
            role_processor.process(clients, realm_name)
            group_processor.process(realm_name, clients)
            user_processor.process(realm_name, clients)
            clientscope_processor.process(realm_name, clients)
            authflow_processor.process(realm_name)
            idp_processor.process(realm_name)
            component_processor.process(realm_name)

    except neo4j_exceptions.AuthError as e:
        logger.critical("Neo4j authentication error: %s", e)
    except Exception as e:
        logger.critical("An unexpected error occurred: %s", e, exc_info=True)
    finally:
        if neo4j_driver:
            neo4j_driver.close()
            logger.info("Neo4j connection closed.")
    logger.info("Extraction and loading finished!")

def run_analyzer(args):
    """Launches the Flask web server."""
    logger = logging.getLogger("kcmapper_web")
    logger.info("Launching web server for analysis...")
    driver = None
    try:
        driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))
        driver.verify_connectivity()
        web_app.config['NEO4J_DRIVER'] = driver
        logger.info(f"--> KcMapper Analyzer available at http://{args.host}:{args.port}")
        web_app.run(host=args.host, port=args.port, debug=False)
    except Exception as e:
        logger.critical(f"Failed to start web server: {e}", exc_info=True)
    finally:
        if driver:
            driver.close()

def main():
    """Main script entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="KcMapper: A tool to export and analyze Keycloak data.",
                                     formatter_class=argparse.RawTextHelpFormatter)

    subparsers = parser.add_subparsers(dest='command', required=True, help='Action to perform')

    # --- EXPORT Sub-command ---
    parser_export = subparsers.add_parser('export', help='Export data from Keycloak to Neo4j.')
    log_group = parser_export.add_argument_group('Logging')
    log_group.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="Set the logging level.")
    log_group.add_argument('--log-file', default='kcmapper_export.log', help="Path to the log file.")
    kc_group = parser_export.add_argument_group('Keycloak Connection')
    kc_group.add_argument('--keycloak-url', default=os.getenv("KEYCLOAK_URL"), required=not os.getenv("KEYCLOAK_URL"), help='Keycloak server URL')
    kc_group.add_argument('--keycloak-realm', default=os.getenv("KEYCLOAK_REALM", "master"), help='Keycloak realm for admin auth')
    kc_group.add_argument('--keycloak-client-id', default=os.getenv("KEYCLOAK_CLIENT_ID", "admin-cli"), help='Client ID for the admin API')
    kc_group.add_argument('--keycloak-user', default=os.getenv("KEYCLOAK_USER"), required=not os.getenv("KEYCLOAK_USER"), help='Keycloak admin username')
    kc_group.add_argument('--keycloak-password', default=os.getenv("KEYCLOAK_PASSWORD"), help='Keycloak admin password (or use env var)')
    kc_group.add_argument('--keycloak-secret', default=os.getenv("KEYCLOAK_CLIENT_SECRET"), help='Keycloak client secret (for confidential clients)')
    kc_group.add_argument('--keycloak-totp', default=os.getenv("KEYCLOAK_TOTP"), help='Time-based One-Time Password for 2FA')
    kc_group.add_argument('--keycloak-cert-path', default=os.getenv("KEYCLOAK_CERT_PATH"), help='Path to client certificate for mTLS')

    neo_group_export = parser_export.add_argument_group('Neo4j Connection')
    neo_group_export.add_argument('--neo4j-uri', default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help='Neo4j connection URI')
    neo_group_export.add_argument('--neo4j-user', default=os.getenv("NEO4J_USER", "neo4j"), help='Neo4j username')
    neo_group_export.add_argument('--neo4j-password', default=os.getenv("NEO4J_PASSWORD"), help='Neo4j password (or use env var)')
    parser_export.add_argument('--clean', action='store_true', help='Clean Neo4j DB before extraction.')

    # --- ANALYZE Sub-command ---
    parser_analyze = subparsers.add_parser('analyze', help='Launch the web UI for interactive analysis.')
    neo_group_analyze = parser_analyze.add_argument_group('Neo4j Connection (for Web UI)')
    neo_group_analyze.add_argument('--neo4j-uri', default=os.getenv("NEO4J_URI", "bolt://localhost:7687"), help='Neo4j connection URI')
    neo_group_analyze.add_argument('--neo4j-user', default=os.getenv("NEO4J_USER", "neo4j"), help='Neo4j username')
    neo_group_analyze.add_argument('--neo4j-password', default=os.getenv("NEO4J_PASSWORD"), help='Neo4j password (or use env var)')
    web_group = parser_analyze.add_argument_group('Web Server')
    web_group.add_argument('--host', type=str, default='127.0.0.1', help='Host for the web server.')
    web_group.add_argument('--port', type=int, default=5001, help='Port for the web server.')

    args = parser.parse_args()

    if args.command == 'export':
        if not args.keycloak_password: sys.exit("Error: Keycloak password is required.")
        if not args.neo4j_password: sys.exit("Error: Neo4j password is required.")
        logger = setup_logging(args.log_level, args.log_file)
        run_export(args, logger)
    elif args.command == 'analyze':
        if not args.neo4j_password: sys.exit("Error: Neo4j password is required for the web UI.")
        run_analyzer(args)

if __name__ == "__main__":
    main()