FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generator.py .

USER 65534

ENTRYPOINT ["python", "generator.py"]
