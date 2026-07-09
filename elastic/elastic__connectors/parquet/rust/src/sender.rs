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
        "Total events sent to Elastic",
        &["destination", "schema"]
    ))
    .unwrap();
    static ref SEND_ERRORS: Counter = Counter::with_opts(prometheus::opts!(
        "parquet_connector_send_errors_total",
        "Total send errors to Elastic",
        &["destination", "schema"]
    ))
    .unwrap();
}

pub async fn send_to_elastic(
    mut rx: mpsc::Receiver<(Vec<Value>, String, usize)>,
    es_host: String,
    es_index: String,
    batch_size: usize,
    buffer_timeout: f64,
    es_auth: Option<String>,
    registry: Arc<Registry>,
) -> Result<()> {
    registry.register(Box::new(EVENTS_SENT.clone()))?;
    registry.register(Box::new(SEND_ERRORS.clone()))?;

    let client = if let Some(auth) = es_auth {
        let mut headers = reqwest::header::HeaderMap::new();
        if auth.contains(':') {
            let (username, password) = auth.split_once(':').unwrap();
            let auth_header = format!("Basic {}", base64::encode(format!("{}:{}", username, password)));
            headers.insert("Authorization", auth_header.parse().unwrap());
            Client::builder().default_headers(headers).build()?
        } else {
            headers.insert("Authorization", format!("ApiKey {}", auth).parse().unwrap());
            Client::builder().default_headers(headers).build()?
        }
    } else {
        Client::new()
    };

    let mut batch = Vec::new();
    let mut last_flush = SystemTime::now();

    loop {
        let timeout = Duration::from_secs_f64(buffer_timeout);
        let result = time::timeout(timeout, rx.recv()).await;

        match result {
            Ok(Some((events, file_name, count))) => {
                let schema_name = file_name.split('.').next().unwrap_or("unknown");
                info!("Received {} events from file {}, schema: {}", count, file_name, schema_name);
                batch.extend(events);

                if batch.len() >= batch_size
                    || last_flush.elapsed().map(|d| d.as_secs_f64() > buffer_timeout).unwrap_or(true)
                {
                    if !batch.is_empty() {
                        send_batch(&client, &es_host, &es_index, &batch, schema_name).await?;
                        batch.clear();
                        last_flush = SystemTime::now();
                    }
                }
            }
            Ok(None) => break,
            Err(_) => {
                if !batch.is_empty() {
                    let schema_name = file_name.split('.').next().unwrap_or("unknown");
                    send_batch(&client, &es_host, &es_index, &batch, schema_name).await?;
                    batch.clear();
                    last_flush = SystemTime::now();
                }
            }
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    Ok(())
}

async fn send_batch(client: &Client, es_host: &str, es_index: &str, batch: &Vec<Value>, schema_name: &str) -> Result<()> {
    let mut body = String::new();
    for doc in batch {
        body.push_str(&format!("{{ \"index\": {{ \"_index\": \"{}\" }} }}\n", es_index));
        body.push_str(&serde_json::to_string(doc)?);
        body.push('\n');
    }

    let response = client
        .post(format!("{}/_bulk", es_host))
        .header("Content-Type", "application/x-ndjson")
        .body(body)
        .send()
        .await
        .context("Failed to send to Elastic")?;

    if response.status().is_success() {
        info!("Sent {} events to Elastic, schema: {}", batch.len(), schema_name);
        EVENTS_SENT.with_label_values(&["elastic", schema_name]).inc_by(batch.len() as f64);
        Ok(())
    } else {
        SEND_ERRORS.with_label_values(&["elastic", schema_name]).inc();
        Err(anyhow::anyhow!("Elastic send failed: {}", response.status()))
    }
}