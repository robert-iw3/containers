import logging
import json
import os
from flask import Flask, jsonify, request, render_template
from neo4j import GraphDatabase, exceptions as neo4j_exceptions

web_app = Flask(__name__, template_folder='templates')
web_logger = logging.getLogger("kcmapper_web")

def load_queries():
    queries_file_path = os.path.join(os.path.dirname(__file__), 'queries.json')
    try:
        with open(queries_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        web_logger.error("Error loading queries.json: %s", e)
        return {}

@web_app.route('/')
def index():
    return render_template('index.html')

@web_app.route('/api/queries', methods=['GET'])
def get_queries():
    return jsonify(load_queries())

@web_app.route('/api/autocomplete', methods=['POST'])
def get_autocomplete_data():
    driver = None
    try:
        driver = web_app.config['NEO4J_DRIVER']
        data = request.json
        source_query_name = data.get('source_query')
        params = data.get('params', {})
        queries = load_queries()
        query_details = queries.get(source_query_name)
        if not query_details: return jsonify({"error": f"Source query '{source_query_name}' not found."}), 404

        with driver.session() as session:
            result = session.run(query_details["query"], **params)
            suggestions = [record.values()[0] for record in result if record.values()[0]]
            return jsonify(suggestions)
    except Exception as e:
        web_logger.error("Error during autocomplete: %s", e)
        return jsonify({"error": str(e)}), 500

@web_app.route('/api/execute', methods=['POST'])
def execute_api_query():
    driver = None
    try:
        driver = web_app.config['NEO4J_DRIVER']
        data = request.json
        query_name = data.get('query_name')
        params = data.get('params', {})
        queries = load_queries()
        query_details = queries.get(query_name)
        if not query_details: return jsonify({"error": f"Query '{query_name}' not found."}), 404

        with driver.session() as session:
            result = session.run(query_details["query"], **params)
            records = [record.data() for record in result]
            return jsonify({"keys": result.keys(), "records": records})
    except neo4j_exceptions.AuthError:
        return jsonify({"error": "Neo4j authentication failed. Check credentials."}), 401
    except neo4j_exceptions.ServiceUnavailable:
        return jsonify({"error": "Could not connect to Neo4j."}), 503
    except Exception as e:
        web_logger.error("Error during query execution: %s", e, exc_info=True)
        return jsonify({"error": f"An internal error occurred: {e}"}), 500