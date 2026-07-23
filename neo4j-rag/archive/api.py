import os
from typing import Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from utils import create_vector_index, BaseLogger
from chains import load_embedding_model, load_llm, configure_llm_only_chain, configure_qa_rag_chain, generate_ticket
from langchain.callbacks.base import BaseCallbackHandler
from threading import Thread
from queue import Queue, Empty
from collections.abc import Generator
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
import json

load_dotenv(".env")

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
llm_name = os.getenv("LLM")
os.environ["NEO4J_URL"] = url

try:
    embeddings, _ = load_embedding_model(
        embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=BaseLogger()
    )
    neo4j_graph = Neo4jGraph(url=url, username=username, password=password, refresh_schema=False)
    create_vector_index(neo4j_graph)
    llm = load_llm(llm_name, logger=BaseLogger(), config={"ollama_base_url": ollama_base_url})
    llm_chain = configure_llm_only_chain(llm)
    rag_chain = configure_qa_rag_chain(
        llm, embeddings, embeddings_store_url=url, username=username, password=password
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize components: {str(e)}")

class QueueCallback(BaseCallbackHandler):
    def __init__(self, q: Queue):
        self.q = q

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.q.put(token)

    def on_llm_end(self, *args, **kwargs) -> None:
        self.q.put(None)  # Signal end

def stream(cb: callable, q: Queue) -> Generator:
    job_done = object()
    def task():
        cb()
        q.put(job_done)
    t = Thread(target=task)
    t.start()
    content = ""
    while True:
        try:
            next_token = q.get(True, timeout=1)
            if next_token is job_done or next_token is None:
                break
            content += next_token
            yield next_token, content
        except Empty:
            continue

app = FastAPI()
# Restricted CORS for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8505", "https://your-domain.com"],  # Restrict to front-end
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "Neo4j GenAI Stack API"}

class Question(BaseModel):
    text: str = Field(..., max_length=1000)  # Sanitization: limit length
    rag: bool = False
    hybrid: bool = True

class BaseTicket(BaseModel):
    text: str = Field(..., max_length=1000)

@app.get("/query-stream")
async def qstream(question: Question = Depends()) -> EventSourceResponse:
    try:
        question.text = question.text.strip().lower()  # Basic sanitization
        output_function = llm_chain if not question.rag else rag_chain
        q = Queue()
        def cb():
            output_function(
                {"question": question.text, "chat_history": []},
                callbacks=[QueueCallback(q)],
            )
        def generate():
            yield json.dumps({"init": True, "model": llm_name})
            for token, _ in stream(cb, q):
                yield json.dumps({"token": token})
        return EventSourceResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream query failed: {str(e)}")

@app.get("/query")
async def ask(question: Question = Depends()) -> Dict[str, Any]:
    try:
        question.text = question.text.strip().lower()  # Sanitization
        output_function = llm_chain if not question.rag else rag_chain
        result = output_function(
            {"question": question.text, "chat_history": []}, callbacks=[]
        )
        return {"result": result["answer"], "model": llm_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/generate-ticket")
async def generate_ticket_api(question: BaseTicket = Depends()) -> Dict[str, Any]:
    try:
        question.text = question.text.strip()  # Sanitization
        new_title, new_question = generate_ticket(
            neo4j_graph=neo4j_graph,
            llm_chain=llm_chain,
            input_question=question.text,
        )
        return {"result": {"title": new_title, "text": new_question}, "model": llm_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ticket generation failed: {str(e)}")