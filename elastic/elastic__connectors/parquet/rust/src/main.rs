use anyhow::{Context, Result};
use dotenvy::dotenv;
use log::{error, info};
use prometheus::Registry;
use std::env;
use std::sync::Arc;
use tokio::signal;
use tokio::sync::mpsc;

mod handler;
mod schema;
mod sender;

use handler::ParquetHandler;
use schema::Schemas;

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();
    dotenv().ok();
    info!("Starting Parquet Connector");

    let data_dir = env::var("DATA_DIR").unwrap_or_else(|_| "/app/data".to_string());
    let schemas_file = env::var("SCHEMAS_FILE").unwrap_or_else(|_| "/app/schemas.yaml".to_string());
    let batch_size = env::var("BATCH_SIZE")
        .unwrap_or_else(|_| "100".to_string())
        .parse::<usize>()
        .context("Invalid BATCH_SIZE")?;
    let buffer_timeout = env::var("BUFFER_TIMEOUT")
        .unwrap_or_else(|_| "2.0".to_string())
        .parse::<f64>()
        .context("Invalid BUFFER_TIMEOUT")?;
    let poll_interval = env::var("POLL_INTERVAL")
        .unwrap_or_else(|_| "60".to_string())
        .parse::<f64>()
        .context("Invalid POLL_INTERVAL")?;
    let state_path = env::var("STATE_PATH").unwrap_or_else(|_| "./state.db".to_string());
    let incremental_enabled = env::var("INCREMENTAL_ENABLED")
        .unwrap_or_else(|_| "false".to_string())
        .parse::<bool>()
        .context("Invalid INCREMENTAL_ENABLED")?;
    let max_files_concurrent = env::var("MAX_FILES_CONCURRENT")
        .unwrap_or_else(|_| "5".to_string())
        .parse::<usize>()
        .context("Invalid MAX_FILES_CONCURRENT")?;
    let max_memory_mb = env::var("MAX_MEMORY_MB")
        .unwrap_or_else(|_| "1024".to_string())
        .parse::<usize>()
        .context("Invalid MAX_MEMORY_MB")?;
    let metrics_port = env::var("METRICS_PORT")
        .unwrap_or_else(|_| "9000".to_string())
        .parse::<u16>()
        .context("Invalid METRICS_PORT")?;
    let es_host = env::var("ES_HOST")
        .unwrap_or_else(|_| "http://localhost:9200".to_string());
    let es_index = env::var("ES_INDEX")
        .unwrap_or_else(|_| "parquet-logs".to_string());
    let es_auth = env::var("ES_AUTH").ok(); // Format: "username:password" or "api_key"
    let sqlcipher_key = env::var("SQLCIPHER_KEY")
        .map(|key| key.to_string())
        .unwrap_or_else(|_| {
            use rand::Rng;
            let key = rand::thread_rng()
                .sample_iter(&rand::distributions::Alphanumeric)
                .take(32)
                .map(char::from)
                .collect::<String>();
            info!("SQLCIPHER_KEY not set, generated random key");
            key
        });

    let schemas = Arc::new(
        Schemas::load(&schemas_file)
            .await
            .context("Failed to load schemas")?,
    );
    let (tx, rx) = mpsc::channel(100);
    let registry = Arc::new(Registry::new());

    let handler = ParquetHandler::new(
        data_dir,
        tx,
        Arc::clone(&schemas),
        batch_size,
        poll_interval,
        state_path,
        incremental_enabled,
        max_files_concurrent,
        max_memory_mb,
        sqlcipher_key,
        Arc::clone(&registry),
    )?;

    // Start metrics server
    let metrics_task = tokio::spawn({
        let registry = Arc::clone(&registry);
        async move {
            prometheus::start_metrics_server(metrics_port, registry)
                .await
                .context("Metrics server failed")
        }
    });

    // Start schema watcher
    let schema_task = tokio::spawn({
        let schemas = Arc::clone(&schemas);
        async move { schemas.watch().await.context("Schema watcher failed") }
    });

    // Start sender
    let sender_task = tokio::spawn(sender::send_to_elastic(
        rx,
        es_host,
        es_index,
        batch_size,
        buffer_timeout,
        es_auth,
        Arc::clone(&registry),
    ));

    // Start handler
    let handler_task = tokio::spawn(handler.start());

    // Handle shutdown
    signal::ctrl_c()
        .await
        .context("Failed to listen for shutdown signal")?;
    info!("Received shutdown signal");
    metrics_task.abort();
    schema_task.abort();
    sender_task.abort();
    handler_task.abort();

    Ok(())
}