"""Shared helpers: logging, Neo4j schema (constraints + indexes), parsing."""
import logging
import sys


class BaseLogger:
    """Minimal logger façade with ``.info``/``.error`` used across the package."""

    def __init__(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )
        _log = logging.getLogger("graphrag")
        self.info = _log.info
        self.error = _log.error


def extract_title_and_question(input_string: str) -> tuple[str, str]:
    """Split an LLM ``Title:/Question:`` response into its two parts."""
    lines = input_string.strip().split("\n")
    title = ""
    question = ""
    is_question = False
    for line in lines:
        if line.startswith("Title:"):
            title = line.split("Title: ", 1)[1].strip()
        elif line.startswith("Question:"):
            question = line.split("Question: ", 1)[1].strip()
            is_question = True
        elif is_question:
            question += "\n" + line.strip()
    return title, question


def create_constraints(driver) -> None:
    """Uniqueness constraints for the StackOverflow knowledge graph."""
    driver.query(
        "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE"
    )


def create_vector_index(driver, dimension: int = 384) -> None:
    """Vector + fulltext indexes the retriever queries.

    The vector index dimension must match the active embedding model
    (see ``load_embedding_model``); recreate it if the model changes.
    """
    driver.query(
        "CREATE VECTOR INDEX stackoverflow IF NOT EXISTS "
        "FOR (m:Question) ON m.embedding "
        "OPTIONS {indexConfig: {`vector.dimensions`: $d, `vector.similarity_function`: 'cosine'}}",
        {"d": dimension},
    )
    driver.query(
        "CREATE VECTOR INDEX top_answers IF NOT EXISTS "
        "FOR (m:Answer) ON m.embedding "
        "OPTIONS {indexConfig: {`vector.dimensions`: $d, `vector.similarity_function`: 'cosine'}}",
        {"d": dimension},
    )
    driver.query(
        "CREATE FULLTEXT INDEX stackoverflow_fulltext IF NOT EXISTS "
        "FOR (q:Question) ON EACH [q.title, q.body]"
    )
