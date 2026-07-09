import pytest
from chains import load_llm, load_embedding_model, configure_llm_only_chain

def test_load_llm():
    llm = load_llm("gpt-3.5")  # Fallback test
    assert llm is not None
    assert hasattr(llm, "invoke")

def test_load_embedding_model():
    embeddings, dim = load_embedding_model("sentence_transformer")
    assert embeddings is not None
    assert dim == 384  # Expected for MiniLM

def test_configure_llm_only_chain():
    from langchain_openai import ChatOpenAI
    mock_llm = ChatOpenAI(model="gpt-3.5-turbo")
    chain = configure_llm_only_chain(mock_llm)
    result = chain({"question": "Test query"}, [])
    assert "answer" in result
    assert len(result["answer"]) > 0