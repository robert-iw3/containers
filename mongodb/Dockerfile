# syntax=docker/dockerfile:1

ARG repo="docker.io" \
    base_image="ubuntu:noble" \
    image_hash="4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

ENV GOSU_VERSION 1.17
ENV JSYAML_VERSION 3.13.1
ENV JSYAML_CHECKSUM 662e32319bdd378e91f67578e56a34954b0a2e33aca11d70ab9f4826af24b941
ARG MONGO_PACKAGE=mongodb-org  # Change to mongodb-enterprise for auditing
ARG MONGO_REPO=repo.mongodb.org
ENV MONGO_PACKAGE=${MONGO_PACKAGE} MONGO_REPO=${MONGO_REPO}
ENV MONGO_MAJOR 8.0
ENV MONGO_VERSION 8.0.26

LABEL org.opencontainers.image.version="8.0.26" \
      org.opencontainers.image.description="MongoDB 8.0.26 Community/Enterprise with CIS Hardening" \
      org.opencontainers.image.licenses="SSPL-1.0"

RUN \
	groupadd --gid 999 --system mongodb; \
	useradd --uid 999 --system --gid mongodb --home-dir /data/db mongodb; \
	mkdir -p /data/db /data/configdb /var/log/mongodb /var/run/mongodb; \
	chown -R mongodb:mongodb /data/db /data/configdb /var/log/mongodb /var/run/mongodb; \
    \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		jq \
		numactl \
		procps; \
	rm -rf /var/lib/apt/lists/*; \
	\
	savedAptMark="$(apt-mark showmanual)"; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		gnupg \
		wget; \
	rm -rf /var/lib/apt/lists/*; \
	\
# download/install gosu
	dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')"; \
	wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch"; \
	wget -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch.asc"; \
	export GNUPGHOME="$(mktemp -d)"; \
	gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4; \
	gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu; \
	gpgconf --kill all; \
	rm -rf "$GNUPGHOME" /usr/local/bin/gosu.asc; \
	chmod +x /usr/local/bin/gosu; \
	\
# download/install js-yaml
	mkdir -p /opt/js-yaml/; \
	wget -O /opt/js-yaml/js-yaml.tgz https://registry.npmjs.org/js-yaml/-/js-yaml-${JSYAML_VERSION}.tgz; \
	echo "$JSYAML_CHECKSUM /opt/js-yaml/js-yaml.tgz" | sha256sum -c -; \
	tar -xz --strip-components=1 -f /opt/js-yaml/js-yaml.tgz -C /opt/js-yaml package/dist/js-yaml.js package/package.json; \
	rm /opt/js-yaml/js-yaml.tgz; \
	ln -s /opt/js-yaml/dist/js-yaml.js /js-yaml.js; \
	\
# download/install MongoDB PGP keys
	export GNUPGHOME="$(mktemp -d)"; \
	wget -O KEYS 'https://pgp.mongodb.com/server-8.0.asc'; \
	gpg --batch --import KEYS; \
	mkdir -p /etc/apt/keyrings; \
	gpg --batch --export --armor '4B0752C1BCA238C0B4EE14DC41DE058A4E7DCA05' > /etc/apt/keyrings/mongodb.asc; \
	gpgconf --kill all; \
	rm -rf "$GNUPGHOME" KEYS; \
	\
	apt-mark auto '.*' > /dev/null; \
	apt-mark manual $savedAptMark > /dev/null; \
	apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
	\
# smoke test gosu
	gosu --version; \
	gosu nobody true; \
    \
    mkdir /docker-entrypoint-initdb.d; \
    \
    echo "deb [ signed-by=/etc/apt/keyrings/mongodb.asc ] http://$MONGO_REPO/apt/ubuntu noble/${MONGO_PACKAGE%-unstable}/$MONGO_MAJOR multiverse" | tee "/etc/apt/sources.list.d/${MONGO_PACKAGE%-unstable}.list"; \
    \
	export DEBIAN_FRONTEND=noninteractive; \
	apt-get update; \
	apt-get install -y \
		${MONGO_PACKAGE}=$MONGO_VERSION \
		${MONGO_PACKAGE}-server=$MONGO_VERSION \
		${MONGO_PACKAGE}-shell=$MONGO_VERSION \
		${MONGO_PACKAGE}-mongos=$MONGO_VERSION \
		${MONGO_PACKAGE}-tools=$MONGO_VERSION \
		${MONGO_PACKAGE}-database=$MONGO_VERSION \
		${MONGO_PACKAGE}-database-tools-extra=$MONGO_VERSION; \
	rm -rf /var/lib/apt/lists/*; \
	rm -rf /var/lib/mongodb; \
    # CIS 5.1: Strict perms on data/logs
    chmod -R 750 /data /var/log/mongodb; \
    chown -R mongodb:mongodb /data /var/log/mongodb;

VOLUME /data/db /data/configdb

ENV HOME /data/db

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER mongodb

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD gosu mongodb mongosh --quiet --eval "db.adminCommand('ping')" || exit 1

EXPOSE 27017
COPY tenant-init.js /docker-entrypoint-initdb.d/
RUN chown mongodb:mongodb /docker-entrypoint-initdb.d/tenant-init.js
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mongod", "--noscripting"]  # CIS 4.2: Disable JS for security/perf