use std::sync::{Arc, Mutex};
use tokio::sync::mpsc;
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher};
use quick_xml::events::Event as XmlEvent;
use quick_xml::Reader;
use serde::{Deserialize, Serialize};
use serde_yaml;
use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader, Seek, SeekFrom};
use std::path::Path;
use tokio::time::{self, Duration};
use reqwest::Client;
use std::env;
use chrono::prelude::*;
use uuid::Uuid;

#[derive(Debug, Deserialize)]
struct Config {
    xml_connectors: XmlConnectorsConfig,
    splunk: SplunkConfig,
    elasticsearch: ElasticsearchConfig,
    deployment: DeploymentConfig,
    buffer_timeout: f64,
    worker_count: usize,
    batch_size: usize,
    delimiter: String,
}

#[derive(Debug, Deserialize)]
struct XmlConnectorsConfig {
    log_dir: String,
    schemas_file: String,
}

#[derive(Debug, Deserialize)]
struct SplunkConfig {
    enabled: bool,
    hec_url: String,
    hec_token: String,
}

#[derive(Debug, Deserialize)]
struct ElasticsearchConfig {
    enabled: bool,
    host: String,
    index: String,
}

#[derive(Debug, Deserialize)]
struct DeploymentConfig {
    method: String,
    namespace: String,
}

#[derive(Debug, Deserialize)]
struct Schema {
    name: String,
    schema_key: String,
    schema_value: String,
    mappings: HashMap<String, HashMap<String, String>>,
}

#[derive(Debug, Serialize)]
struct EcsEvent {
    #[serde(rename = "@timestamp")]
    timestamp: String,
    event: Event,
    xml: XmlData,
    #[serde(flatten)]
    extra: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize)]
struct Event {
    kind: String,
    dataset: String,
    #[serde(flatten)]
    extra: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Serialize)]
struct XmlData {
    schema: String,
    raw: HashMap<String, String>,
}

#[derive(Debug, Serialize)]
struct CimEvent {
    event: CimEventData,
    sourcetype: String,
}

#[derive(Debug, Serialize)]
struct CimEventData {
    time: String,
    schema: String,
    vendor_product: String,
    #[serde(flatten)]
    extra: HashMap<String, serde_json::Value>,
}

async fn load_config(path: &str) -> Result<Config, Box<dyn std::error::Error>> {
    let file = File::open(path)?;
    let config: Config = serde_yaml::from_reader(file)?;
    Ok(config)
}

async fn load_schemas(path: &str) -> Result<Vec<Schema>, Box<dyn std::error::Error>> {
    let file = File::open(path)?;
    let yaml: HashMap<String, Vec<Schema>> = serde_yaml::from_reader(file)?;
    Ok(yaml.get("schemas").cloned().unwrap_or_default())
}

fn get_schema(event: &HashMap<String, String>, schemas: &[Schema]) -> Option<&Schema> {
    for schema in schemas {
        if event.get(&schema.schema_key).map_or(false, |v| v == &schema.schema_value) {
            return Some(schema);
        }
    }
    None
}

fn transform_to_ecs(event: &HashMap<String, String>, schema: &Schema) -> EcsEvent {
    let mappings = schema.mappings.get("ecs").unwrap_or(&HashMap::new());
    let timestamp = event
        .get(mappings.get("timestamp").unwrap_or(&"timestamp".to_string()))
        .map(|s| s.to_string())
        .unwrap_or_else(|| Utc::now().to_rfc3339());

    let mut ecs_extra = HashMap::new();
    for (ecs_field, xml_field) in mappings.iter() {
        if let Some(value) = event.get(xml_field) {
            // Handle nested ECS fields (e.g., source.ip, event.category)
            let parts: Vec<&str> = ecs_field.split('.').collect();
            if parts.len() == 1 {
                // Handle special case for event_category as a list
                if ecs_field == "event_category" {
                    if value.starts_with('[') {
                        if let Ok(list) = serde_json::from_str::<Vec<String>>(value) {
                            ecs_extra.insert(ecs_field.clone(), serde_json::to_value(list).unwrap());
                        } else {
                            ecs_extra.insert(ecs_field.clone(), serde_json::Value::String(value.clone()));
                        }
                    } else {
                        ecs_extra.insert(ecs_field.clone(), serde_json::Value::String(value.clone()));
                    }
                } else {
                    // Try parsing as number for fields like ports, bytes, etc.
                    if let Ok(num) = value.parse::<i64>() {
                        ecs_extra.insert(ecs_field.clone(), serde_json::Value::Number(num.into()));
                    } else {
                        ecs_extra.insert(ecs_field.clone(), serde_json::Value::String(value.clone()));
                    }
                }
            } else {
                // Nested fields (e.g., source.ip, destination.port)
                let mut current = &mut ecs_extra;
                for (i, part) in parts.iter().enumerate() {
                    if i == parts.len() - 1 {
                        if let Ok(num) = value.parse::<i64>() {
                            current.insert(part.to_string(), serde_json::Value::Number(num.into()));
                        } else {
                            current.insert(part.to_string(), serde_json::Value::String(value.clone()));
                        }
                    } else {
                        current = current
                            .entry(part.to_string())
                            .or_insert_with(|| serde_json::Value::Object(serde_json::Map::new()))
                            .as_object_mut()
                            .unwrap();
                    }
                }
            }
        }
    }

    EcsEvent {
        timestamp,
        event: Event {
            kind: "event".to_string(),
            dataset: format!("xml.{}", schema.name),
            extra: ecs_extra,
        },
        xml: XmlData {
            schema: schema.name.clone(),
            raw: event.clone(),
        },
        extra: HashMap::new(), // Additional top-level ECS fields can be added here
    }
}

