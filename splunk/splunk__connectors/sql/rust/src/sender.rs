use std::time::Duration;

use prometheus::IntCounterVec;
use reqwest::Client;
use serde_json::Value;
use thiserror::Error;
use tokio::sync::mpsc;
use tokio::time;
use tracing::{error, info};

lazy_static::lazy_static! {
    static ref EVENTS_SENT: IntCounterVec = prometheus::register_int_counter_vec!(
        "sql_connector_events_sent_total",
        "Total number of events sent to Splunk",
        &["destination"]
    ).unwrap();
    static ref SEND_ERRORS: IntCounterVec = prometheus::register_int_counter_vec!(
        "sql_connector_send_errors_total",
        "Total number of send errors to Splunk",
        &["destination"]
    ).unwrap();
}

#[derive(Error, Debug)]
pub enum SenderError {
    #[error("Request error: {0}")]
    Reqwest(#[from] reqwest::Error),
    #[error("Serialization error: {0}")]
    Serde(#[from] serde_json::Error),
    #[error("Receive error: {0}")]
    Recv(#[from] mpsc::error::RecvError),
}

pub async fn send_to_splunk(
    mut rx: mpsc::Receiver<(Vec<Value>, String, u64)>,
    splunk_url: String,
    splunk_token: String,
    batch_size: usize,
    buffer_timeout: Duration,
) -> Result<(), SenderError> {
    let client = Client::new();
    let mut batch = Vec::new();
    let mut last_flush = time::Instant::now();

    while let Some((events, table, count)) = rx.recv().await {
        info!("Received {} events from table {}", count, table);
        batch.extend(events);

        if batch.len() >= batch_size || last_flush.elapsed() > buffer_timeout {
            if !batch.is_empty() {
                let body = serde_json::to_string(&batch)?;
                let res = client
                    .post(&splunk_url)
                    .header("Authorization", format!("Splunk {}", splunk_token))
                    .header("Content-Type", "application/json")
                    .body(body)
                    .send()
                    .await;
                match res {
                    Ok(res) if res.status().is_success() => {
                        info!("Sent {} events to Splunk", batch.len());
                        EVENTS_SENT.with_label_values(&["splunk"]).inc_by(batch.len() as u64);
                    }
                    Ok(res) => {
                        SEND_ERRORS.with_label_values(&["splunk"]).inc();
                        error!("Splunk send failed: {}", res.status());
                    }
                    Err(e) => {
                        SEND_ERRORS.with_label_values(&["splunk"]).inc();
                        error!("Splunk send error: {}", e);
                    }
                }
                batch = Vec::new();
                last_flush = time::Instant::now();
            }
        }

        time::sleep(Duration::from_millis(100)).await;
    }

    Ok(())
}