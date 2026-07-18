"""
Record-store API: the service the API Firewall protects in this stack.

A generic, multi-use-case data API: records are (owner_id, kind, data)
where `data` is a free-form JSON object — usable as-is for tasks, events,
profiles, telemetry, etc. Owners are sharded across SQL Server instances
(see db.py). Every query is parameterized; the JSON payload is stored as
an opaque value, never interpolated into SQL.

Defense in depth: this app *also* validates inputs and requires an API
key, but the firewall in front enforces the same contract (plus WAF,
denylist) before requests get here. FastAPI 0.98/pydantic v1 on purpose —
the firewall needs the OpenAPI 3.0.2 this generation emits.
"""
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

import db

app = FastAPI(
    title="Sharded record-store API",
    version="1.0.0",
    description="Generic record store sharded over SQL Server, fronted by Wallarm API Firewall.",
)

API_KEYS = {k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()}
api_key_header = APIKeyHeader(name="X-API-Key")


def require_key(key: str = Security(api_key_header)) -> str:
    if key not in API_KEYS:
        raise HTTPException(status_code=401, detail="invalid API key")
    return key


ERROR_RESPONSES = {
    401: {
        "description": "Invalid API key",
        "content": {"application/json": {"schema": {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
            "required": ["detail"],
        }}},
    },
    404: {
        "description": "Record not found",
        "content": {"application/json": {"schema": {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
            "required": ["detail"],
        }}},
    },
}


class RecordIn(BaseModel):
    kind: str = Field(..., min_length=1, max_length=32, regex=r"^[a-z0-9_-]+$")
    data: Dict[str, Any] = Field(..., description="Free-form JSON payload")

    class Config:
        extra = "forbid"


class RecordOut(BaseModel):
    id: int
    owner_id: int
    kind: str
    data: Dict[str, Any]
    shard: int
    created_at: str
    updated_at: str


class ShardStatus(BaseModel):
    shard: int
    server: str
    healthy: bool
    records: Optional[int] = None
    error: Optional[str] = None


@app.on_event("startup")
def startup() -> None:
    db.bootstrap()


def _row_to_record(row, owner_id: int) -> dict:
    return {
        "id": row[0],
        "owner_id": row[1],
        "kind": row[2],
        "data": json.loads(row[3]),
        "shard": db.shard_for(owner_id),
        "created_at": row[4].isoformat(),
        "updated_at": row[5].isoformat(),
    }


SELECT_COLS = "id, owner_id, kind, data, created_at, updated_at"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/owners/{owner_id}/records", response_model=RecordOut, status_code=201,
          responses=ERROR_RESPONSES, dependencies=[Depends(require_key)])
def create_record(record: RecordIn, owner_id: int = Path(..., ge=1)):
    cur = db.get_conn(db.shard_for(owner_id)).cursor()
    cur.execute(
        f"INSERT INTO dbo.records (owner_id, kind, data) "
        f"OUTPUT INSERTED.{SELECT_COLS.replace(', ', ', INSERTED.')} "
        f"VALUES (%s, %s, %s)",
        (owner_id, record.kind, json.dumps(record.data)),
    )
    return _row_to_record(cur.fetchone(), owner_id)


@app.get("/v1/owners/{owner_id}/records", response_model=List[RecordOut],
         responses=ERROR_RESPONSES, dependencies=[Depends(require_key)])
def list_records(
    owner_id: int = Path(..., ge=1),
    kind: Optional[str] = Query(None, min_length=1, max_length=32, regex=r"^[a-z0-9_-]+$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    cur = db.get_conn(db.shard_for(owner_id)).cursor()
    if kind is None:
        cur.execute(
            f"SELECT {SELECT_COLS} FROM dbo.records WHERE owner_id = %s "
            f"ORDER BY id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (owner_id, offset, limit),
        )
    else:
        cur.execute(
            f"SELECT {SELECT_COLS} FROM dbo.records WHERE owner_id = %s AND kind = %s "
            f"ORDER BY id OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            (owner_id, kind, offset, limit),
        )
    return [_row_to_record(r, owner_id) for r in cur.fetchall()]


@app.get("/v1/owners/{owner_id}/records/{record_id}", response_model=RecordOut,
         responses=ERROR_RESPONSES, dependencies=[Depends(require_key)])
def get_record(owner_id: int = Path(..., ge=1), record_id: int = Path(..., ge=1)):
    cur = db.get_conn(db.shard_for(owner_id)).cursor()
    cur.execute(
        f"SELECT {SELECT_COLS} FROM dbo.records WHERE owner_id = %s AND id = %s",
        (owner_id, record_id),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return _row_to_record(row, owner_id)


@app.put("/v1/owners/{owner_id}/records/{record_id}", response_model=RecordOut,
         responses=ERROR_RESPONSES, dependencies=[Depends(require_key)])
def update_record(record: RecordIn, owner_id: int = Path(..., ge=1),
                  record_id: int = Path(..., ge=1)):
    cur = db.get_conn(db.shard_for(owner_id)).cursor()
    cur.execute(
        f"UPDATE dbo.records SET kind = %s, data = %s, updated_at = SYSUTCDATETIME() "
        f"OUTPUT INSERTED.{SELECT_COLS.replace(', ', ', INSERTED.')} "
        f"WHERE owner_id = %s AND id = %s",
        (record.kind, json.dumps(record.data), owner_id, record_id),
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return _row_to_record(row, owner_id)


@app.delete("/v1/owners/{owner_id}/records/{record_id}", status_code=204,
            responses=ERROR_RESPONSES, dependencies=[Depends(require_key)])
def delete_record(owner_id: int = Path(..., ge=1), record_id: int = Path(..., ge=1)):
    cur = db.get_conn(db.shard_for(owner_id)).cursor()
    cur.execute(
        "DELETE FROM dbo.records WHERE owner_id = %s AND id = %s",
        (owner_id, record_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Record not found")


@app.get("/v1/shards", response_model=List[ShardStatus],
         responses=ERROR_RESPONSES, dependencies=[Depends(require_key)])
def shards():
    return db.shard_health()
