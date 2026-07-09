use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::{DateTime, Utc};
use postgres_protocol::message::backend::ReplicationMessage;
use postgres_types::{FromSql, Type};
use prometheus::{IntCounterVec, IntGauge, HistogramVec};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sled::Db;
use sqlx::{any::AnyRow, AnyPool, AnyPoolOptions, Connection, Executor, Pool, Row};
use thiserror::Error;
use tokio::sync::mpsc;
use tokio_retry::{strategy::ExponentialBackoff, Retry};
use tracing::{debug, error, info, warn};
use uuid::Uuid;
use warp::Filter;

use crate::schema::{Schema, Schemas};

lazy_static::lazy_static! {
    static ref EVENTS_PROCESSED: IntCounterVec = prometheus::register_int_counter_vec!(
        "sql_connector_events_processed_total",
        "Total number of events processed per table",
        &["table"]
    ).unwrap();
    static ref ERRORS_TOTAL: IntCounterVec = prometheus::register_int_counter_vec!(
        "sql_connector_errors_total",
        "Total number of errors per table",
        &["table"]
    ).unwrap();
    static ref QUERY_LATENCY: HistogramVec = prometheus::register_histogram_vec!(
        "sql_connector_query_latency_seconds",
        "Query latency per table",
        &["table"]
    ).unwrap();
    static ref ACTIVE_CONNECTIONS: IntGauge = prometheus::register_int_gauge!(
        "sql_connector_active_connections",
        "Number of active database connections"
    ).unwrap();
}

#[derive(Clone)]
pub enum DbType {
    Postgres,
    MySql,
    MsSql,
    SQLite,
    Oracle,
}

