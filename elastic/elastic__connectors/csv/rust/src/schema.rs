use std::collections::HashMap;
use std::fs::File;

use serde::{Deserialize, Serialize};
use serde_yaml;

#[derive(Serialize, Deserialize)]
pub struct Mappings {
    pub ecs: HashMap<String, String>,
    pub cim: HashMap<String, String>,
}

#[derive(Serialize, Deserialize)]
pub struct Schema {
    pub name: String,
    pub schema_key: String,
    pub schema_value: String,
    pub mappings: Mappings,
}

#[derive(Serialize, Deserialize)]
pub struct Schemas {
    pub schemas: Vec<Schema>,
}

impl Schemas {
    pub fn load(file_path: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let file = File::open(file_path)?;
        let schemas = serde_yaml::from_reader(file)?;
        Ok(schemas)
    }

    pub fn get_schema(&self, event: &HashMap<String, String>) -> Option<&Schema> {
        for schema in &self.schemas {
            if event.get(&schema.schema_key).map_or(false, |v| v == &schema.schema_value) {
                return Some(schema);
            }
        }
        None
    }
}