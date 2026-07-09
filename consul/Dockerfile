# consul: uses service identities and traditional networking practices to help organizations securely connect applications running in any environment.

ARG repo="docker.io" \
    base_image="alpine:3.24" \
    image_hash="79ff19e9084a00eece421b2523fb93e22d730e2c0e525905de047e848e56d95f"

FROM ${repo}/${base_image}@sha256:${image_hash} AS base

RUN \
    apk add --no-cache \
		bash \
    	dumb-init \
		libc6-compat \
		iptables \
		tzdata \
		curl \
		ca-certificates \
		iputils \
		libcap \
		openssl \
		su-exec \
		jq \
		clamav \
		freshclam

FROM base as build-env

ENV CONSUL_VER=2.0.1 \
    CONSUL_GPGKEY=C874011F0AB405110D02105534365D9472D7468F

RUN \
     apk add --no-cache -t .build-deps \
		ca-certificates \
		gnupg \
		unzip \
		wget; \
		\
	    apkArch="$(apk --print-arch)"; \
	    case "$apkArch" in armhf) ARCH='arm' ;; \
	      aarch64) ARCH='arm64' ;; \
	      x86_64) ARCH='amd64' ;; \
	      x86) ARCH='386' ;; \
	      *) echo >&2 "error: unsupported architecture: $apkArch"; \
	      exit 1 ;; \
	    esac; \
		\
	    found=''; \
	    for server in \
	      hkps://keys.openpgp.org \
	      hkps://keyserver.ubuntu.com \
	      hkps://pgp.mit.edu; do \
	      echo "Fetching GPG key $CONSUL_GPGKEY from $server"; \
	      gpg --batch --keyserver "$server" --recv-keys "$CONSUL_GPGKEY"; \
	      found=yes && break; \
	    done; \
		\
	    test -z "$found" && echo >&2 "error: failed to fetch GPG key $CONSUL_GPGKEY" && exit 1; \
	    mkdir -p /tmp/build; \
	    cd /tmp/build; \
	    wget --progress=bar:force https://releases.hashicorp.com/consul/${CONSUL_VER}/consul_${CONSUL_VER}_linux_${ARCH}.zip; \
	    wget --progress=bar:force https://releases.hashicorp.com/consul/${CONSUL_VER}/consul_${CONSUL_VER}_SHA256SUMS; \
	    wget --progress=bar:force https://releases.hashicorp.com/consul/${CONSUL_VER}/consul_${CONSUL_VER}_SHA256SUMS.sig; \
	    gpg --batch --verify consul_${CONSUL_VER}_SHA256SUMS.sig consul_${CONSUL_VER}_SHA256SUMS; \
	    grep consul_${CONSUL_VER}_linux_${ARCH}.zip consul_${CONSUL_VER}_SHA256SUMS | sha256sum -c; \
	    unzip -d /tmp/build consul_${CONSUL_VER}_linux_${ARCH}.zip; \
	    cp /tmp/build/consul /bin/consul; \
	    if [ -f /tmp/build/EULA.txt ]; then mkdir -p /usr/share/doc/consul; mv /tmp/build/EULA.txt /usr/share/doc/consul/EULA.txt; fi; \
	    if [ -f /tmp/build/TermsOfEvaluation.txt ]; then mkdir -p /usr/share/doc/consul; mv /tmp/build/TermsOfEvaluation.txt /usr/share/doc/consul/TermsOfEvaluation.txt; fi; \
	    rm -rf /tmp/build; \
	    gpgconf --kill dirmngr; \
	    gpgconf --kill gpg-agent; \
	    apk del --no-network --purge .consul-deps; \
	    rm -rf /root/.gnupg /var/cache/apk/*

FROM base

LABEL \
	org.opencontainers.image.name='Hashicorp Consul' \
    org.opencontainers.image.description='Automate Service Networking Across Clouds.' \
    org.opencontainers.image.usage='https://developer.hashicorp.com/consul/docs' \
    org.opencontainers.image.url='https://www.hashicorp.com/products/consul' \
    org.opencontainers.image.vendor='Hashicorp' \
    org.opencontainers.image.licenses='Mozilla Public License 2.0' \
    org.opencontainers.image.schema-version='2.0.1' \
    MAINTAINER="@rw"

RUN \
    addgroup -g 65535 consul; \
    adduser --shell /sbin/nologin --disabled-password -h /home/consul --uid 65535 --ingroup consul consul; \
    mkdir -p /consul/data; \
    mkdir -p /consul/config; \
    chown -R consul:consul /consul

COPY --chown=consul:consul --from=build-env /bin/consul /usr/local/bin/
COPY --chmod=755 entrypoint.sh /usr/local/bin/
# quick single node bootstrap, advise use compose to create cluster
#COPY --chown=consul:consul single-node.json /bootstrap.json
COPY --chown=consul:consul vault-storage.json /consul/config/

RUN \
	#smoke
	consul version; \
    freshclam; \
    clamscan -rvi -l /home/consul/last_scan.log --exclude-dir="^/sys" /; \
    chown consul:consul /home/consul/last_scan.log; \
    grep -Hrn FOUND /home/consul/last_scan.log; \
    apk del --no-network clamav freshclam; \
    rm -rf /var/cache/apk/*; \
    test -e /etc/nsswitch.conf || echo 'hosts: files dns' > /etc/nsswitch.conf; \
	\
	# replace encrypt: in "consul-agent.json" with this key (podman exec consul-leader sh -c "cat /consul/config/key.txt")
	mkdir -p /consul/certs; \
	cd /consul/certs; \
	consul keygen 2>&1 | tee /consul/config/key.txt; \
	consul tls ca create -domain=consul; \
	consul tls cert create -server -dc=dc1 -domain=consul; \
	# Create API certs for Vault
	mkdir -p /consul/certs/vault; \
	consul tls cert create -cli -ca="consul-agent-ca.pem"; \
	mv dc1-cli-consul-0.pem /consul/certs/vault/; \
	mv dc1-cli-consul-0-key.pem /consul/certs/vault/; \
	chown -R consul:consul /consul

VOLUME /consul/data
EXPOSE 8300
EXPOSE 8301 8301/udp 8302 8302/udp
EXPOSE 8500 8600 8600/udp
EXPOSE 8501/tcp
USER consul
ENTRYPOINT [ "entrypoint.sh" ]
# single node quick demo
#CMD [ "/bin/bash", "-c", "consul agent -config-file=/bootstrap.json" ]
