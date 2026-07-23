"""
OpenAI-compatible API in front of the Neo4j GraphRAG chains.

OpenWebUI (or any OpenAI client) registers this service as an external model
provider. Two models are exposed:

  neo4j-graphrag  retrieval-augmented answers grounded in the Neo4j graph
  neo4j-llm       the same LLM with no retrieval (baseline / comparison)

Auth is a static bearer token (GRAPHRAG_API_KEY); the graph, embeddings and
LLM are shared process-wide and initialised once at startup.
"""
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_neo4j import Neo4jGraph
from pydantic import BaseModel

from chains import (
    configure_llm_only_chain,
    configure_qa_rag_chain,
    load_embedding_model,
    load_llm,
)
from utils import BaseLogger, create_vector_index

logger = BaseLogger()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://neo4j:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence_transformer")
LLM_NAME = os.getenv("LLM", "llama3.2:3b")
API_KEY = os.getenv("GRAPHRAG_API_KEY", "")

RAG_MODEL = "neo4j-graphrag"
LLM_MODEL = "neo4j-llm"

# Populated by the background bootstrap so the app can report health while
# Neo4j and Ollama finish coming up rather than crash-looping on import.
_state: Dict[str, Any] = {"ready": False, "error": None}

app = FastAPI(title="Neo4j GraphRAG API", version="2.0.0")
_bearer = HTTPBearer(auto_error=False)


def _init() -> None:
    embeddings, dimension = load_embedding_model(
        EMBEDDING_MODEL, config={"ollama_base_url": OLLAMA_BASE_URL}, logger=logger
    )
    graph = Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        refresh_schema=False,
    )
    create_vector_index(graph, dimension)
    llm = load_llm(LLM_NAME, logger=logger, config={"ollama_base_url": OLLAMA_BASE_URL})
    _state.update(
        graph=graph,
        chains={
            LLM_MODEL: configure_llm_only_chain(llm),
            RAG_MODEL: configure_qa_rag_chain(
                llm,
                embeddings,
                embeddings_store_url=NEO4J_URI,
                username=NEO4J_USERNAME,
                password=NEO4J_PASSWORD,
            ),
        },
        ready=True,
        error=None,
    )
    logger.info("GraphRAG initialised; models ready")


@app.on_event("startup")
def startup() -> None:
    def bootstrap() -> None:
        # Neo4j and Ollama may still be settling; retry a few times before
        # leaving the service in a not-ready (503) state.
        for attempt in range(1, 13):
            try:
                _init()
                return
            except Exception as exc:
                _state["error"] = str(exc)
                logger.error(f"Init attempt {attempt} failed: {exc}")
                time.sleep(10)
        logger.error("Initialisation gave up; /health will report not-ready")

    import threading

    threading.Thread(target=bootstrap, daemon=True).start()


def require_auth(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> None:
    if not API_KEY:
        return  # auth disabled when no key configured (local dev only)
    if creds is None or creds.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_ready() -> None:
    if not _state["ready"]:
        raise HTTPException(
            status_code=503, detail=_state["error"] or "initialising, retry shortly"
        )


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = RAG_MODEL
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


def _question(req: ChatCompletionRequest) -> str:
    """The last user turn is the question the chain answers."""
    for msg in reversed(req.messages):
        if msg.role == "user":
            return msg.content.strip()
    return req.messages[-1].content.strip() if req.messages else ""


def _stream(model: str, chain, question: str) -> StreamingResponse:
    created = int(time.time())
    cid = f"chatcmpl-{uuid.uuid4().hex}"

    def frame(delta: Dict[str, Any], finish: Optional[str]) -> str:
        payload = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    def gen():
        yield frame({"role": "assistant"}, None)
        try:
            for chunk in chain.stream(question):
                if chunk:
                    yield frame({"content": chunk}, None)
        except Exception as exc:  # surface as a final assistant token
            yield frame({"content": f"\n\n[error] {exc}"}, None)
        yield frame({}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok" if _state["ready"] else "initialising", "error": _state["error"]}


@app.get("/v1/models")
def list_models(_: None = Depends(require_auth)) -> Dict[str, Any]:
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": RAG_MODEL, "object": "model", "created": now, "owned_by": "neo4j-rag"},
            {"id": LLM_MODEL, "object": "model", "created": now, "owned_by": "neo4j-rag"},
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(
    req: ChatCompletionRequest,
    _: None = Depends(require_auth),
    __: None = Depends(require_ready),
):
    model = req.model if req.model in (RAG_MODEL, LLM_MODEL) else RAG_MODEL
    chain = _state["chains"][model]
    question = _question(req)
    if not question:
        raise HTTPException(status_code=400, detail="no user message provided")

    if req.stream:
        return _stream(model, chain, question)

    try:
        answer = chain.invoke(question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"generation failed: {exc}")
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(question.split()),
            "completion_tokens": len(answer.split()),
            "total_tokens": len(question.split()) + len(answer.split()),
        },
    }
