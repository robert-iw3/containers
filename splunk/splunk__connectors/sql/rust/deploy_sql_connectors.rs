use std::fs::{self, File};
use std::io::Write;
use std::path::Path;
use std::process::Command;

use clap::{Arg, Command as ClapCommand};
use serde::{Deserialize, Serialize};
use serde_yaml;

#[derive(Serialize, Deserialize)]
struct SqlConnectorsConfig {
    schemas_file: String,
    state_path: String,
}

#[derive(Serialize, Deserialize)]
struct SplunkConfig {
    enabled: bool,
    hec_url: String,
    hec_token: String,
}

#[derive(Serialize, Deserialize)]
struct DatabaseConfig {
    db_type: String,
    conn_str: String,
}

#[derive(Serialize, Deserialize)]
struct KubernetesConfig {
    replicas: i32,
}

#[derive(Serialize, Deserialize)]
struct DeploymentConfig {
    method: String,
    namespace: String,
    kubernetes: KubernetesConfig,
}

#[derive(Serialize, Deserialize)]
struct Config {
    sql_connectors: SqlConnectorsConfig,
    splunk: SplunkConfig,
    database: DatabaseConfig,
    deployment: DeploymentConfig,
    buffer_timeout: f64,
    worker_count: i32,
    batch_size: i32,
    poll_interval: u64,
    cdc_enabled: bool,
    max_connections_per_table: u32,
    metrics_port: u16,
}

fn validate_resources() {
    let cpu_count = num_cpus::get();
    let mem_total = psutil::memory::virtual_memory().unwrap().total / 1024 / 1024 / 1024; // GB
    let disk_free = psutil::disk::disk_usage("/").unwrap().free / 1024 / 1024 / 1024; // GB
    if cpu_count < 2 {
        eprintln!("Warning: Less than 2 CPU cores available");
    }
    if mem_total < 2 {
        eprintln!("Warning: Less than 2GB memory available");
    }
    if disk_free < 2 {
        eprintln!("Warning: Less than 2GB disk space available");
    }
}

fn backup_files(config_files: &[&str], backup_dir: &str) {
    fs::create_dir_all(backup_dir).unwrap();
    for src in config_files {
        if Path::new(src).exists() {
            let dst = Path::new(backup_dir).join(Path::new(src).file_name().unwrap());
            fs::copy(src, dst).unwrap();
        }
    }
}

fn deploy_docker(config: &Config, use_podman: bool) -> Result<(), Box<dyn std::error::Error>> {
    let compose_cmd = if use_podman { "podman-compose" } else { "docker-compose" };
    if Command::new(compose_cmd).output().is_err() {
        return Err(format!("{} not found", compose_cmd).into());
    }

    Command::new(compose_cmd)
        .args(&["up", "-d", "--build"])
        .env("SCHEMAS_FILE", &config.sql_connectors.schemas_file)
        .env("STATE_PATH", &config.sql_connectors.state_path)
        .env("SPLUNK_ENABLED", config.splunk.enabled.to_string())
        .env("SPLUNK_HEC_URL", &config.splunk.hec_url)
        .env("SPLUNK_TOKEN", &config.splunk.hec_token)
        .env("DB_TYPE", &config.database.db_type)
        .env("DB_CONN_STR", &config.database.conn_str)
        .env("BATCH_SIZE", config.batch_size.to_string())
        .env("BUFFER_TIMEOUT", config.buffer_timeout.to_string())
        .env("WORKER_COUNT", config.worker_count.to_string())
        .env("POLL_INTERVAL", config.poll_interval.to_string())
        .env("CDC_ENABLED", config.cdc_enabled.to_string())
        .env("MAX_CONNECTIONS_PER_TABLE", config.max_connections_per_table.to_string())
        .env("METRICS_PORT", config.metrics_port.to_string())
        .status()?;

    Ok(())
}

