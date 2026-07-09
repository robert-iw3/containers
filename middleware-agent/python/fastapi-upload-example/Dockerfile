# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.19" \
    image_hash="13b7e62e8df80264dbb747995705a986aa530415763a6c58f84a3ca8af9a5bcd"

FROM ${repo}/${base_image}@sha256:${image_hash}

RUN apk add --no-cache \
        ca-certificates \
        python3 \
        py3-pip \
        tzdata

COPY requirements.txt /requirements.txt

RUN pip install -r requirements.txt

WORKDIR /app
COPY . /app
EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80", "--reload"]