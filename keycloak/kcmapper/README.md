# KcMapper

KcMapper is a tool for exporting Keycloak configuration data into a Neo4j graph database. This representation allows for the analysis of relationships between realms, clients, users, groups, and roles. The tool includes a web interface to run pre-defined Cypher queries for analysis and security auditing.

## Features

* **Complete Export**: Extracts realms, clients, roles (including composites), groups (with hierarchy), users, client scopes, mappers, and authentication flows.
* **Graph Modeling**: Represents the Keycloak configuration as a graph in Neo4j.
* **Interactive Analysis**: Provides a local web interface to execute pre-defined analysis queries on the exported data.
* **Security Auditing**: Includes queries to help identify potentially weak security configurations.
* **Extendable**: Custom analysis queries can be added by modifying the `webapp/queries.json` file.

## Installation and Usage

This guide covers the local installation of KcMapper. This method requires you to install Python and Neo4j on your machine.

### Prerequisites

* Python 3.9+
* A running Neo4j instance (Community or Desktop).

#### Neo4j Installation (Example for Debian/Ubuntu)

You can install Neo4j Community Edition by following these steps:

```bash
# Add the Neo4j GPG key
wget -O - [https://debian.neo4j.com/neotechnology.gpg.key](https://debian.neo4j.com/neotechnology.gpg.key) | sudo apt-key add -

# Add the Neo4j repository
echo 'deb [https://debian.neo4j.com](https://debian.neo4j.com) stable 5' | sudo tee /etc/apt/sources.list.d/neo4j.list

# Update packages and install Neo4j
sudo apt-get update
sudo apt-get install neo4j -y

# Start the Neo4j service
sudo systemctl start neo4j
```

After installation, navigate to `http://localhost:7474` in your browser and set the initial password (the default is `neo4j`/`neo4j`).

**For other systems (Windows, macOS, etc.):**

* **Neo4j Desktop**: This is the simplest option. Download and install [Neo4j Desktop](https://neo4j.com/download-center/#desktop), which provides a graphical interface for managing your databases.
* **Other Linux Installations**: Follow the official instructions on the [Neo4j installation page](https://neo4j.com/docs/operations-manual/current/installation/).

### Configuration

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/synacktiv/kcmapper.git](https://github.com/synacktiv/kcmapper.git)
    cd kcmapper
    ```

2.  **Set up a Python virtual environment (recommended)**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables**
    Copy the `.env.example` file to `.env`.
    ```bash
    cp .env.example .env
    ```
    Modify the `.env` file to point to your Keycloak instance and your **local** Neo4j database.
    ```dotenv
    # --- Keycloak Connection ---
    KEYCLOAK_URL=http://your-keycloak-server:8080/
    KEYCLOAK_USER=admin
    KEYCLOAK_PASSWORD=your_keycloak_admin_password
    # Optional - for confidential clients
    KEYCLOAK_CLIENT_SECRET=
    # Optional - for users with 2FA enabled
    KEYCLOAK_TOTP=
    # Optional - for mTLS authentication
    KEYCLOAK_CERT_PATH=

    # --- Neo4j Connection (for local environment) ---
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_local_neo4j_password
    ```

### Usage

1.  **Export Data**
    Run the `export` command to populate your Neo4j database.
    ```bash
    python kcmapper_cli.py export
    ```
    * To clean the database before a new export, use the `--clean` option:
        ```bash
        python kcmapper_cli.py export --clean
        ```

2.  **Analyze Data**
    Once the export is complete, launch the web analysis interface.
    ```bash
    python kcmapper_cli.py analyze
    ```
    * The server will be accessible by default at **http://127.0.0.1:5001**.

## Architecture

* **`kcmapper_cli.py`**: Main command-line entry point.
* **`/processors`**: Contains the extraction and loading logic for each Keycloak object type.
* **`/utils`**: Utility functions, primarily for Neo4j connection and data cleaning.
* **`/webapp`**: Contains the Flask web application for data analysis.

## Contributing

Contributions are welcome. Please feel free to open an issue to report a bug or suggest a new feature. To add new analysis queries, modify the `webapp/queries.json` file and submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.