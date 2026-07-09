# syntax=docker/dockerfile:1
ARG repo="docker.io" \
    base_image="ubuntu:focal" \
    image_hash="218bb51abbd1864df8be26166f847547b3851a89999ca7bfceb85ca9b5d2e95d"

FROM ${repo}/${base_image}@sha256:${image_hash}

ENV GITLAB_VERSION=16.5.1 \
    RUBY_VERSION=3.0.6 \
    RUBY_SOURCE_SHA256SUM="6e6cbd490030d7910c0ff20edefab4294dfcd1046f0f8f47f78b597987ac683e" \
    GOLANG_VERSION=1.21.3 \
    GITLAB_SHELL_VERSION=14.29.0 \
    GITLAB_PAGES_VERSION=16.5.1 \
    GITALY_SERVER_VERSION=16.5.1 \
    GITLAB_USER="git" \
    GITLAB_HOME="/home/git" \
    GITLAB_LOG_DIR="/var/log/gitlab" \
    GITLAB_CACHE_DIR="/etc/docker-gitlab" \
    RAILS_ENV=production \
    NODE_ENV=production

ENV GITLAB_INSTALL_DIR="${GITLAB_HOME}/gitlab" \
    GITLAB_SHELL_INSTALL_DIR="${GITLAB_HOME}/gitlab-shell" \
    GITLAB_GITALY_INSTALL_DIR="${GITLAB_HOME}/gitaly" \
    GITLAB_DATA_DIR="${GITLAB_HOME}/data" \
    GITLAB_BUILD_DIR="${GITLAB_CACHE_DIR}/build" \
    GITLAB_RUNTIME_DIR="${GITLAB_CACHE_DIR}/runtime"

RUN \
    apt-get update -y; \
    DEBIAN_FRONTEND=noninteractive; \
    apt-get install --no-install-recommends -y \
      wget \
      ca-certificates \
      apt-transport-https \
      gnupg2; \
    apt-get upgrade -y; \
    rm -rf /var/lib/apt/lists/*

RUN \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv E1DD270288B4E6030699E45FA1715D88E1DF1F24; \
    echo "deb http://ppa.launchpad.net/git-core/ppa/ubuntu focal main" >> /etc/apt/sources.list; \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 8B3981E7A6852F782CC4951600A6F0A3C300EE8C; \
    echo "deb http://ppa.launchpad.net/nginx/stable/ubuntu focal main" >> /etc/apt/sources.list; \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - ; \
    echo 'deb http://apt.postgresql.org/pub/repos/apt/ focal-pgdg main' > /etc/apt/sources.list.d/pgdg.list; \
    wget --quiet -O - https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - ; \
    echo 'deb https://deb.nodesource.com/node_18.x focal main' > /etc/apt/sources.list.d/nodesource.list; \
    wget --quiet -O - https://dl.yarnpkg.com/debian/pubkey.gpg  | apt-key add - ; \
    echo 'deb https://dl.yarnpkg.com/debian/ stable main' > /etc/apt/sources.list.d/yarn.list; \
    apt-get update -y; \
    DEBIAN_FRONTEND=noninteractive; \
    apt-get install --no-install-recommends -y \
      sudo \
      supervisor \
      logrotate \
      locales \
      curl \
      nginx \
      openssh-server \
      postgresql-contrib \
      redis-tools \
      postgresql-client-13 \
      postgresql-client-14 \
      postgresql-client-15 \
      python3 \
      python3-docutils \
      nodejs \
      yarn \
      gettext-base \
      graphicsmagick \
      libpq5 \
      zlib1g \
      libyaml-0-2 \
      libssl1.1 \
      libgdbm6 \
      libreadline8 \
      libncurses5 \
      libffi7 \
      libxml2 \
      libxslt1.1 \
      libcurl4 \
      libicu66 \
      libre2-dev \
      tzdata \
      unzip \
      libimage-exiftool-perl \
      libmagic1; \
    update-locale LANG=C.UTF-8 LC_MESSAGES=POSIX; \
    locale-gen en_US.UTF-8; \
    DEBIAN_FRONTEND=noninteractive; \
    dpkg-reconfigure locales; \
    rm -rf /var/lib/apt/lists/*

COPY src/build/ ${GITLAB_BUILD_DIR}/
RUN bash ${GITLAB_BUILD_DIR}/install.sh

COPY src/runtime/ ${GITLAB_RUNTIME_DIR}/
COPY --chmod=755 entrypoint.sh /sbin/entrypoint.sh

ENV prometheus_multiproc_dir="/dev/shm"

ARG BUILD_DATE
ARG VCS_REF

EXPOSE 22/tcp 80/tcp 443/tcp

VOLUME ["${GITLAB_DATA_DIR}", "${GITLAB_LOG_DIR}","${GITLAB_HOME}/gitlab/node_modules"]
WORKDIR ${GITLAB_INSTALL_DIR}
ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["app:start"]
