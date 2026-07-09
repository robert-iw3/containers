use std::time::Duration;

use reqwest::Client;
use serde_json::Value;
use tokio::sync::mpsc;
use tokio::time;

pub async fn send_to_elasticsearch(
    mut rx: mpsc::Receiver<(Vec<Value>, String, u64)>,
    es_host: String,
    es_index: String,
    batch_size: usize,
    buffer_timeout: Duration,
) -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    let mut batch = Vec::new();
    let mut last_flush = time::Instant::now();

    while let Some((events, _file_path, _new_position)) = rx.recv().await {
        batch.extend(events);

        if batch.len() >= batch_size || last_flush.elapsed() > buffer_timeout {
            if !batch.is_empty() {
                let actions: Vec<Value> = batch
                    .into_iter()
                    .map(|event| serde_json::json!({ "_index": &es_index, "_source": event }))
                    .collect();

                client
                    .post(format!("{}/_bulk", es_host))
                    .header("Content-Type", "application/json")
                    .body(serde_json::to_string(&actions)?)
                    .send()
                    .await?;

                batch = Vec::new();
                last_flush = time::Instant::now();
            }
        }

        time::sleep(Duration::from_millis(100)).await;
    }

    Ok(())
}

pub async fn send_to_splunk(
    mut rx: mpsc::Receiver<(Vec<Value>, String, u64)>,
    splunk_url: String,
    splunk_token: String,
    batch_size: usize,
    buffer_timeout: Duration,
) -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    let mut batch = Vec::new();
    let mut last_flush = time::Instant::now();

    while let Some((events, _file_path, _new_position)) = rx.recv().await {
        batch.extend(events);

        if batch.len() >= batch_size || last_flush.elapsed() > buffer_timeout {
            if !batch.is_empty() {
                client
                    .post(&splunk_url)
                    .header("Authorization", format!("Splunk {}", splunk_token))
                    .header("Content-Type", "application/json")
                    .body(serde_json::to_string(&batch)?)
                    .send()
                    .await?;

                batch = Vec::new();
                last_flush = time::Instant::now();
            }
        }

        time::sleep(Duration::from_millis(100)).await;
    }

    Ok(())
}