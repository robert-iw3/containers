FROM golang:1.24.3-alpine3.21
WORKDIR /app
COPY main.go .
RUN go mod init goconsumer \
    && go get github.com/apache/pulsar-client-go/pulsar@v0.20.0 \
    && go mod tidy
CMD ["go", "run", "./main.go"]
