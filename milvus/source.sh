#!/bin/bash

git clone https://github.com/milvus-io/milvus.git; cd milvus
podman-compose up -d
