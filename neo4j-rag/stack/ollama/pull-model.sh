#!/bin/sh
# One-shot init: wait for Ollama, then pull the chat + embedding models named
# in the environment. Idempotent — Ollama skips models it already has.
set -eu

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
LLM="${LLM:-llama3.2:3b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-sentence_transformer}"

echo "-- waiting for Ollama at $OLLAMA_BASE_URL"
i=0
until curl -fsS "$OLLAMA_BASE_URL/api/version" >/dev/null 2>&1; do
    i=$((i + 2))
    [ "$i" -ge 300 ] && { echo "!! Ollama not reachable after 300s"; exit 1; }
    sleep 2
done

pull() {
    echo "-- pulling $1"
    curl -fsS "$OLLAMA_BASE_URL/api/pull" -d "{\"model\":\"$1\"}" \
        | tail -c 200 >/dev/null && echo "   done: $1"
}

# Only pull an LLM that runs on Ollama (skip hosted OpenAI/Bedrock/Google ids).
case "$LLM" in
    gpt-*|claude*|anthropic.*|amazon.*|cohere.*|meta.*|mistral.*|ai21.*|google-*) : ;;
    *) pull "$LLM" ;;
esac

# nomic-embed-text is only needed when embeddings run on Ollama.
[ "$EMBEDDING_MODEL" = "ollama" ] && pull "nomic-embed-text"

echo "-- model pull complete"