fn transform_to_cim(event: &HashMap<String, String>, schema: &Schema) -> CimEvent {
    let mappings = schema.mappings.get("cim").unwrap_or(&HashMap::new());
    let mut cim_extra = HashMap::new();

    for (cim_field, xml_field) in mappings.iter() {
        if let Some(value) = event.get(xml_field) {
            // Try parsing as number for fields like ports, bytes, etc.
            if let Ok(num) = value.parse::<i64>() {
                cim_extra.insert(cim_field.clone(), serde_json::Value::Number(num.into()));
            } else {
                cim_extra.insert(cim_field.clone(), serde_json::Value::String(value.clone()));
            }
        }
    }

    // Ensure time is always present
    let time = event
        .get(mappings.get("time").unwrap_or(&"timestamp".to_string()))
        .map(|s| s.to_string())
        .unwrap_or_else(|| Utc::now().timestamp().to_string());

    CimEvent {
        event: CimEventData {
            time,
            schema: schema.name.clone(),
            vendor_product: "XML_Connector".to_string(),
            extra: cim_extra,
        },
        sourcetype: mappings
            .get("sourcetype")
            .map(|s| s.to_string())
            .unwrap_or(format!("xml:{}", schema.name)),
    }
}

async fn process_xml_chunk(
    file_path: &str,
    position: u64,
    schemas: &[Schema],
    batch_size: usize,
    delimiter: &str,
) -> Result<(Vec<EcsEvent>, Vec<CimEvent>, String, u64), Box<dyn std::error::Error>> {
    let mut ecs_batch = Vec::new();
    let mut cim_batch = Vec::new();
    let mut file = File::open(file_path)?;
    file.seek(SeekFrom::Start(position))?;
    let reader = BufReader::new(file);
    let mut xml_reader = Reader::from_reader(reader);
    xml_reader.trim_text(true);
    let mut buf = Vec::new();
    let mut event = HashMap::new();
    let mut current_element = String::new();
    let mut current_schema: Option<&Schema> = None;
    let mut event_count = 0;
    let mut depth = 0;

    // Handle delimiter-separated XML documents (e.g., concatenated XML events)
    let mut xml_string = String::new();
    let mut file_content = String::new();
    let mut file_reader = BufReader::new(File::open(file_path)?);
    file_reader.seek(SeekFrom::Start(position))?;
    file_reader.read_to_string(&mut file_content)?;
    let xml_chunks = if delimiter.is_empty() {
        vec![file_content.as_str()]
    } else {
        file_content.split(&delimiter).collect()
    };

    let mut new_position = position;
    for chunk in xml_chunks {
        if event_count >= batch_size {
            break;
        }
        xml_reader = Reader::from_str(chunk);
        xml_reader.trim_text(true);
        event.clear();
        current_schema = None;

        loop {
            match xml_reader.read_event_into(&mut buf) {
                Ok(XmlEvent::Start(ref e)) => {
                    let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                    depth += 1;
                    if depth == 1 {
                        // Root element: determine schema
                        current_schema = get_schema(&event, schemas);
                        if current_schema.is_none() {
                            // Try to infer schema from root element name if schema_key is not yet populated
                            let temp_event = HashMap::from([(
                                "event_type".to_string(),
                                tag.clone(),
                            )]);
                            current_schema = get_schema(&temp_event, schemas);
                            if current_schema.is_none() {
                                eprintln!("No schema found for root element {} in {}", tag, file_path);
                                break;
                            }
                            event.insert("event_type".to_string(), tag.clone());
                        }
                    }
                    current_element = tag;
                }
                Ok(XmlEvent::Text(ref e)) => {
                    if !current_element.is_empty() {
                        let text = e.unescape()?.to_string();
                        event.insert(current_element.clone(), text);
                    }
                }
                Ok(XmlEvent::End(ref e)) => {
                    depth -= 1;
                    if depth == 0 && current_schema.is_some() {
                        let schema = current_schema.unwrap();
                        if schema.mappings.contains_key("ecs") {
                            ecs_batch.push(transform_to_ecs(&event, schema));
                        }
                        if schema.mappings.contains_key("cim") {
                            cim_batch.push(transform_to_cim(&event, schema));
                        }
                        event_count += 1;
                        event.clear();
                        current_schema = None;
                        new_position += chunk.len() as u64 + delimiter.len() as u64;
                        if event_count >= batch_size {
                            break;
                        }
                    }
                    current_element.clear();
                }
                Ok(XmlEvent::Eof) => break,
                Err(e) => {
                    eprintln!("Error processing XML chunk in {}: {}", file_path, e);
                    break;
                }
                _ => {}
            }
            buf.clear();
        }
    }

    Ok((ecs_batch, cim_batch, file_path.to_string(), new_position))
}

