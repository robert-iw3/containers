use anyhow::{Context, Result};
use log::{error, info, warn};
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher};
use parquet::file::reader::{FileReader, SerializedFileReader};
use parquet::arrow::ArrowReader;
use arrow::record_batch::RecordBatch;
use arrow::datatypes::SchemaRef;
use arrow::io::parquet::read::read_metadata;
use arrow::io::parquet::read::ParquetFile;
use prometheus::{Counter, Gauge, Histogram, Registry};
use rusqlite::{params, Connection};
use serde_json::Value;
use std::collections::HashSet;
use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use tokio::sync::mpsc;
use tokio::time;

use crate::schema::{Schema, Schemas};

lazy_static::lazy_static! {
    static ref EVENTS_PROCESSED: Counter = Counter::with_opts(prometheus::opts!(
        "parquet_connector_events_processed_total",
        "Total events processed per file",
        &["file", "schema"]
    ))
    .unwrap();
    static ref ERRORS_TOTAL: Counter = Counter::with_opts(prometheus::opts!(
        "parquet_connector_errors_total",
        "Total errors per file",
        &["file", "schema"]
    ))
    .unwrap();
    static ref PROCESSING_LATENCY: Histogram = Histogram::with_opts(
        prometheus::histogram_opts!(
            "parquet_connector_processing_latency_seconds",
            "Processing latency per file",
            &["file", "schema"]
        )
    )
    .unwrap();
    static ref ACTIVE_FILES: Gauge = Gauge::with_opts(prometheus::opts!(
        "parquet_connector_active_files",
        "Active Parquet files being processed",
        &["schema"]
    ))
    .unwrap();
}

#[derive(thiserror::Error, Debug)]
pub enum HandlerError {
    #[error("Invalid configuration: {0}")]
    Config(String),
    #[error("File error: {0}")]
    File(String),
    #[error("Database error: {0}")]
    Database(String),
    #[error("Schema error: {0}")]
    Schema(String),
}

#[derive(serde::Serialize, serde::Deserialize)]
struct Position {
    kind: String,
    value: String,
}

impl Position {
    fn new_timestamp(timestamp: SystemTime) -> Self {
        Self {
            kind: "Timestamp".to_string(),
            value: timestamp
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_secs()
                .to_string(),
        }
    }

    fn new_offset(offset: usize) -> Self {
        Self {
            kind: "Offset".to_string(),
            value: offset.to_string(),
        }
    }
}

pub struct ParquetHandler {
    data_dir: String,
    sender_queue: mpsc::Sender<(Vec<Value>, String, usize)>,
    schemas: Arc<Schemas>,
    batch_size: usize,
    poll_interval: f64,
    state_path: String,
    incremental_enabled: bool,
    max_files_concurrent: usize,
    max_memory_mb: usize,
    sqlcipher_key: String,
    active_files: HashSet<String>,
    registry: Arc<Registry>,
}

impl ParquetHandler {
    pub fn new(
        data_dir: String,
        sender_queue: mpsc::Sender<(Vec<Value>, String, usize)>,
        schemas: Arc<Schemas>,
        batch_size: usize,
        poll_interval: f64,
        state_path: String,
        incremental_enabled: bool,
        max_files_concurrent: usize,
        max_memory_mb: usize,
        sqlcipher_key: String,
        registry: Arc<Registry>,
    ) -> Result<Self> {
        if !(1..=1000).contains(&batch_size) {
            return Err(HandlerError::Config("batch_size must be between 1 and 1000".to_string()).into());
        }
        if !(1.0..=3600.0).contains(&poll_interval) {
            return Err(HandlerError::Config("poll_interval must be between 1 and 3600 seconds".to_string()).into());
        }
        if !(1..=50).contains(&max_files_concurrent) {
            return Err(HandlerError::Config("max_files_concurrent must be between 1 and 50".to_string()).into());
        }
        if !(100..=8192).contains(&max_memory_mb) {
            return Err(HandlerError::Config("max_memory_mb must be between 100 and 8192 MB".to_string()).into());
        }

        let path = Path::new(&data_dir);
        if !path.is_dir() {
            return Err(HandlerError::File(format!("Data directory {} does not exist", data_dir)).into());
        }
        if !std::fs::metadata(&data_dir)
            .map(|m| m.permissions().readonly())
            .unwrap_or(true)
        {
            return Err(HandlerError::File(format!("No read permission for {}", data_dir)).into());
        }

        Ok(Self {
            data_dir,
            sender_queue,
            schemas,
            batch_size,
            poll_interval,
            state_path,
            incremental_enabled,
            max_files_concurrent,
            max_memory_mb,
            sqlcipher_key,
            active_files: HashSet::new(),
            registry,
        })
    }

