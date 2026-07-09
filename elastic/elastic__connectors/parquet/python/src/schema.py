from typing import Dict, List, Optional
import yaml
from watchfiles import awatch
import structlog

logger = structlog.get_logger()

class Mappings:
    def __init__(self, ecs: Dict[str, str]):
        self.ecs = ecs

class Schema:
    def __init__(self, name: str, file_name: str, mappings: Mappings, timestamp_field: Optional[str] = None):
        self.name = name
        self.file_name = file_name
        self.mappings = mappings
        self.timestamp_field = timestamp_field

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
                raise ValueError(f"Invalid schemas.yaml format at {file_path}")
            schemas = [
                Schema(
                    name=s["name"],
                    file_name=s["file_name"],
                    mappings=Mappings(s["mappings"]["ecs"]),
                    timestamp_field=s.get("timestamp_field"),
                )
                for s in data["schemas"]
            ]
            logger.info(f"Loaded {len(schemas)} schemas from {file_path}")
            return cls(schemas, file_path)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error for {file_path}: {e}", exc_info=True)
            raise ValueError(f"Failed to load schemas from {file_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load schemas from {file_path}: {e}", exc_info=True)
            raise ValueError(f"Failed to load schemas from {file_path}: {e}")

    def get_schema(self, file_name: str) -> Optional[Schema]:
        for schema in self.schemas:
            if schema.file_name == file_name:
                return schema
        logger.debug(f"No schema found for file {file_name}")
        return None

    async def watch(self):
        async for changes in awatch(self.file_path):
            try:
                self.schemas = self.load(self.file_path).schemas
                logger.info(f"Reloaded schemas from {self.file_path}")
            except Exception as e:
                logger.error(f"Failed to reload schemas from {self.file_path}: {e}", exc_info=True)