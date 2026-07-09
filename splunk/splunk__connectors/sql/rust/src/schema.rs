use std::collections::HashMap;
use std::fs::File;

use serde::{Deserialize, Serialize};
use serde_yaml;

#[derive(Serialize, Deserialize, Clone)]
pub struct Mappings {
    pub cim: HashMap<String, String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Schema {
    pub name: String,
    pub table_name: String,
    pub mappings: Mappings,
    pub timestamp_field: Option<String>,
    pub id_field: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Schemas {
    pub schemas: Vec<Schema>,
}

impl Schemas {
    pub fn load(file_path: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let file = File::open(file_path)?;
        let schemas = serde_yaml::from_reader(file)?;
        Ok(schemas)
    }

    pub fn get_schema(&self, table_name: &str) -> Option<&Schema> {
        self.schemas.iter().find(|s| s.table_name == table_name)
    }
}