    pub async fn start(&self) -> Result<()> {
        self.registry.register(Box::new(EVENTS_PROCESSED.clone()))?;
        self.registry.register(Box::new(ERRORS_TOTAL.clone()))?;
        self.registry.register(Box::new(PROCESSING_LATENCY.clone()))?;
        self.registry.register(Box::new(ACTIVE_FILES.clone()))?;

        if self.incremental_enabled {
            self.start_incremental().await
        } else {
            self.start_full_scan().await
        }
    }

    async fn start_full_scan(&self) -> Result<()> {
        let mut interval = time::interval(Duration::from_secs_f64(self.poll_interval));
        loop {
            interval.tick().await;
            if let Err(e) = self.process_files().await {
                error!("Error discovering files: {}", e);
                ERRORS_TOTAL.with_label_values(&["discover", "global"]).inc();
            }
        }
    }

    async fn start_incremental(&self) -> Result<()> {
        let mut watcher = RecommendedWatcher::new(
            move |res| {
                if let Err(e) = res {
                    error!("File watch error: {}", e);
                }
            },
            Config::default(),
        )?;
        watcher.watch(Path::new(&self.data_dir), RecursiveMode::NonRecursive)?;
        loop {
            if let Err(e) = self.process_files().await {
                error!("Error discovering files: {}", e);
                ERRORS_TOTAL.with_label_values(&["discover", "global"]).inc();
            }
            tokio::time::sleep(Duration::from_secs_f64(self.poll_interval)).await;
        }
    }

    async fn process_files(&self) -> Result<()> {
        let files: Vec<_> = std::fs::read_dir(&self.data_dir)?
            .filter_map(|entry| {
                let path = entry.ok()?.path();
                if path.extension().map(|ext| ext == "parquet").unwrap_or(false) {
                    Some(path.to_str()?.to_string())
                } else {
                    None
                }
            })
            .collect();
        info!("Discovered {} Parquet files", files.len());

        for file in files {
            if self.active_files.len() >= self.max_files_concurrent {
                tokio::time::sleep(Duration::from_millis(100)).await;
                continue;
            }
            if let Err(e) = self.process_file(&file).await {
                let file_name = Path::new(&file).file_name().unwrap().to_str().unwrap();
                let schema_name = self.schemas.get_schema(file_name).map(|s| s.name).unwrap_or("unknown".to_string());
                ERRORS_TOTAL.with_label_values(&[file_name, &schema_name]).inc();
                error!("Error processing file {}: {}", file, e);
            }
        }
        Ok(())
    }

    async fn process_file(&self, file: &str) -> Result<()> {
        let file_name = Path::new(file).file_name().unwrap().to_str().unwrap().to_string();
        if self.active_files.contains(&file_name) {
            return Ok(());
        }
        self.active_files.insert(file_name.clone());
        let schema = self.schemas.get_schema(&file_name);
        let schema_name = schema.as_ref().map(|s| s.name.clone()).unwrap_or("unknown".to_string());
        ACTIVE_FILES.with_label_values(&[&schema_name]).inc();

        if schema.is_none() {
            warn!("No schema found for file {}", file_name);
            self.active_files.remove(&file_name);
            ACTIVE_FILES.with_label_values(&[&schema_name]).dec();
            return Ok(());
        }
        let schema = schema.unwrap();
        info!("Processing file: {}, schema: {}", file_name, schema_name);

        let conn = Connection::open(&self.state_path)?;
        conn.pragma_update(None, "key", &self.sqlcipher_key)?;
        conn.execute(
            "CREATE TABLE IF NOT EXISTS positions (file_name TEXT PRIMARY KEY, position TEXT)",
            [],
        )?;

        let mut batch = Vec::new();
        let pos = self.load_position(&conn, &file_name)?;
        let start_row = if pos.kind == "Offset" {
            pos.value.parse::<usize>().unwrap_or(0)
        } else {
            0
        };
        let mut new_pos = pos.clone();

        // Try as single Parquet file, then as dataset
        let mut is_dataset = false;
        let schema_arrow: SchemaRef;
        let mut record_batches: Box<dyn Iterator<Item = Result<RecordBatch>>>;

        if let Ok(file_reader) = SerializedFileReader::new(std::fs::File::open(file)?) {
            let arrow_reader = ArrowReader::new(file_reader);
            schema_arrow = arrow_reader.get_schema()?;
            record_batches = Box::new(arrow_reader);
        } else {
            let dataset = arrow::dataset::ParquetFile::try_new(file)?;
            schema_arrow = dataset.schema().clone();
            record_batches = Box::new(dataset.into_iter());
            is_dataset = true;
        }

        let missing_fields = self.validate_schema(&schema_arrow, &schema);
        if !missing_fields.is_empty() {
            return Err(HandlerError::Schema(format!("Missing fields: {:?}", missing_fields)).into());
        }

        for record_batch in record_batches {
            let record_batch = record_batch?;
            for row in 0..record_batch.num_rows() {
                if row < start_row {
                    continue;
                }
                let event = self.row_to_event(&record_batch, row)?;
                if self.incremental_enabled && schema.timestamp_field.is_some() {
                    let ts = event
                        .get(schema.timestamp_field.as_ref().unwrap())
                        .and_then(|v| v.as_i64())
                        .map(|v| SystemTime::UNIX_EPOCH + Duration::from_secs(v as u64));
                    if let (Some(ts), Position { kind, value, .. }) = (ts, &pos) {
                        if kind == "Timestamp" && ts <= (SystemTime::UNIX_EPOCH + Duration::from_secs(value.parse::<u64>().unwrap_or(0))) {
                            continue;
                        }
                    }
                }
                let transformed = self.transform_to_ecs(&event, &schema);
                batch.push(transformed);
                EVENTS_PROCESSED.with_label_values(&[&file_name, &schema_name]).inc();

                if schema.timestamp_field.is_some() {
                    if let Some(ts) = event.get(schema.timestamp_field.as_ref().unwrap()).and_then(|v| v.as_i64()) {
                        new_pos = Position::new_timestamp(SystemTime::UNIX_EPOCH + Duration::from_secs(ts as u64));
                    }
                } else {
                    new_pos = Position::new_offset(row + 1);
                }

                if batch.len() >= self.batch_size {
                    self.sender_queue
                        .send((batch.clone(), file_name.clone(), batch.len()))
                        .await
                        .context("Failed to send batch")?;
                    batch.clear();
                }
            }
        }

        if !batch.is_empty() {
            self.sender_queue
                .send((batch.clone(), file_name.clone(), batch.len()))
                .await
                .context("Failed to send batch")?;
        }

        if new_pos != pos {
            self.save_position(&conn, &file_name, &new_pos)?;
        }

        self.active_files.remove(&file_name);
        ACTIVE_FILES.with_label_values(&[&schema_name]).dec();
        Ok(())
    }

