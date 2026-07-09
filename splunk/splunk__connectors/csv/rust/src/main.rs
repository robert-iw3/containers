use std::env;
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::mpsc;
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher};
use dotenv::dotenv;

mod handler;
mod schema;
mod sender;

use handler::CSVHandler;
use schema::Schemas;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();

    let log_dir = env::var("CSV_LOG_DIR").unwrap_or_else(|_| "/var/log/csv_data".to_string());
    let schemas_file = env::var("SCHEMAS_FILE").unwrap_or_else(|_| "/app/schemas.yaml".to_string());
    let batch_size = env::var("BATCH_SIZE").unwrap_or_else(|_| "100".to_string()).parse::<usize>()?;
    let buffer_timeout = env::var("BUFFER_TIMEOUT").unwrap_or_else(|_| "2.0".to_string()).parse::<f64>()?;
    let worker_count = env::var("WORKER_COUNT").unwrap_or_else(|_| num_cpus::get().to_string()).parse::<usize>()?;

    let schemas = Arc::new(Schemas::load(&schemas_file)?);
    let (tx, rx) = mpsc::channel(100);

    let is_splunk = env::var("ENABLE_SPLUNK").unwrap_or_else(|_| "false".to_string()) == "true";
    let handler = Arc::new(CSVHandler::new(is_splunk, tx, schemas.clone(), batch_size));

    // Start sender task
    let sender_handle = if is_splunk {
        let splunk_url = env::var("SPLUNK_HEC_URL").unwrap_or_else(|_| "https://your-splunk-host:8088/services/collector/event".to_string());
        let splunk_token = env::var("SPLUNK_TOKEN").unwrap_or_else(|_| "your-splunk-hec-token".to_string());
        tokio::spawn(sender::send_to_splunk(rx, splunk_url, splunk_token, batch_size, Duration::from_secs_f64(buffer_timeout)))
    } else {
        let es_host = env::var("ES_HOST").unwrap_or_else(|_| "http://localhost:9200".to_string());
        let es_index = env::var("ES_INDEX").unwrap_or_else(|_| "csv-logs".to_string());
        tokio::spawn(sender::send_to_elasticsearch(rx, es_host, es_index, batch_size, Duration::from_secs_f64(buffer_timeout)))
    };

    // Set up filesystem watcher
    let mut watcher = RecommendedWatcher::new(
        move |res| {
            let handler = handler.clone();
            tokio::spawn(async move {
                if let Err(e) = handler.handle_event(res) {
                    eprintln!("Event handling error: {}", e);
                }
            });
        },
        Config::default().with_poll_interval(Duration::from_millis(100)),
    )?;

    watcher.watch(Path::new(&log_dir), RecursiveMode::NonRecursive)?;
    println!("Monitoring CSV logs in {} with {} workers", log_dir, worker_count);

    // Keep the main thread alive
    sender_handle.await??;
    Ok(())
}