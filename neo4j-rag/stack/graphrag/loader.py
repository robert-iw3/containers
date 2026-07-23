"""
CLI loader: import StackOverflow Q&A into the Neo4j knowledge graph.

Replaces the former Streamlit loader. Run as a one-shot job:

  python loader.py --tag neo4j --pages 2
  python loader.py --high-score
"""
import argparse
import os
import sys

import requests
from langchain_neo4j import Neo4jGraph

from chains import load_embedding_model
from utils import BaseLogger, create_constraints, create_vector_index

logger = BaseLogger()
SO_API = "https://api.stackexchange.com/2.3/search/advanced"

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://neo4j:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence_transformer")

embeddings, dimension = load_embedding_model(
    EMBEDDING_MODEL, config={"ollama_base_url": OLLAMA_BASE_URL}, logger=logger
)
graph = Neo4jGraph(
    url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD, refresh_schema=False
)

IMPORT_QUERY = """
UNWIND $data AS q
MERGE (question:Question {id:q.question_id})
ON CREATE SET question.title = q.title, question.link = q.link, question.score = q.score,
    question.favorite_count = q.favorite_count, question.creation_date = datetime({epochSeconds: q.creation_date}),
    question.body = q.body_markdown, question.embedding = q.embedding
FOREACH (tagName IN q.tags |
    MERGE (tag:Tag {name:tagName})
    MERGE (question)-[:TAGGED]->(tag)
)
FOREACH (a IN q.answers |
    MERGE (question)<-[:ANSWERS]-(answer:Answer {id:a.answer_id})
    SET answer.is_accepted = a.is_accepted,
        answer.score = a.score,
        answer.creation_date = datetime({epochSeconds:a.creation_date}),
        answer.body = a.body_markdown,
        answer.embedding = a.embedding
    MERGE (answerer:User {id:coalesce(a.owner.user_id, "deleted")})
    ON CREATE SET answerer.display_name = a.owner.display_name,
                  answerer.reputation= a.owner.reputation
    MERGE (answer)<-[:PROVIDED]-(answerer)
)
WITH * WHERE NOT q.owner.user_id IS NULL
MERGE (owner:User {id:q.owner.user_id})
ON CREATE SET owner.display_name = q.owner.display_name,
              owner.reputation = q.owner.reputation
MERGE (owner)-[:ASKED]->(question)
"""


def insert_so_data(data: dict) -> int:
    items = data.get("items", [])
    for q in items:
        question_text = q["title"] + "\n" + q["body_markdown"]
        q["embedding"] = embeddings.embed_query(question_text)
        for a in q["answers"]:
            a["embedding"] = embeddings.embed_query(question_text + "\n" + a["body_markdown"])
    graph.query(IMPORT_QUERY, {"data": items})
    return len(items)


def load_tag(tag: str, page: int) -> int:
    params = (
        f"?pagesize=250&page={page}&order=desc&sort=creation&answers=1&tagged={tag}"
        "&site=stackoverflow&filter=!*236eb_eL9rai)MOSNZ-6D3Q6ZKb0buI*IVotWaTb"
    )
    return insert_so_data(requests.get(SO_API + params, timeout=60).json())


def load_high_score() -> int:
    params = (
        "?fromdate=1664150400&order=desc&sort=votes&site=stackoverflow&"
        "filter=!.DK56VBPooplF.)bWW5iOX32Fh1lcCkw1b_Y6Zkb7YD8.ZMhrR5.FRRsR6Z1uK8*Z5wPaONvyII"
    )
    return insert_so_data(requests.get(SO_API + params, timeout=60).json())


def main() -> int:
    parser = argparse.ArgumentParser(description="Load StackOverflow data into Neo4j")
    parser.add_argument("--tag", default="neo4j", help="StackOverflow tag to import")
    parser.add_argument("--pages", type=int, default=1, help="pages of 250 questions")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument(
        "--high-score", action="store_true", help="import top-voted questions instead of a tag"
    )
    args = parser.parse_args()

    logger.info("Ensuring constraints and indexes")
    create_constraints(graph)
    create_vector_index(graph, dimension)

    total = 0
    if args.high_score:
        total += load_high_score()
    else:
        for i in range(args.pages):
            total += load_tag(args.tag, args.start_page + i)
    logger.info(f"Imported {total} questions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