    fn load_position(&self, conn: &Connection, file_name: &str) -> Result<Position> {
        let mut stmt = conn.prepare("SELECT position FROM positions WHERE file_name = ?")?;
        let pos: Option<String> = stmt
            .query_row(params![file_name], |row| row.get(0))
            .optional()?;
        Ok(pos
            .map(|p| serde_json::from_str(&p).context("Failed to parse position"))
            .transpose()?
            .unwrap_or(Position {
                kind: "Offset".to_string(),
                value: "0".to_string(),
            }))
    }

    fn save_position(&self, conn: &Connection, file_name: &str, position: &Position) -> Result<()> {
        let pos_json = serde_json::to_string(position)?;
        conn.execute(
            "INSERT OR REPLACE INTO positions (file_name, position) VALUES (?, ?)",
            params![file_name, pos_json],
        )?;
        Ok(())
    }

    fn validate_schema(&self, arrow_schema: &SchemaRef, schema: &Schema) -> Vec<String> {
        let expected_fields: HashSet<_> = schema
            .mappings
            .ecs
            .iter()
            .filter(|(k, _)| k != &"sourcetype")
            .filter(|(_, v)| !v.starts_with('"') || !v.ends_with('"'))
            .map(|(_, v)| v.clone())
            .collect();
        let actual_fields: HashSet<_> = arrow_schema.fields().iter().map(|f| f.name().clone()).collect();
        expected_fields.difference(&actual_fields).cloned().collect()
    }

    fn row_to_event(&self, batch: &RecordBatch, row: usize) -> Result<Value> {
        let mut event = serde_json::Map::new();
        for (i, column) in batch.columns().iter().enumerate() {
            let name = batch.schema().field(i).name();
            let value = column.get(row)?;
            event.insert(name.to_string(), value.into());
        }
        Ok(Value::Object(event))
    }

    fn transform_to_ecs(&self, event: &Value, schema: &Schema) -> Value {
        let mut ecs = serde_json::Map::new();
        ecs.insert(
            "@timestamp".to_string(),
            event
                .get(schema.mappings.ecs.get("@timestamp").unwrap_or(&"timestamp".to_string()))
                .cloned()
                .unwrap_or(Value::String(chrono::Utc::now().to_rfc3339())),
        );
        ecs.insert("ecs".to_string(), Value::Object(serde_json::Map::from_iter(vec![(
            "version".to_string(),
            Value::String("8.0.0".to_string()),
        )])));

        for (key, value) in &schema.mappings.ecs {
            if !key.starts_with('@') {
                if value.starts_with('"') && value.ends_with('"') {
                    ecs.insert(key.clone(), Value::String(value.trim_matches('"').to_string()));
                } else {
                    ecs.insert(key.clone(), event.get(value).cloned().unwrap_or(Value::String("".to_string())));
                }
            }
        }

        Value::Object(ecs)
    }
}