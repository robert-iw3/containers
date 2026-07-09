use anyhow::{Context, Result};
use log::{error, info};
use prometheus::{Counter, Registry};
use reqwest::Client;
use serde_json::Value;
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use tokio::sync::mpsc;
use tokio::time;

lazy_static::lazy_static! {
    static ref EVENTS_SENT: Counter = Counter::with_opts(prometheus::opts!(
        "parquet_connector_events_sent_total",
        "Total events sent to Splunk"
    ))
    .unwrap();
    static ref SEND_ERRORS: Counter = Counter::with_opts(prometheus::opts!(
        "parquet_connector_send_errors_total",
        "Total send errors to Splunk"
    ))
    .unwrap();
}

pub async fn send_to_splunk(
    mut rx: mpsc::Receiver<(Vec<Value>, String, usize)>,
    splunk_url: String,
    splunk_token: String,
    batch_size: usize,
    buffer_timeout: f64,
    registry: Arc<Registry>,
) -> Result<()> {
    registry.register(Box::new(EVENTS_SENT.clone()))?;
    registry.register(Box::new(SEND_ERRORS.clone()))?;

    let client = Client::new();
    let mut batch = Vec::new();
    let mut last_flush = SystemTime::now();

    loop {
        let timeout = Duration::from_secs_f64(buffer_timeout);
        let result = time::timeout(timeout, rx.recv()).await;

        match result {
            Ok(Some((events, file_name, count))) => {
                info!("Received {} events from file {}", count, file_name);
                batch.extend(events);

                if batch.len() >= batch_size
                    || last_flush.elapsed().map(|d| d.as_secs_f64() > buffer_timeout).unwrap_or(true)
                {
                    if !batch.is_empty() {
                        send_batch(&client, &splunk_url, &splunk_token, &batch).await?;
                        batch.clear();
                        last_flush = SystemTime::now();
                    }
                }
            }
            Ok(None) => break,
            Err(_) => {
                if !batch.is_empty() {
                    send_batch(&client, &splunk_url, &splunk_token, &batch).await?;
                    batch.clear();
                    last_flush = SystemTime::now();
                }
            }
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    Ok(())
}

async fn send_batch(client: &Client, splunk_url: &str, splunk_token: &str, batch: &[Value]) -> Result<()> {
    let headers = [
        ("Authorization", format!("Splunk {}", splunk_token)),
        ("Content-Type", "application/json".to_string()),
    ];
    let response = client
        .post(splunk_url)
        .headers(headers.into_iter().collect())
        .json(batch)
        .send()
        .await
        .context("Failed to send to Splunk")?;

    if response.status().is_success() {
        info!("Sent {} events to Splunk", batch.len());
        EVENTS_SENT.with_label_values(&["splunk"]).inc_by(batch.len() as f64);
        Ok(())
    } else {
        SEND_ERRORS.with_label_values(&["splunk"]).inc();
        Err(anyhow::anyhow!("Splunk send failed: {}", response.status()))
    }
}