fn deploy_kubernetes(config: &Config) -> Result<(), Box<dyn std::error::Error>> {
    if Command::new("kubectl").output().is_err() {
        return Err("kubectl not found".into());
    }

    let manifests = ["sql-splunk-deployment.yaml"];

    for manifest in &manifests {
        let content = fs::read_to_string(manifest)?;
        let content = content
            .replace("{{namespace}}", &config.deployment.namespace)
            .replace("{{replicas}}", &config.deployment.kubernetes.replicas.to_string())
            .replace("{{splunk_hec_url}}", &config.splunk.hec_url)
            .replace("{{splunk_token}}", &config.splunk.hec_token)
            .replace("{{batch_size}}", &config.batch_size.to_string())
            .replace("{{buffer_timeout}}", &config.buffer_timeout.to_string())
            .replace("{{worker_count}}", &config.worker_count.to_string())
            .replace("{{poll_interval}}", &config.poll_interval.to_string())
            .replace("{{db_type}}", &config.database.db_type)
            .replace("{{db_conn_str}}", &config.database.conn_str)
            .replace("{{cdc_enabled}}", &config.cdc_enabled.to_string())
            .replace("{{max_connections_per_table}}", &config.max_connections_per_table.to_string())
            .replace("{{metrics_port}}", &config.metrics_port.to_string());

        let temp_file = format!("temp_{}", manifest);
        let mut file = File::create(&temp_file)?;
        file.write_all(content.as_bytes())?;

        Command::new("kubectl")
            .args(&["apply", "-f", &temp_file])
            .status()?;

        fs::remove_file(&temp_file)?;
    }

    Ok(())
}

fn deploy_ansible(config: &Config) -> Result<(), Box<dyn std::error::Error>> {
    if Command::new("ansible-playbook").output().is_err() {
        return Err("ansible-playbook not found".into());
    }

    Command::new("ansible-playbook")
        .args(&["deploy_sql_connectors.yml", "-e", &format!("config_file={}", "deploy_config.yaml")])
        .status()?;

    Ok(())
}

fn cleanup_docker(use_podman: bool) -> Result<(), Box<dyn std::error::Error>> {
    let compose_cmd = if use_podman { "podman-compose" } else { "docker-compose" };
    if Command::new(compose_cmd).output().is_ok() {
        Command::new(compose_cmd)
            .args(&["down", "-v"])
            .status()?;
    }
    Ok(())
}

fn cleanup_kubernetes(config: &Config) -> Result<(), Box<dyn std::error::Error>> {
    if Command::new("kubectl").output().is_ok() {
        let manifests = ["sql-splunk-deployment.yaml"];
        for manifest in &manifests {
            Command::new("kubectl")
                .args(&["delete", "-f", manifest, "-n", &config.deployment.namespace])
                .status()?;
        }
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let matches = ClapCommand::new("Deploy SQL Connectors")
        .arg(Arg::new("config").default_value("deploy_config.yaml").help("Path to configuration file"))
        .arg(Arg::new("cleanup").long("cleanup").action(clap::ArgAction::SetTrue).help("Cleanup deployment"))
        .get_matches();

    let config_file = matches.get_one::<String>("config").unwrap();
    let cleanup = matches.get_flag("cleanup");

    let config_files = [
        "deploy_config.yaml",
        "docker-compose.yml",
        "Dockerfile",
        "schemas.yaml",
        "sql-splunk-deployment.yaml",
        "deploy_sql_connectors.yml",
    ];

    if cleanup {
        println!("Cleaning up SQL connectors deployment...");
        let config = load_config(config_file)?;
        match config.deployment.method.as_str() {
            "docker" => cleanup_docker(false)?,
            "podman" => cleanup_docker(true)?,
            "kubernetes" => cleanup_kubernetes(&config)?,
            "ansible" => deploy_ansible(&config)?,
            _ => return Err(format!("Unsupported deployment method: {}", config.deployment.method).into()),
        }
        return Ok(());
    }

    validate_resources();
    let config = load_config(config_file)?;
    let backup_dir = format!("backup/{}", chrono::Local::now().format("%Y%m%d_%H%M%S"));
    backup_files(&config_files, &backup_dir);

    match config.deployment.method.as_str() {
        "docker" => deploy_docker(&config, false)?,
        "podman" => deploy_docker(&config, true)?,
        "kubernetes" => deploy_kubernetes(&config)?,
        "ansible" => deploy_ansible(&config)?,
        _ => return Err(format!("Unsupported deployment method: {}", config.deployment.method).into()),
    }

    println!("SQL connectors deployed");
    Ok(())
}

fn load_config(config_file: &str) -> Result<Config, Box<dyn std::error::Error>> {
    let file = File::open(config_file)?;
    let config: Config = serde_yaml::from_reader(file)?;
    Ok(config)
}