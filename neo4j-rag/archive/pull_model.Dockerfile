#syntax=docker/dockerfile:1.4
FROM ollama/ollama:latest AS ollama
FROM babashka/babashka:latest

# Copy ollama binary as client
COPY --from=ollama /usr/local/bin/ollama /bin/ollama

WORKDIR /app

COPY pull_model.clj .

ENTRYPOINT ["bb", "-f", "pull_model.clj"]