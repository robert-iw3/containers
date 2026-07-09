from typing import List, Any, Optional, Dict
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_aws import BedrockEmbeddings, ChatBedrock
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain_community.cache import RedisCache  # New: for caching
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.retrievers.document_compressors import LLMChainExtractor  # For advanced RAG
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from utils import BaseLogger, extract_title_and_question
import redis  # For caching

AWS_MODELS = (
    "ai21.jamba-instruct-v1:0",
    "amazon.titan-text-premier-v1:0",
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "cohere.command-r-plus-v1:0",
    "meta.llama3-1-70b-instruct-v1:0",
    "mistral.mixtral-8x7b-instruct-v0:1",
)

def load_embedding_model(embedding_model_name: str, logger=BaseLogger(), config: dict = {}) -> tuple:
    try:
        if embedding_model_name == "ollama":
            embeddings = OllamaEmbeddings(
                base_url=config["ollama_base_url"], model="nomic-embed-text"
            )
            dimension = 768
            logger.info("Embedding: Using Ollama (nomic-embed-text)")
        elif embedding_model_name == "openai":
            embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
            dimension = 1536
            logger.info("Embedding: Using OpenAI (text-embedding-3-small)")
        elif embedding_model_name == "aws":
            embeddings = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")
            dimension = 1024
            logger.info("Embedding: Using AWS (titan-embed-text-v2)")
        elif embedding_model_name == "google-genai-embedding-001":
            embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
            dimension = 768
            logger.info("Embedding: Using Google Generative AI (text-embedding-004)")
        else:
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L12-v2",
                cache_folder="/embedding_model"
            )
            dimension = 384
            logger.info("Embedding: Using SentenceTransformer (all-MiniLM-L12-v2)")
        return embeddings, dimension
    except Exception as e:
        logger.error(f"Failed to load embedding model: {str(e)}")
        raise

def load_llm(llm_name: str, logger=BaseLogger(), config: dict = {}) -> Any:
    try:
        # Token logging for cost optimization
        tokens_used = 0  # Placeholder; integrate with callback for real usage
        if llm_name in ["gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-4o-mini"]:
            llm = ChatOpenAI(temperature=0, model_name=llm_name, streaming=True, max_tokens=4096)
            logger.info(f"LLM: Using GPT-4 variant: {llm_name} (tokens: {tokens_used})")
        elif llm_name == "gpt-3.5":
            llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo", streaming=True, max_tokens=4096)
            logger.info("LLM: Using GPT-3.5")
        elif llm_name == "claudev2":
            llm = ChatBedrock(
                model_id="anthropic.claude-v2",
                model_kwargs={"temperature": 0.0, "max_tokens": 4096},
                streaming=True,
            )
            logger.info("LLM: ClaudeV2 (consider upgrading to claude-3-5-sonnet)")
        elif any(model.startswith(llm_name) for model in AWS_MODELS):
            llm = ChatBedrock(
                model_id=llm_name,
                model_kwargs={"temperature": 0.0, "max_tokens": 4096},
                streaming=True,
            )
            logger.info(f"LLM: AWS {llm_name}")
        elif llm_name:
            llm = ChatOllama(
                temperature=0,
                base_url=config["ollama_base_url"],
                model=llm_name,
                streaming=True,
                top_k=40,
                top_p=0.95,
                repeat_penalty=1.1,
                num_ctx=8192,
            )
            logger.info(f"LLM: Using Ollama: {llm_name} (tokens: {tokens_used})")
        else:
            llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo", streaming=True, max_tokens=4096)
            logger.info("LLM: Falling back to GPT-3.5")
        return llm
    except Exception as e:
        logger.error(f"Failed to load LLM: {str(e)}")
        raise

def configure_llm_only_chain(llm: Any) -> callable:
    template = """
    You are a helpful assistant for answering programming questions.
    Provide concise, accurate responses. If you don't know the answer, say so and avoid speculation.
    """
    system_message_prompt = SystemMessagePromptTemplate.from_template(template)
    human_template = "{question}"
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
    chat_prompt = ChatPromptTemplate.from_messages(
        [system_message_prompt, human_message_prompt]
    )

    def generate_llm_output(
        user_input: Dict[str, Any], callbacks: List[Any], prompt=chat_prompt
    ) -> Dict[str, str]:
        try:
            chain = prompt | llm
            answer = chain.invoke(
                {"question": user_input["question"]}, config={"callbacks": callbacks}
            ).content
            return {"answer": answer}
        except Exception as e:
            return {"answer": f"Error generating response: {str(e)}"}

    return generate_llm_output

