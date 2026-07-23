"""
LLM / embedding loaders and the Neo4j GraphRAG retrieval chain (LangChain 1.x LCEL).

Providers are selected by environment (LLM, EMBEDDING_MODEL); Ollama is the
default so the stack runs fully local with no external API keys. The chains are
plain LCEL runnables: ``.invoke(question)`` returns a string and
``.stream(question)`` yields string chunks.
"""
import os
from typing import Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_neo4j import Neo4jVector

from utils import BaseLogger

AWS_MODELS = (
    "ai21.jamba-instruct-v1:0",
    "amazon.titan-text-premier-v1:0",
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "cohere.command-r-plus-v1:0",
    "meta.llama3-1-70b-instruct-v1:0",
    "mistral.mixtral-8x7b-instruct-v0:1",
)

# Vector dimensions per embedding backend; must match the Neo4j vector index.
EMBEDDING_DIMENSIONS = {
    "ollama": 768,
    "openai": 1536,
    "aws": 1024,
    "google-genai-embedding-001": 768,
    "sentence_transformer": 384,
}


def load_embedding_model(
    embedding_model_name: str, logger=BaseLogger(), config: dict | None = None
) -> tuple[Any, int]:
    config = config or {}
    if embedding_model_name == "ollama":
        from langchain_ollama import OllamaEmbeddings

        embeddings = OllamaEmbeddings(
            base_url=config["ollama_base_url"], model="nomic-embed-text"
        )
        logger.info("Embedding: Ollama (nomic-embed-text)")
    elif embedding_model_name == "openai":
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        logger.info("Embedding: OpenAI (text-embedding-3-small)")
    elif embedding_model_name == "aws":
        from langchain_aws import BedrockEmbeddings

        embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")
        logger.info("Embedding: AWS Bedrock (titan-embed-text-v2)")
    elif embedding_model_name == "google-genai-embedding-001":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        logger.info("Embedding: Google GenAI (text-embedding-004)")
    else:
        embedding_model_name = "sentence_transformer"
        from langchain_huggingface import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L12-v2",
            cache_folder="/embedding_model",
        )
        logger.info("Embedding: SentenceTransformer (all-MiniLM-L12-v2)")
    return embeddings, EMBEDDING_DIMENSIONS[embedding_model_name]


def load_llm(llm_name: str, logger=BaseLogger(), config: dict | None = None) -> Any:
    config = config or {}
    if llm_name in ("gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-4o-mini", "gpt-3.5"):
        from langchain_openai import ChatOpenAI

        model = "gpt-3.5-turbo" if llm_name == "gpt-3.5" else llm_name
        logger.info(f"LLM: OpenAI {model}")
        return ChatOpenAI(temperature=0, model=model, streaming=True, max_tokens=4096)
    if any(model.startswith(llm_name) for model in AWS_MODELS):
        from langchain_aws import ChatBedrock

        logger.info(f"LLM: AWS Bedrock {llm_name}")
        return ChatBedrock(
            model_id=llm_name,
            model_kwargs={"temperature": 0.0, "max_tokens": 4096},
            streaming=True,
        )
    if llm_name:
        from langchain_ollama import ChatOllama

        logger.info(f"LLM: Ollama {llm_name}")
        return ChatOllama(
            temperature=0,
            base_url=config["ollama_base_url"],
            model=llm_name,
            num_ctx=8192,
        )
    raise ValueError("LLM env var is empty; set it to an Ollama/OpenAI/Bedrock model")


def configure_llm_only_chain(llm: Any) -> Runnable:
    """Plain assistant chain with no retrieval. Input: question string."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant for answering programming questions. "
                "Provide concise, accurate responses. If you don't know the answer, "
                "say so and avoid speculation.",
            ),
            ("human", "{question}"),
        ]
    )
    return {"question": RunnablePassthrough()} | prompt | llm | StrOutputParser()


def _format_docs(docs: list[Document]) -> str:
    blocks = []
    for d in docs:
        source = d.metadata.get("source", "")
        blocks.append(d.page_content + (f"\nSource: {source}" if source else ""))
    return "\n\n".join(blocks) if blocks else "No relevant context found."


def configure_qa_rag_chain(
    llm: Any,
    embeddings: Any,
    embeddings_store_url: str,
    username: str,
    password: str,
    k: int = 4,
    search_type: str | None = None,
) -> Runnable:
    """GraphRAG chain: vector search over questions, expanded to their top answers.

    ``search_type`` defaults to RAG_SEARCH_TYPE (``vector``); set ``hybrid`` to
    also match the fulltext index. Input: question string; output: answer string.
    """
    search_type = (search_type or os.getenv("RAG_SEARCH_TYPE", "vector")).lower()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Use the following context to answer the question. The context contains "
                "StackOverflow question-answer pairs with links. Prefer information from "
                "accepted or highly upvoted answers, and use only the provided context. "
                "If you don't know the answer, state that clearly. End with a 'Sources' "
                "section listing the relevant StackOverflow links.\n----\n{context}\n----",
            ),
            ("human", "Question: ```{question}```"),
        ]
    )

    store_kwargs = dict(
        embedding=embeddings,
        url=embeddings_store_url,
        username=username,
        password=password,
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
        index_name="stackoverflow",
        text_node_property="body",
        search_type=search_type,
        retrieval_query="""
        WITH node AS question, score AS similarity
        CALL {
            WITH question
            MATCH (question)<-[:ANSWERS]-(answer)
            WITH answer ORDER BY answer.is_accepted DESC, answer.score DESC
            WITH collect(answer)[..3] AS answers
            RETURN reduce(str='', answer IN answers | str +
                    '\n### Answer (Accepted: ' + toString(answer.is_accepted) +
                    ' Score: ' + toString(answer.score) + '): ' + answer.body + '\n') AS answerTexts
        }
        RETURN '##Question: ' + question.title + '\n' + question.body + '\n' + answerTexts AS text,
            similarity AS score, {source: question.link} AS metadata
        ORDER BY similarity DESC
        """,
    )
    if search_type == "hybrid":
        store_kwargs["keyword_index_name"] = "stackoverflow_fulltext"
    retriever = Neo4jVector.from_existing_index(**store_kwargs).as_retriever(
        search_kwargs={"k": k}
    )

    return (
        {
            "context": retriever | RunnableLambda(_format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
