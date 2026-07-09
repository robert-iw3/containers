use anyhow::{Context, Result};
use log::{error, info};
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Serialize, Deserialize, Clone)]
pub struct Mappings {
    pub ecs: HashMap<String, String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Schema {
    pub name: String,
    pub file_name: String,
    pub mappings: Mappings,
    pub timestamp_field: Option<String>,
}

#[derive(Serialize, Deserialize)]
struct SchemasConfig {
    schemas: Vec<Schema>,
}

pub struct Schemas {
    schemas: Arc<RwLock<Vec<Schema>>>,
    file_path: String,
}

impl Schemas {
    pub async fn load(file_path: &str) -> Result<Self> {
        let content = std::fs::read_to_string(file_path)?;
        let config: SchemasConfig = serde_yaml::from_str(&content)
            .context(format!("Failed to parse schemas from {}", file_path))?;
        info!("Loaded {} schemas from {}", config.schemas.len(), file_path);
        Ok(Self {
            schemas: Arc::new(RwLock::new(config.schemas)),
            file_path: file_path.to_string(),
        })
    }

    pub fn get_schema(&self, file_name: &str) -> Option<Schema> {
        let schemas = self.schemas.blocking_read();
        schemas.iter().find(|s| s.file_name == file_name).cloned()
    }

    pub async fn watch(&self) -> Result<()> {
        let mut watcher = RecommendedWatcher::new(
            move |res| {
                if let Err(e) = res {
                    error!("Schema watch error: {}", e);
                }
            },
            Config::default(),
        )?;
        watcher.watch(Path::new(&self.file_path), RecursiveMode::NonRecursive)?;
        loop {
            tokio::time::sleep(Duration::from_secs(1)).await;
            let content = std::fs::read_to_string(&self.file_path)?;
            let config: SchemasConfig = serde_yaml::from_str(&content)
                .context(format!("Failed to parse schemas from {}", self.file_path))?;
            {
                let mut schemas = self.schemas.write().await;
                *schemas = config.schemas;
            }
            info!("Reloaded schemas from {}", self.file_path);
        }
    }
}