def configure_qa_rag_chain(llm: Any, embeddings: Any, embeddings_store_url: str, username: str, password: str, k: int = 4) -> Any:
    # Setup Redis cache for performance
    try:
        cache = RedisCache(redis_url="redis://localhost:6379")  # Assume Redis service
        llm_with_cache = llm.with_config(cache=cache)
    except Exception as e:
        print(f"Redis cache failed: {e}, using uncached LLM")
        llm_with_cache = llm

    general_system_template = """
    Use the following context to answer the question. The context contains StackOverflow question-answer pairs with links.
    Prefer information from accepted or highly upvoted answers. Use only the provided context to ensure accuracy.
    If you don't know the answer, state that clearly. Cite useful StackOverflow links at the end.
    ----
    {summaries}
    ----
    Include a 'Sources' section with links to relevant StackOverflow questions from the context.
    """
    general_user_template = "Question:```{question}```"
    messages = [
        SystemMessagePromptTemplate.from_template(general_system_template),
        HumanMessagePromptTemplate.from_template(general_user_template),
    ]
    qa_prompt = ChatPromptTemplate.from_messages(messages)

    qa_chain = load_qa_with_sources_chain(
        llm_with_cache,  # Cached LLM
        chain_type="stuff",
        prompt=qa_prompt,
    )

    # Advanced RAG: Parent-child retriever for better context (child chunks, parent docs)
    kg = Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=embeddings_store_url,
        username=username,
        password=password,
        database="neo4j",
        index_name="stackoverflow",
        text_node_property="body",
        search_type="hybrid",
        distance_strategy="cosine",
        retrieval_query="""
        // Inline comment: Retrieve top 3 accepted/high-score answers per question for context
        WITH node AS question, score AS similarity
        CALL { WITH question
            MATCH (question)<-[:ANSWERS]-(answer)
            WITH answer
            ORDER BY answer.is_accepted DESC, answer.score DESC
            WITH collect(answer)[..3] as answers
            RETURN reduce(str='', answer IN answers | str +
                    '\n### Answer (Accepted: '+ answer.is_accepted +
                    ' Score: ' + answer.score + '): '+ answer.body + '\n') as answerTexts
        }
        RETURN '##Question: ' + question.title + '\n' + question.body + '\n'
            + answerTexts AS text, similarity as score, {source: question.link} AS metadata
        ORDER BY similarity DESC
        """,
        relevance_score_fn=lambda score: 1.0 - score,
    )

    # Parent-child retriever: Compress/re-rank for advanced RAG
    compressor = LLMChainExtractor.from_llm(llm_with_cache)
    retriever = kg.as_retriever(search_kwargs={"k": k}) | compressor

    kg_qa = RetrievalQAWithSourcesChain(
        combine_documents_chain=qa_chain,
        retriever=retriever,  # Advanced retriever
        reduce_k_below_max_tokens=False,
        max_tokens_limit=4096,
    )
    return kg_qa

def generate_ticket(neo4j_graph: Any, llm_chain: callable, input_question: str) -> tuple:
    try:
        records = neo4j_graph.query(
            "MATCH (q:Question) RETURN q.title AS title, q.body AS body ORDER BY q.score DESC LIMIT 3"
        )
        questions = [(q["title"], q["body"]) for q in records]
        questions_prompt = "".join(
            f"{i}. \n{q[0]}\n----\n\n{q[1][:150]}\n\n----\n\n"
            for i, q in enumerate(questions, 1)
        )

        gen_system_template = f"""
        You're an expert in formulating high-quality questions.
        Formulate a question in the same style and tone as the following examples.
        {questions_prompt}
        ---
        Use only the provided question. Return in this format:
        ---
        Title: New title
        Question: New question
        ---
        """
        system_prompt = SystemMessagePromptTemplate.from_template(
            gen_system_template, template_format="jinja2"
        )
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                system_prompt,
                SystemMessagePromptTemplate.from_template(
                    """
                    Respond in the following template format:
                    ---
                    Title: New title
                    Question: New question
                    ---
                    """
                ),
                HumanMessagePromptTemplate.from_template("{question}"),
            ]
        )
        llm_response = llm_chain(
            {"question": f"Rewrite this question: ```{input_question}```", "chat_history": []},
            [],
            chat_prompt,
        )
        new_title, new_question = extract_title_and_question(llm_response["answer"])
        return (new_title, new_question)
    except Exception as e:
        return ("Error generating ticket", f"Failed to generate: {str(e)}")