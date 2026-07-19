FROM docker.io/library/python:3.12-slim

WORKDIR /uat
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pytest.ini corpus.py test_milvus_uat.py ./

USER nobody
CMD ["pytest", "-q"]
