# Build the Hadoop cluster images (tagged :latest to match docker-compose.yml).
# Use podman by default; override with `make CR=docker build`.
CR ?= podman

build:
	$(CR) build -t hadoop-base:latest ./base
	@for c in namenode datanode resourcemanager nodemanager historyserver submit; do \
		$(CR) build -t hadoop-$$c:latest ./$$c || exit 1; \
	done

up:
	$(CR)-compose up -d

down:
	$(CR)-compose down

clean:
	$(CR)-compose down -v

# Distributed multi-format log-processing demo on the datalake (HDFS + YARN):
# create the datalake zones + load sample logs, then run the Streaming job.
datalake:
	./datalake/init_datalake.sh
	./datalake/process_logs.sh
