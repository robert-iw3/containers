from typing import Dict, List, Optional
import yaml
from watchfiles import awatch

class Mappings:
    def __init__(self, cim: Dict[str, str]):
        self.cim = cim

class Schema:
    def __init__(self, name: str, table_name: str, mappings: Mappings, timestamp_field: Optional[str] = None, id_field: Optional[str] = None):
        self.name = name
        self.table_name = table_name
        self.mappings = mappings
        self.timestamp_field = timestamp_field
        self.id_field = id_field

class Schemas:
    def __init__(self, schemas: List[Schema], file_path: str):
        self.schemas = schemas
        self.file_path = file_path

    @classmethod
    def load(cls, file_path: str) -> "Schemas":
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
            if not data or "schemas" not in data:
                raise ValueError("Invalid schemas.yaml format")
            schemas = [
                Schema(
                    name=s["name"],
                    table_name=s["table_name"],
                    mappings=Mappings(s["mappings"]["cim"]),
                    timestamp_field=s.get("timestamp_field"),
                    id_field=s.get("id_field"),
                )
                for s in data["schemas"]
            ]
            return cls(schemas, file_path)
        except Exception as e:
            raise ValueError(f"Failed to load schemas: {e}")

    def get_schema(self, table_name: str) -> Optional[Schema]:
        for schema in self.schemas:
            if schema.table_name == table_name:
                return schema
        return None

    async def watch(self):
        async for changes in awatch(self.file_path):
            try:
                self.schemas = self.load(self.file_path).schemas
                print(f"Reloaded schemas from {self.file_path}")
            except Exception as e:
                print(f"Failed to reload schemas: {e}")