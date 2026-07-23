import os
import streamlit as st
from streamlit.logger import get_logger
from langchain.callbacks.base import BaseCallbackHandler
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from utils import create_vector_index
from chains import load_embedding_model, load_llm, configure_llm_only_chain, configure_qa_rag_chain, generate_ticket

load_dotenv(".env")

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
llm_name = os.getenv("LLM")
os.environ["NEO4J_URL"] = url

logger = get_logger(__name__)

neo4j_graph = Neo4jGraph(url=url, username=username, password=password, refresh_schema=False)
embeddings, _ = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger
)
create_vector_index(neo4j_graph)

class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)

llm = load_llm(llm_name, logger=logger, config={"ollama_base_url": ollama_base_url})
llm_chain = configure_llm_only_chain(llm)
rag_chain = configure_qa_rag_chain(
    llm, embeddings, embeddings_store_url=url, username=username, password=password
)

st.markdown("""
<style>
    .element-container:has([aria-label="Select RAG mode"]) {
        position: fixed;
        bottom: 33px;
        background: white;
        z-index: 101;
    }
    .stChatFloatingInputContainer {
        bottom: 20px;
    }
    textarea[aria-label="Description"] {
        height: 200px;
    }
</style>
""", unsafe_allow_html=True)

def chat_input():
    user_input = st.chat_input("What coding issue can I help you resolve today?")
    if user_input:
        with st.chat_message("user"):
            st.write(user_input)
        with st.chat_message("assistant"):
            st.caption(f"RAG: {name}")
            stream_handler = StreamHandler(st.empty())
            result = output_function(
                {"question": user_input, "chat_history": st.session_state.get("messages", [])},
                callbacks=[stream_handler]
            )["answer"]
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.messages.append({"role": "assistant", "content": result, "rag_mode": name})

def display_chat():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages[-5:]:  # Show last 5 exchanges
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.caption(f"RAG: {msg.get('rag_mode', 'Unknown')}")
            st.write(msg["content"])

    with st.expander("Not finding what you're looking for?"):
        st.write("Generate a draft ticket for our support team.")
        st.button("Generate ticket", type="primary", key="show_ticket", on_click=open_sidebar)

def mode_select() -> str:
    options = ["LLM only", "RAG (Vector + Graph)"]
    return st.radio("Select RAG mode", options, horizontal=True, index=1)

name = mode_select()
output_function = llm_chain if name == "LLM only" else rag_chain

def open_sidebar():
    st.session_state.open_sidebar = True

def close_sidebar():
    st.session_state.open_sidebar = False

if "open_sidebar" not in st.session_state:
    st.session_state.open_sidebar = False
if st.session_state.open_sidebar and st.session_state.messages:
    new_title, new_question = generate_ticket(
        neo4j_graph=neo4j_graph,
        llm_chain=llm_chain,
        input_question=st.session_state.messages[-2]["content"],  # Last user input
    )
    with st.sidebar:
        st.title("Ticket draft")
        st.write("Auto-generated draft ticket")
        st.text_input("Title", new_title)
        st.text_area("Description", new_question)
        st.button("Submit to support team", type="primary", key="submit_ticket", on_click=close_sidebar)

display_chat()
chat_input()