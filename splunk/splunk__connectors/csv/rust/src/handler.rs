use std::collections::HashMap;
use std::fs::File;
use std::io::{Seek, SeekFrom};
use std::path::Path;
use std::sync::Arc;

use csv::ReaderBuilder;
use notify::Event;
use serde_json::{Value, json};
use tokio::sync::mpsc;

use crate::schema::{Schema, Schemas};

pub struct CSVHandler {
    is_splunk: bool,
    tx: mpsc::Sender<(Vec<Value>, String, u64)>,
    schemas: Arc<Schemas>,
    batch_size: usize,
    file_positions: HashMap<String, u64>,
}

impl CSVHandler {
    pub fn new(is_splunk: bool, tx: mpsc::Sender<(Vec<Value>, String, u64)>, schemas: Arc<Schemas>, batch_size: usize) -> Self {
        CSVHandler {
            is_splunk,
            tx,
            schemas,
            batch_size,
            file_positions: HashMap::new(),
        }
    }

    pub async fn handle_event(&mut self, res: notify::Result<Event>) -> Result<(), Box<dyn std::error::Error>> {
        let event = res?;
        if event.kind.is_create() || event.kind.is_modify() {
            for path in event.paths {
                if path.extension().map_or(false, |ext| ext == "csv") {
                    self.process_file(&path).await?;
                }
            }
        }
        Ok(())
    }

    fn detect_delimiter(&self, file_path: &Path) -> char {
        let file = File::open(file_path).unwrap();
        let sample = std::io::read_to_string(&file).unwrap_or_default();
        for delim in [',', ';', '\t', '|'] {
            if sample.contains(delim) && sample.split(delim).count() > 1 {
                return delim;
            }
        }
        std::env::var("CSV_DELIMITER").unwrap_or_else(|_| ",".to_string()).chars().next().unwrap_or(',')
    }

    async fn process_file(&mut self, file_path: &Path) -> Result<(), Box<dyn std::error::Error>> {
        let file_path_str = file_path.to_string_lossy().to_string();
        let position = self.file_positions.get(&file_path_str).copied().unwrap_or(0);

        let delimiter = self.detect_delimiter(file_path);
        let mut file = File::open(file_path)?;
        file.seek(SeekFrom::Start(position))?;

        let mut reader = ReaderBuilder::new()
            .delimiter(delimiter as u8)
            .from_reader(file);

        let mut batch = Vec::new();
        let mut event_count = 0;
        let start_pos = position;

        for result in reader.deserialize::<HashMap<String, String>>() {
            let row = result?;
            if let Some(schema) = self.schemas.get_schema(&row) {
                let event = if self.is_splunk {
                    self.transform_to_cim(&row, &schema)
                } else {
                    self.transform_to_ecs(&row, &schema)
                };
                batch.push(event);
                event_count += 1;
            } else {
                eprintln!("No schema found for event in {}", file_path_str);
                continue;
            }

            if event_count >= self.batch_size || file.metadata()?.len() - start_pos >= 1024 * 1024 {
                break;
            }
        }

        let new_position = file.seek(SeekFrom::Current(0))?;
        self.file_positions.insert(file_path_str.clone(), new_position);

        if !batch.is_empty() {
            self.tx.send((batch, file_path_str, new_position)).await?;
        }

        Ok(())
    }

    fn transform_to_ecs(&self, event: &HashMap<String, String>, schema: &Schema) -> Value {
        let mut ecs = json!({
            "@timestamp": event.get(&schema.mappings.ecs.get("timestamp").unwrap_or("timestamp".to_string())).unwrap_or(&chrono::Utc::now().to_rfc3339()),
            "event": {
                "kind": "event",
                "dataset": format!("csv.{}", schema.name),
                "id": event.get(&schema.mappings.ecs.get("event_id").unwrap_or("id".to_string())).unwrap_or_default(),
                "category": {
                    let category = schema.mappings.ecs.get("event_category").unwrap_or(&"unknown".to_string());
                    if category.starts_with('[') {
                        serde_json::from_str(category).unwrap_or(json!(["unknown"]))
                    } else {
                        json!([category])
                    }
                }
            },
            "csv": {
                "schema": &schema.name,
                "raw": event
            }
        });

        for (key, value) in &schema.mappings.ecs {
            if !["timestamp", "event_id", "event_category"].contains(&key.as_str()) {
                let target_value = if value.starts_with('"') && value.ends_with('"') {
                    // Handle fixed string values (e.g., "modbus", "dnp3")
                    json!(value.trim_matches('"'))
                } else {
                    // Treat as CSV field reference
                    json!(event.get(value).unwrap_or_default())
                };

                let keys = key.split('/').collect::<Vec<_>>();
                let mut target = &mut ecs;
                for k in keys.iter().take(keys.len() - 1) {
                    target = target.get_mut(k).unwrap_or(&mut json!({}));
                }
                target[keys.last().unwrap()] = target_value;
            }
        }

        ecs
    }

    fn transform_to_cim(&self, event: &HashMap<String, String>, schema: &Schema) -> Value {
        let mut cim = json!({
            "time": event.get(&schema.mappings.cim.get("time").unwrap_or("timestamp".to_string())).unwrap_or(&chrono::Utc::now().timestamp().to_string()),
            "vendor_product": "CSV_Connector",
            "schema": &schema.name
        });

        for (key, value) in &schema.mappings.cim {
            if key != "sourcetype" {
                let target_value = if value.starts_with('"') && value.ends_with('"') {
                    // Handle fixed string values (e.g., "modbus", "dnp3")
                    json!(value.trim_matches('"'))
                } else {
                    // Treat as CSV field reference
                    json!(event.get(value).unwrap_or_default())
                };
                cim[key] = target_value;
            }
        }

        json!({
            "event": cim,
            "sourcetype": schema.mappings.cim.get("sourcetype").map_or(format!("csv:{}", schema.name), |v| v.to_string())
        })
    }
}