#[derive(Error, Debug)]
pub enum HandlerError {
    #[error("Database error: {0}")]
    Db(#[from] sqlx::Error),
    #[error("Serialization error: {0}")]
    Serde(#[from] serde_json::Error),
    #[error("State storage error: {0}")]
    Sled(#[from] sled::Error),
    #[error("Send error: {0}")]
    Send(#[from] mpsc::error::SendError<(Vec<Value>, String, u64)>),
    #[error("CDC error: {0}")]
    Cdc(String),
    #[error("Other error: {0}")]
    Other(#[from] Box<dyn std::error::Error + Send + Sync>),
}

#[derive(Serialize, Deserialize, Clone, Copy)]
pub enum Position {
    Timestamp(DateTime<Utc>),
    Id(Uuid),
    Lsn(u64), // For PostgreSQL CDC
}

pub struct SqlHandler {
    db_type: DbType,
    conn_str: String,
    tx: mpsc::Sender<(Vec<Value>, String, u64)>,
    schemas: Arc<Schemas>,
    batch_size: usize,
    last_positions: HashMap<String, Position>,
    poll_interval: Duration,
    state_db: Db,
    cdc_enabled: bool,
    max_connections_per_table: u32,
    pools: HashMap<String, Pool<sqlx::Any>>,
}

impl SqlHandler {
    pub fn new(
        db_type: DbType,
        conn_str: String,
        tx: mpsc::Sender<(Vec<Value>, String, u64)>,
        schemas: Arc<Schemas>,
        batch_size: usize,
        poll_interval: Duration,
        state_path: &str,
        cdc_enabled: bool,
        max_connections_per_table: u32,
    ) -> Result<Self, HandlerError> {
        let state_db = sled::open(state_path)?;
        let mut last_positions = HashMap::new();
        for res in state_db.iter() {
            let (key, value) = res?;
            let table = String::from_utf8(key.to_vec()).unwrap_or_default();
            let pos: Position = bincode::deserialize(&value)?;
            last_positions.insert(table, pos);
        }
        Ok(SqlHandler {
            db_type,
            conn_str,
            tx,
            schemas,
            batch_size,
            last_positions,
            poll_interval,
            state_db,
            cdc_enabled,
            max_connections_per_table,
            pools: HashMap::new(),
        })
    }

    pub async fn start(&mut self) -> Result<(), HandlerError> {
        // Start metrics server
        tokio::spawn(async move {
            let metrics = warp::path("metrics")
                .and(warp::get())
                .map(|| {
                    let metric_families = prometheus::gather();
                    warp::reply::with_header(
                        prometheus::TextEncoder::new().encode_to_string(&metric_families).unwrap(),
                        "content-type",
                        "text/plain; version=0.0.4",
                    )
                });
            warp::serve(metrics).run(([0, 0, 0, 0], 9000)).await;
        });

        if self.cdc_enabled && matches!(self.db_type, DbType::Postgres) {
            self.start_cdc().await?;
        } else {
            self.start_polling().await?;
        }
        Ok(())
    }

    async fn start_polling(&mut self) -> Result<(), HandlerError> {
        loop {
            match self.discover_tables().await {
                Ok(tables) => {
                    for table in tables {
                        if let Err(e) = self.process_table(&table).await {
                            ERRORS_TOTAL.with_label_values(&[&table]).inc();
                            error!("Error processing table {}: {}", table, e);
                        }
                    }
                }
                Err(e) => {
                    ERRORS_TOTAL.with_label_values(&["discover"]).inc();
                    error!("Error discovering tables: {}", e);
                }
            }
            tokio::time::sleep(self.poll_interval).await;
        }
    }

    async fn start_cdc(&mut self) -> Result<(), HandlerError> {
        if !matches!(self.db_type, DbType::Postgres) {
            return Err(HandlerError::Cdc("CDC only supported for PostgreSQL".into()));
        }

        let pool = self.get_pool(None).await?;
        let mut conn = pool.acquire().await?;
        sqlx::query("CREATE PUBLICATION sql_connector_pub FOR ALL TABLES").execute(&mut *conn).await?;
        let slot_name = "sql_connector_slot";
        sqlx::query(&format!("CREATE_REPLICATION_SLOT {} LOGICAL pgoutput", slot_name)).execute(&mut *conn).await?;

        let mut stream = sqlx::postgres::PgCopyIn::new(&mut *conn, &format!("START_REPLICATION SLOT {} LOGICAL 0/0", slot_name)).await?;
        while let Some(replication_message) = stream.next().await {
            match replication_message {
                ReplicationMessage::XLogData(xlog_data) => {
                    if let Some(change) = xlog_data.data().as_change() {
                        self.process_cdc_change(change).await?;
                    }
                }
                _ => continue,
            }
        }
        Ok(())
    }

    async fn process_cdc_change(&mut self, change: postgres_protocol::message::backend::LogicalReplicationChange) -> Result<(), HandlerError> {
        match change {
            postgres_protocol::message::backend::LogicalReplicationChange::Insert { relation, tuple } => {
                let table = relation.name().to_string();
                if let Some(schema) = self.schemas.get_schema(&table) {
                    let event: HashMap<String, String> = relation
                        .columns()
                        .iter()
                        .zip(tuple.values())
                        .filter_map(|(col, val)| {
                            val.as_ref().map(|v| (col.name().to_string(), v.to_string()))
                        })
                        .collect();
                    let transformed = self.transform_to_cim(&event, schema);
                    self.tx.send((vec![transformed], table.clone(), 1)).await?;
                    EVENTS_PROCESSED.with_label_values(&[&table]).inc();

                    if let Some(lsn) = change.lsn() {
                        self.last_positions.insert(table.clone(), Position::Lsn(lsn));
                        self.state_db.insert(table.as_bytes(), &bincode::serialize(&Position::Lsn(lsn))?)?;
                        self.state_db.flush()?;
                    }
                }
            }
            _ => {} // Handle updates/deletes if needed
        }
        Ok(())
    }

    async fn discover_tables(&self) -> Result<Vec<String>, HandlerError> {
        info!("Discovering tables");
        let pool = self.get_pool(None).await?;
        let query = match self.db_type {
            DbType::Postgres => "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_type = 'BASE TABLE' OR table_type = 'VIEW')",
            DbType::MySql => "SHOW TABLES",
            DbType::MsSql => "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' OR TABLE_TYPE = 'VIEW'",
            DbType::SQLite => "SELECT name FROM sqlite_master WHERE type='table' OR type='view'",
            DbType::Oracle => "SELECT TABLE_NAME FROM USER_TABLES UNION SELECT VIEW_NAME AS TABLE_NAME FROM USER_VIEWS",
        };
        let start = Instant::now();
        let rows = sqlx::query(query).fetch_all(&pool).await?;
        let latency = start.elapsed().as_secs_f64();
        QUERY_LATENCY.with_label_values(&["discover"]).observe(latency);
        let tables: Vec<String> = rows.iter().map(|row: &AnyRow| row.get(0)).collect();
        debug!("Discovered tables: {:?}", tables);
        Ok(tables)
    }

    async fn get_pool(&mut self, table: Option<&str>) -> Result<Pool<sqlx::Any>, HandlerError> {
        if let Some(table) = table {
            if let Some(pool) = self.pools.get(table) {
                ACTIVE_CONNECTIONS.set(pool.status().size as i64);
                return Ok(pool.clone());
            }
        }
        let retry_strategy = ExponentialBackoff::from_millis(100).max_delay(Duration::from_secs(10)).take(5);
        let pool = Retry::retry_async(retry_strategy, || async {
            info!("Creating connection pool for {}", table.unwrap_or("global"));
            AnyPoolOptions::new()
                .max_connections(self.max_connections_per_table)
                .connect(&self.conn_str)
                .await
                .map_err(HandlerError::from)
        })
        .await?;
        ACTIVE_CONNECTIONS.set(pool.status().size as i64);
        if let Some(table) = table {
            self.pools.insert(table.to_string(), pool.clone());
        }
        Ok(pool)
    }

    async fn process_table(&mut self, table: &str) -> Result<(), HandlerError> {
        if let Some(schema) = self.schemas.get_schema(table) {
            info!("Processing table: {}", table);
            let pool = self.get_pool(Some(table)).await?;
            let pos = self.last_positions.get(table).cloned();

            let mut query = format!("SELECT * FROM \"{}\" WHERE 1=1", table);
            let (order_field, filter) = match (&schema.timestamp_field, &schema.id_field, pos) {
                (Some(ts), _, Some(Position::Timestamp(last_ts))) => (ts.clone(), format!(" AND \"{}\" > '{}'", ts, last_ts)),
                (_, Some(id), Some(Position::Id(last_id))) => (id.clone(), format!(" AND \"{}\" > '{}'", id, last_id)),
                (Some(ts), _, _) => (ts.clone(), String::new()),
                (_, Some(id), _) => (id.clone(), String::new()),
                _ => {
                    warn!("No incremental field for table {}, full scan", table);
                    ("1".to_string(), String::new())
                },
            };
            query.push_str(&filter);
            query.push_str(&format!(" ORDER BY \"{}\" ASC LIMIT {}", order_field, self.batch_size));

            debug!("Executing query: {}", query);
            let start = Instant::now();
            let mut rows = sqlx::query(&query).fetch(&pool);
            let mut batch = Vec::new();
            let mut new_pos = pos;
            let mut event_count = 0;

            while let Some(row) = rows.try_next().await? {
                let event: HashMap<String, String> = (0..row.len())
                    .filter_map(|i| {
                        let name = row.column(i).name().to_string();
                        let value: Option<String> = row.try_get(i).ok();
                        value.map(|v| (name, v))
                    })
                    .collect();
                let transformed = self.transform_to_cim(&event, schema);
                batch.push(transformed);

                if let Some(ts_field) = &schema.timestamp_field {
                    if let Ok(ts) = row.try_get(ts_field) {
                        new_pos = Some(Position::Timestamp(ts));
                    }
                } else if let Some(id_field) = &schema.id_field {
                    if let Ok(id) = row.try_get(id_field) {
                        new_pos = Some(Position::Id(id));
                    }
                }

                event_count += 1;
                EVENTS_PROCESSED.with_label_values(&[table]).inc();
                if event_count >= self.batch_size {
                    break;
                }
            }

            QUERY_LATENCY.with_label_values(&[table]).observe(start.elapsed().as_secs_f64());

            if let Some(pos) = new_pos {
                self.last_positions.insert(table.to_string(), pos);
                self.state_db.insert(table.as_bytes(), &bincode::serialize(&pos)?)?;
                self.state_db.flush()?;
            }

            if !batch.is_empty() {
                info!("Sending batch of {} events for table {}", batch.len(), table);
                self.tx.send((batch, table.to_string(), event_count as u64)).await?;
            }
        } else {
            warn!("No schema found for table {}", table);
        }
        Ok(())
    }

    fn transform_to_cim(&self, event: &HashMap<String, String>, schema: &Schema) -> Value {
        let mut cim = json!({
            "time": event.get(schema.mappings.cim.get("time").unwrap_or(&"timestamp".to_string())).unwrap_or(&chrono::Utc::now().timestamp().to_string()),
            "vendor_product": "SQL_Connector",
            "schema": &schema.name
        });

        for (key, value) in &schema.mappings.cim {
            if key != "sourcetype" {
                let target_value = if value.starts_with('"') && value.ends_with('"') {
                    json!(value.trim_matches('"'))
                } else {
                    json!(event.get(value).unwrap_or_default())
                };
                cim[key] = target_value;
            }
        }

        json!({
            "event": cim,
            "sourcetype": schema.mappings.cim.get("sourcetype").map_or(format!("sql:{}", schema.name), |v| v.to_string())
        })
    }
}