FROM docker.io/debian:buster

LABEL usage="docker run -i -t --privileged -v /root/.falco:/root/.falco -v /proc:/host/proc:ro -v /boot:/host/boot:ro -v /lib/modules:/host/lib/modules:ro -v /usr:/host/usr:ro -v /etc:/host/etc:ro falcosecurity/falco-driver-loader:latest-buster [driver] [options]"

ARG TARGETARCH

ARG FALCO_VERSION=latest
ARG VERSION_BUCKET=deb
ENV VERSION_BUCKET=${VERSION_BUCKET}

ENV FALCO_VERSION=${FALCO_VERSION}
ENV HOST_ROOT /host
ENV HOME /root

RUN cp /etc/skel/.bashrc /root ; cp /etc/skel/.profile /root

RUN \
	apt-get update ; \
	apt-get install -y --no-install-recommends \
		bash-completion \
		bc \
		bison \
		clang-7 \
		ca-certificates \
		curl \
		dkms \
		flex \
		gnupg2 \
		gcc \
		jq \
		libc6-dev \
		libssl-dev \
		llvm-7 \
		netcat \
		patchelf \
		xz-utils \
		zstd; \
	rm -rf /var/lib/apt/lists/*; \
	\
	if [ "$TARGETARCH" = "amd64" ]; \
	then apt-get install -y --no-install-recommends libmpx2; \
	fi; \
	\
	if [ "$TARGETARCH" = "amd64" ]; then curl -L -o libcilkrts5_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/libcilkrts5_6.3.0-18_${TARGETARCH}.deb; fi; \
	curl -L -o cpp-6_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/cpp-6_6.3.0-18_${TARGETARCH}.deb; \
	curl -L -o gcc-6-base_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/gcc-6-base_6.3.0-18_${TARGETARCH}.deb; \
	curl -L -o gcc-6_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/gcc-6_6.3.0-18_${TARGETARCH}.deb; \
	curl -L -o libasan3_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/libasan3_6.3.0-18_${TARGETARCH}.deb; \
	curl -L -o libgcc-6-dev_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/libgcc-6-dev_6.3.0-18_${TARGETARCH}.deb; \
	curl -L -o libubsan0_6.3.0-18_${TARGETARCH}.deb https://download.falco.org/dependencies/libubsan0_6.3.0-18_${TARGETARCH}.deb; \
	curl -L -o libmpfr4_3.1.3-2_${TARGETARCH}.deb https://download.falco.org/dependencies/libmpfr4_3.1.3-2_${TARGETARCH}.deb; \
	curl -L -o libisl15_0.18-1_${TARGETARCH}.deb https://download.falco.org/dependencies/libisl15_0.18-1_${TARGETARCH}.deb; \
	dpkg -i cpp-6_6.3.0-18_${TARGETARCH}.deb gcc-6-base_6.3.0-18_${TARGETARCH}.deb gcc-6_6.3.0-18_${TARGETARCH}.deb libasan3_6.3.0-18_${TARGETARCH}.deb; \
	if [ "$TARGETARCH" = "amd64" ]; then dpkg -i libcilkrts5_6.3.0-18_${TARGETARCH}.deb; fi; \
	dpkg -i libgcc-6-dev_6.3.0-18_${TARGETARCH}.deb libubsan0_6.3.0-18_${TARGETARCH}.deb libmpfr4_3.1.3-2_${TARGETARCH}.deb libisl15_0.18-1_${TARGETARCH}.deb; \
	rm -f cpp-6_6.3.0-18_${TARGETARCH}.deb gcc-6-base_6.3.0-18_${TARGETARCH}.deb gcc-6_6.3.0-18_${TARGETARCH}.deb libasan3_6.3.0-18_${TARGETARCH}.deb libcilkrts5_6.3.0-18_${TARGETARCH}.deb libgcc-6-dev_6.3.0-18_${TARGETARCH}.deb libubsan0_6.3.0-18_${TARGETARCH}.deb libmpfr4_3.1.3-2_${TARGETARCH}.deb libisl15_0.18-1_${TARGETARCH}.deb
	\
	if [ "$TARGETARCH" = "amd64" ]; then curl -L -o libmpx0_5.5.0-12_${TARGETARCH}.deb https://download.falco.org/dependencies/libmpx0_5.5.0-12_${TARGETARCH}.deb; fi; \
	curl -L -o cpp-5_5.5.0-12_${TARGETARCH}.deb https://download.falco.org/dependencies/cpp-5_5.5.0-12_${TARGETARCH}.deb; \
	curl -L -o gcc-5-base_5.5.0-12_${TARGETARCH}.deb https://download.falco.org/dependencies/gcc-5-base_5.5.0-12_${TARGETARCH}.deb; \
	curl -L -o gcc-5_5.5.0-12_${TARGETARCH}.deb https://download.falco.org/dependencies/gcc-5_5.5.0-12_${TARGETARCH}.deb; \
	curl -L -o libasan2_5.5.0-12_${TARGETARCH}.deb	https://download.falco.org/dependencies/libasan2_5.5.0-12_${TARGETARCH}.deb; \
	curl -L -o libgcc-5-dev_5.5.0-12_${TARGETARCH}.deb https://download.falco.org/dependencies/libgcc-5-dev_5.5.0-12_${TARGETARCH}.deb; \
	curl -L -o libisl15_0.18-4_${TARGETARCH}.deb https://download.falco.org/dependencies/libisl15_0.18-4_${TARGETARCH}.deb; \
	dpkg -i cpp-5_5.5.0-12_${TARGETARCH}.deb gcc-5-base_5.5.0-12_${TARGETARCH}.deb gcc-5_5.5.0-12_${TARGETARCH}.deb libasan2_5.5.0-12_${TARGETARCH}.deb; \
	if [ "$TARGETARCH" = "amd64" ]; then dpkg -i libmpx0_5.5.0-12_${TARGETARCH}.deb; fi; \
	dpkg -i libgcc-5-dev_5.5.0-12_${TARGETARCH}.deb libisl15_0.18-4_${TARGETARCH}.deb; \
	rm -f cpp-5_5.5.0-12_${TARGETARCH}.deb gcc-5-base_5.5.0-12_${TARGETARCH}.deb gcc-5_5.5.0-12_${TARGETARCH}.deb libasan2_5.5.0-12_${TARGETARCH}.deb libgcc-5-dev_5.5.0-12_${TARGETARCH}.deb libisl15_0.18-4_${TARGETARCH}.deb libmpx0_5.5.0-12_${TARGETARCH}.deb
	\
	rm -rf /usr/bin/gcc ; ln -s /usr/bin/gcc-5 /usr/bin/gcc; \
	\
	rm -rf /usr/bin/clang; \
	rm -rf /usr/bin/llc; \
	ln -s /usr/bin/clang-7 /usr/bin/clang; \
	ln -s /usr/bin/llc-7 /usr/bin/llc;
	\
	curl -s https://falco.org/repo/falcosecurity-packages.asc | apt-key add - ; \
	echo "deb https://download.falco.org/packages/${VERSION_BUCKET} stable main" | tee -a /etc/apt/sources.list.d/falcosecurity.list; \
	apt-get update -y; \
	if [ "$FALCO_VERSION" = "latest" ]; then FALCO_DRIVER_CHOICE=none apt-get install -y --no-install-recommends falco; else FALCO_DRIVER_CHOICE=none apt-get install -y --no-install-recommends falco=${FALCO_VERSION}; fi ; \
	apt-get clean; \
	rm -rf /var/lib/apt/lists/*

ADD ../config/falco.iso8601_timeformat.yaml /etc/falco/config.d/

RUN \
	rm -df /lib/modules; \
	ln -s $HOST_ROOT/lib/modules /lib/modules; \
	if [ "$TARGETARCH" = "amd64" ] ; then \
		curl -L -o binutils-x86-64-linux-gnu_2.30-22_${TARGETARCH}.deb https://download.falco.org/dependencies/binutils-x86-64-linux-gnu_2.30-22_${TARGETARCH}.deb; \
	else  \
		curl -L -o  binutils-aarch64-linux-gnu_2.30-22_${TARGETARCH}.deb https://download.falco.org/dependencies/binutils-aarch64-linux-gnu_2.30-22_${TARGETARCH}.deb; \
	fi; \
	\
	curl -L -o binutils_2.30-22_${TARGETARCH}.deb https://download.falco.org/dependencies/binutils_2.30-22_${TARGETARCH}.deb ; \
	curl -L -o libbinutils_2.30-22_${TARGETARCH}.deb https://download.falco.org/dependencies/libbinutils_2.30-22_${TARGETARCH}.deb ; \
	curl -L -o binutils-common_2.30-22_${TARGETARCH}.deb https://download.falco.org/dependencies/binutils-common_2.30-22_${TARGETARCH}.deb ; \
	dpkg -i *binutils*.deb \
	rm -f *binutils*.deb

COPY --chmod=755 docker-entrypoint.sh /

ENTRYPOINT ["/docker-entrypoint.sh"]
