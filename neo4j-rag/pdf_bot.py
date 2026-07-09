import os
import streamlit as st
from langchain.chains import RetrievalQA
from PyPDF2 import PdfReader
from langchain.callbacks.base import BaseCallbackHandler
from langchain_text_splitters import SemanticChunker
from langchain_community.vectorstores import Neo4jVector
from streamlit.logger import get_logger
from chains import load_embedding_model, load_llm
from dotenv import load_dotenv

load_dotenv(".env")

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
llm_name = os.getenv("LLM")
os.environ["NEO4J_URL"] = url

logger = get_logger(__name__)

embeddings, _ = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger
)

class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)

llm = load_llm(llm_name, logger=logger, config={"ollama_base_url": ollama_base_url})

def main():
    st.header("📄 Chat with your PDF file")

    pdf = st.file_uploader("Upload your PDF", type="pdf")
    if pdf is not None:
        pdf_reader = PdfReader(pdf)
        text = "".join(page.extract_text() or "" for page in pdf_reader.pages)

        chunker = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
        chunks = chunker.split_text(text)

        vectorstore = Neo4jVector.from_texts(
            chunks,
            url=url,
            username=username,
            password=password,
            embedding=embeddings,
            index_name="pdf_bot",
            node_label="PdfBotChunk",
            pre_delete_collection=True,
            search_type="hybrid",
        )
        qa = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        )

        query = st.text_input("Ask questions about your PDF file")
        if query:
            stream_handler = StreamHandler(st.empty())
            with st.spinner("Generating response..."):
                result = qa.run(query, callbacks=[stream_handler])
                st.markdown(result)

if __name__ == "__main__":
    main()