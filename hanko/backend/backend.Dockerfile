# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="golang:1.23-alpine" \
    image_hash="a7ecaac5efda22510d8c903bdc6b19026543f1eac3317d47363680df22161bd8"

FROM ${repo}/${base_image}@sha256:${image_hash} AS go-builder

WORKDIR /go/src/hanko
RUN apk add --no-cache git ca-certificates && \
    update-ca-certificates

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /hanko -ldflags="-s -w" ./backend/main.go

FROM gcr.io/distroless/static:nonroot
COPY --chown=nonroot:nonroot --from=go-builder /hanko /hanko
COPY --chown=nonroot:nonroot --from=go-builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
USER nonroot:nonroot
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD ["curl", "-f", "http://localhost:8000/health"]
ENTRYPOINT ["/hanko"]