async fn sender_process(
    mut rx: mpsc::Receiver<(Vec<EcsEvent>, Vec<CimEvent>, String, u64)>,
    config: Arc<Config>,
    file_positions: Arc<Mutex<HashMap<String, u64>>>,
) {
    let client = Client::new();
    let mut ecs_batch = Vec::new();
    let mut cim_batch = Vec::new();
    let mut last_flush = time::Instant::now();

    while let Some((ecs, cim, file_path, new_position)) = rx.recv().await {
        ecs_batch.extend(ecs);
        cim_batch.extend(cim);
        {
            let mut positions = file_positions.lock().unwrap();
            positions.insert(file_path, new_position);
        }

        if ecs_batch.len() >= config.batch_size || last_flush.elapsed().as_secs_f64() > config.buffer_timeout {
            if config.elasticsearch.enabled && !ecs_batch.is_empty() {
                let actions: Vec<HashMap<String, serde_json::Value>> = ecs_batch
                    .iter()
                    .map(|event| {
                        let mut action = HashMap::new();
                        action.insert("_index".to_string(), serde_json::Value::String(config.elasticsearch.index.clone()));
                        action.insert("_source".to_string(), serde_json::to_value(event).unwrap());
                        action
                    })
                    .collect();
                if let Err(e) = client
                    .post(&format!("{}/_bulk", config.elasticsearch.host))
                    .json(&actions)
                    .send()
                    .await
                {
                    eprintln!("Elasticsearch error: {}", e);
                }
                ecs_batch.clear();
            }

            if config.splunk.enabled && !cim_batch.is_empty() {
                let mut headers = reqwest::header::HeaderMap::new();
                headers.insert("Authorization", format!("Splunk {}", config.splunk.hec_token).parse().unwrap());
                headers.insert("Content-Type", "application/json".parse().unwrap());
                if let Err(e) = client
                    .post(&config.splunk.hec_url)
                    .headers(headers)
                    .json(&cim_batch)
                    .send()
                    .await
                {
                    eprintln!("Splunk error: {}", e);
                }
                cim_batch.clear();
            }

            last_flush = time::Instant::now();
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config_path = env::var("CONFIG_FILE").unwrap_or_else(|_| "deploy_config.yaml".to_string());
    let config = Arc::new(load_config(&config_path).await?);
    let schemas = Arc::new(load_schemas(&config.xml_connectors.schemas_file).await?);
    let file_positions = Arc::new(Mutex::new(HashMap::new()));
    let (tx, rx) = mpsc::channel(100);

    // Start sender process
    let config_clone = config.clone();
    let file_positions_clone = file_positions.clone();
    tokio::spawn(sender_process(rx, config_clone, file_positions_clone));

    // Start file system watcher
    let mut watcher = RecommendedWatcher::new(
        move |res: notify::Result<notify::Event>| {
            if let Ok(event) = res {
                for path in event.paths {
                    if path.extension().map_or(false, |ext| ext == "xml") {
                        let file_path = path.to_str().unwrap().to_string();
                        let position = file_positions.lock().unwrap().get(&file_path).cloned().unwrap_or(0);
                        let tx = tx.clone();
                        let schemas = schemas.clone();
                        let batch_size = config.batch_size;
                        let delimiter = config.delimiter.clone();
                        tokio::spawn(async move {
                            if let Ok((ecs_batch, cim_batch, file_path, new_position)) =
                                process_xml_chunk(&file_path, position, &schemas, batch_size, &delimiter).await
                            {
                                let _ = tx.send((ecs_batch, cim_batch, file_path, new_position)).await;
                            }
                        });
                    }
                }
            }
        },
        Config::default(),
    )?;
    watcher.watch(Path::new(&config.xml_connectors.log_dir), RecursiveMode::NonRecursive)?;

    println!(
        "Monitoring XML logs in {} with {} workers for {}",
        config.xml_connectors.log_dir,
        config.worker_count,
        if config.splunk.enabled && config.elasticsearch.enabled {
            "Splunk and Elasticsearch"
        } else if config.splunk.enabled {
            "Splunk"
        } else {
            "Elasticsearch"
        }
    );

    // Keep the program running
    tokio::signal::ctrl_c().await?;
    Ok(())
}