"""UAT mock backend for the Wallarm API Firewall.

Deliberately permissive: it accepts anything the firewall lets through and
records every request it receives, so the UAT battery can assert that
blocked requests never reached the backend. In the UAT stack every
firewall block returns HTTP 418 (APIFW_CUSTOM_BLOCK_STATUS_CODE), so a 418
always proves the firewall acted — never this app.

Pinned to FastAPI 0.98 / pydantic v1 on purpose: that generation emits
OpenAPI 3.0.2, which the firewall's kin-openapi parser fully supports
(OpenAPI 3.1 from newer FastAPI is not reliably parsed).
"""
from typing import List

from fastapi import FastAPI, HTTPException, Path, Query, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

app = FastAPI(
    title="API Firewall UAT backend",
    version="1.0.0",
    description="Mock service used to user-acceptance-test the API Firewall.",
)

# Every request that reaches this app, in order. Exposed only on the
# hidden /_uat/* endpoints (excluded from the OpenAPI spec, therefore
# unreachable through the firewall).
HITS: List[str] = []


@app.middleware("http")
async def record_hits(request: Request, call_next):
    # /health is pinged by the container healthcheck and /_uat/* by the
    # battery itself; recording them would make hit-count assertions racy.
    path = request.url.path
    if path != "/health" and not path.startswith("/_uat/"):
        HITS.append(f"{request.method} {path}")
    return await call_next(request)


NOT_FOUND = {
    404: {
        "description": "Item not found",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                }
            }
        },
    }
}


class Item(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    # ge (inclusive) on purpose: gt= would emit draft-07 numeric
    # exclusiveMinimum, which kin-openapi rejects in an OpenAPI 3.0 doc.
    price: float = Field(..., ge=0.01)
    tags: List[str] = Field(default_factory=list, max_items=5)

    class Config:
        # -> additionalProperties: false in the spec; the firewall rejects
        # unknown body fields before they get here.
        extra = "forbid"


class StoredItem(Item):
    id: int


ITEMS = {
    1: StoredItem(id=1, name="anvil", price=9.99),
    2: StoredItem(id=2, name="rocket", price=129.5, tags=["acme"]),
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items", response_model=List[StoredItem])
def list_items(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return list(ITEMS.values())[offset : offset + limit]


@app.get("/items/{item_id}", response_model=StoredItem, responses=NOT_FOUND)
def get_item(item_id: int = Path(..., ge=1)):
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    return ITEMS[item_id]


@app.post("/items", response_model=StoredItem, status_code=201)
def create_item(item: Item):
    new_id = max(ITEMS, default=0) + 1
    stored = StoredItem(id=new_id, **item.dict())
    ITEMS[new_id] = stored
    return stored


@app.put("/items/{item_id}", response_model=StoredItem, responses=NOT_FOUND)
def update_item(item: Item, item_id: int = Path(..., ge=1)):
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = StoredItem(id=item_id, **item.dict())
    ITEMS[item_id] = stored
    return stored


@app.delete("/items/{item_id}", status_code=204, responses=NOT_FOUND)
def delete_item(item_id: int = Path(..., ge=1)):
    if item_id not in ITEMS:
        raise HTTPException(status_code=404, detail="Item not found")
    del ITEMS[item_id]


# The spec marks this endpoint as requiring the X-API-Key header; the
# firewall enforces the requirement (and the token denylist) before the
# request arrives. The app itself accepts any key on purpose.
api_key = APIKeyHeader(name="X-API-Key")


@app.get("/admin/secrets")
def admin_secrets(key: str = Security(api_key)):
    return {"secret": "uat-master-secret", "presented_key": key}


# Response-validation canary: the spec (below) promises {"ok": boolean} but
# the app deliberately returns a string. With APIFW_RESPONSE_VALIDATION=
# BLOCK the firewall must intercept this response and return 418.
@app.get(
    "/rogue",
    responses={
        200: {
            "description": "Rogue response",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                        "required": ["ok"],
                        "additionalProperties": False,
                    }
                }
            },
        }
    },
)
def rogue():
    return {"ok": "definitely-not-a-boolean"}


# ---- UAT introspection (hidden: not in the spec, so the firewall will ----
# ---- never let external callers reach these)                          ----
@app.get("/_uat/hits", include_in_schema=False)
def uat_hits():
    return {"count": len(HITS), "hits": HITS}


@app.post("/_uat/reset", include_in_schema=False)
def uat_reset():
    HITS.clear()
    return {"count": 0}
