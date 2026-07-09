use std::env;
use std::sync::Arc;
use std::time::Duration;

use dotenv::dotenv;
use tokio::signal;
use tokio::sync::mpsc;
use tracing::{error, info};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

mod handler;
mod schema;
mod sender;

use handler::{DbType, SqlHandler};
use schema::Schemas;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();

    // Setup logging
    tracing_subscriber::registry()
        .with(fmt::layer().json())
        .with(EnvFilter::from_env("RUST_LOG"))
        .init();
    info!("Starting SQL Connector");

    let db_type_str = env::var("DB_TYPE").unwrap_or_else(|_| "postgres".to_string());
    let db_type = match db_type_str.as_str() {
        "postgres" => DbType::Postgres,
        "mysql" => DbType::MySql,
        "mssql" => DbType::MsSql,
        "sqlite" => DbType::SQLite,
        "oracle" => DbType::Oracle,
        _ => {
            error!("Unsupported DB type: {}", db_type_str);
            return Err("Unsupported DB type".into());
        },
    };
    let conn_str = env::var("DB_CONN_STR").expect("DB_CONN_STR not set");
    let schemas_file = env::var("SCHEMAS_FILE").unwrap_or_else(|_| "/app/schemas.yaml".to_string());
    let batch_size = env::var("BATCH_SIZE").unwrap_or_else(|_| "100".to_string()).parse::<usize>()?;
    let buffer_timeout = env::var("BUFFER_TIMEOUT").unwrap_or_else(|_| "2.0".to_string()).parse::<f64>()?;
    let poll_interval = env::var("POLL_INTERVAL").unwrap_or_else(|_| "60".to_string()).parse::<u64>()?;
    let state_path = env::var("STATE_PATH").unwrap_or_else(|_| "./state.db".to_string());
    let cdc_enabled = env::var("CDC_ENABLED").unwrap_or_else(|_| "false".to_string()) == "true";
    let max_connections_per_table = env::var("MAX_CONNECTIONS_PER_TABLE").unwrap_or_else(|_| "5".to_string()).parse::<u32>()?;

    let schemas = Arc::new(Schemas::load(&schemas_file)?);
    let (tx, rx) = mpsc::channel(100);

    let mut handler = SqlHandler::new(
        db_type,
        conn_str,
        tx,
        schemas,
        batch_size,
        Duration::from_secs(poll_interval),
        &state_path,
        cdc_enabled,
        max_connections_per_table,
    )?;

    // Start sender task
    let splunk_url = env::var("SPLUNK_HEC_URL").unwrap_or_else(|_| "https://your-splunk-host:8088/services/collector/event".to_string());
    let splunk_token = env::var("SPLUNK_TOKEN").unwrap_or_else(|_| "your-splunk-hec-token".to_string());
    let sender_handle = tokio::spawn(async move {
        if let Err(e) = sender::send_to_splunk(rx, splunk_url, splunk_token, batch_size, Duration::from_secs_f64(buffer_timeout)).await {
            error!("Sender error: {}", e);
        }
    });

    // Start handler
    let handler_handle = tokio::spawn(async move {
        if let Err(e) = handler.start().await {
            error!("Handler error: {}", e);
        }
    });

    // Graceful shutdown
    signal::ctrl_c().await?;
    info!("Received shutdown signal");
    handler_handle.abort();
    sender_handle.abort();

    Ok(())
}