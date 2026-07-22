# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="alpine:3.19" \
    image_hash="13b7e62e8df80264dbb747995705a986aa530415763a6c58f84a3ca8af9a5bcd"

FROM ${repo}/${base_image}@sha256:${image_hash}

ARG AWS_DEFAULT_REGION
ARG AWS_REGION
ARG AWS_ACCOUNT_ID

ENV SIEGE_VER 4.1.6
COPY cdk/ .

# Install prerequisite packages
RUN \
    apk add --no-cache -t .siege-deps \
        wget \
        g++ \
        make \
        zlib-dev; \
    wget https://download.joedog.org/siege/siege-${SIEGE_VER}.tar.gz; \
    tar -xf siege-${SIEGE_VER}.tar.gz; \
    cd siege-${SIEGE_VER}; \
    ./configure; \
    make install; \
    cd /; \
    rm -rf siege-${SIEGE_VER}; \
    rm -f siege-${SIEGE_VER}.tar.gz; \
    apk del --no-network .siege-deps; \
    \
    apk add --no-cache \
        aws-cli \
        bash \
        python3 \
        py3-pip \
        jq \
        nodejs \
        npm; \
    \
    # Install cdk packages
    python3 -m venv cdk; \
    . cdk/bin/activate; \
    pip3 install --upgrade awslogs; \
    pip3 install -r requirements.txt; \
    \
    #  Verify environment variables required to communicate with AWS API's via the cli tools
    export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}; \
    export AWS_REGION=${AWS_REGION}; \
    export AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}; \
    \
    aws iam get-role --role-name "AWSServiceRoleForElasticLoadBalancing" || aws iam create-service-linked-role --aws-service-name "elasticloadbalancing.amazonaws.com"; \
    \
    aws iam get-role --role-name "AWSServiceRoleForECS" || aws iam create-service-linked-role --aws-service-name "ecs.amazonaws.com"; \
    \
    npm install -g aws-cdk; \
    \
    cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_DEFAULT_REGION; \
    cdk synth; \
    cdk diff; \
    cdk deploy --require-approval never

