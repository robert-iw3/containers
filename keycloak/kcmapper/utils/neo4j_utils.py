import json
import logging

def execute_query(driver, logger, query, parameters=None):
    """Executes a Cypher query in a session."""
    with driver.session() as session:
        try:
            session.run(query, parameters)
        except Exception as e:
            logger.error("Error executing Neo4j query: %s", e)
            logger.debug("Failed Query: %s", query)
            logger.debug("Failed Parameters: %s", parameters)

def _flatten_and_clean_dict(data, parent_key='', sep='.'):
    """Recursively flattens a nested dictionary and cleans values."""
    items = {}
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(_flatten_and_clean_dict(value, new_key, sep=sep))
        elif isinstance(value, list):
            items[new_key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            items[new_key] = str(value).lower()
        elif value is None:
            items[new_key] = ''
        else:
            items[new_key] = value
    return items

def clean_properties(properties, keys_to_ignore=None):
    """
    Cleans a dictionary of properties to be compatible with Neo4j.
    - Flattens nested dictionaries, prefixing keys.
    - Converts booleans to strings.
    - Converts None to empty strings.
    - Serializes lists to JSON strings.
    - Ignores specified keys.
    """
    cleaned = {}
    if not isinstance(properties, dict):
        return {}

    ignore_set = set(keys_to_ignore) if keys_to_ignore else set()

    for key, value in properties.items():
        if key in ignore_set:
            continue

        if isinstance(value, dict):
            cleaned.update(_flatten_and_clean_dict(value, parent_key=key))
        elif isinstance(value, list):
            cleaned[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            cleaned[key] = str(value).lower()
        elif value is None:
            cleaned[key] = ''
        else:
            cleaned[key] = value
    return cleaned

def clean_database(driver, logger):
    """Deletes ALL nodes, relationships, indexes, and constraints from the database."""
    logger.warning("--- CLEANING DATABASE ---")
    logger.warning("The --clean flag was used. This will delete ALL data and schema in the database.")

    with driver.session() as session:
        try:
            # 1. Get and drop all constraints
            logger.info("Dropping all constraints...")
            constraints = session.run("SHOW CONSTRAINTS YIELD name").data()
            for constraint in constraints:
                constraint_name = constraint['name']
                logger.debug("Dropping constraint: %s", constraint_name)
                # Use backticks to handle special characters in names
                session.run(f"DROP CONSTRAINT `{constraint_name}`")
            logger.info("-> All constraints dropped.")

            # 2. Get and drop all standalone indexes
            logger.info("Dropping all standalone indexes...")
            # Filter out indexes backing constraints as they are dropped automatically with constraints
            indexes = session.run("SHOW INDEXES YIELD name, type WHERE type <> 'CONSTRAINT'").data()
            for index in indexes:
                index_name = index['name']
                logger.debug("Dropping index: %s", index_name)
                session.run(f"DROP INDEX `{index_name}`")
            logger.info("-> All standalone indexes dropped.")

            # 3. Delete all remaining nodes and relationships
            logger.info("Deleting all nodes and relationships...")
            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume()
            logger.info(
                "-> All nodes and relationships deleted. Nodes deleted: %d, Relationships deleted: %d.",
                summary.counters.nodes_deleted,
                summary.counters.relationships_deleted
            )
            logger.info("Database cleaning complete.")
        except Exception as e:
            logger.error("An error occurred during database cleaning: %s", e, exc_info=True)