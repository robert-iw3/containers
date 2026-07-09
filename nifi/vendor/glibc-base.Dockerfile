FROM docker.io/debian:13-slim as glibc-base

ARG GLIBC_VERSION=2.36
ARG GLIBC_PREFIX=/usr/glibc
ARG LANG=en_US.UTF-8

RUN \
    apt-get update ; \
    apt-get install -y \
        curl \
        build-essential \
        gawk \
        bison \
        python3 \
        texinfo \
        gettext; \
    cd /root; \
    curl -SL http://ftp.gnu.org/gnu/glibc/glibc-${GLIBC_VERSION}.tar.gz | tar xzf - ;\
    mkdir -p /root/build ;\
    cd /root/build ;\
    ../glibc-${GLIBC_VERSION}/configure \
          --prefix=${GLIBC_PREFIX} \
          --libdir="${GLIBC_PREFIX}/lib" \
          --libexecdir="${GLIBC_PREFIX}/lib" \
          --enable-multi-arch \
          --enable-stack-protector=strong ;\
    make -j`nproc` ;\
    make DESTDIR=/root/dest install ;\
    RTLD=`find /root/dest${GLIBC_PREFIX}/lib -name 'ld-linux-*.so.*'` ;\
    [ -x "$RTLD" ] ;\
    LOCALEDEF="$RTLD --library-path /root/dest${GLIBC_PREFIX}/lib /root/dest${GLIBC_PREFIX}/bin/localedef --alias-file=/root/glibc-${GLIBC_VERSION}/intl/locale.alias" ;\
    export I18NPATH=/root/glibc-${GLIBC_VERSION}/localedata ;\
    export GCONVPATH=/root/glibc-${GLIBC_VERSION}/iconvdata ;\
    LOCALE=$(echo ${LANG} | cut -d. -f1) ;\
    CHARMAP=$(echo ${LANG} | cut -d. -f2) ;\
    mkdir -pv /root/dest${GLIBC_PREFIX}/lib/locale ;\
    cd /root/glibc-${GLIBC_VERSION}/localedata ;\
    ${LOCALEDEF} -i locales/$LOCALE -f charmaps/$CHARMAP --prefix=/root/dest $LANG ;\
    cd /root ;\
    rm -rf build glibc-${GLIBC_VERSION} ;\
    cd /root/dest${GLIBC_PREFIX} ;\
    ( strip bin/* sbin/* lib/* || true ) ;\
    echo "/usr/local/lib" > /root/dest${GLIBC_PREFIX}/etc/ld.so.conf ;\
    echo "${GLIBC_PREFIX}/lib" >> /root/dest${GLIBC_PREFIX}/etc/ld.so.conf ;\
    echo "/usr/lib" >> /root/dest${GLIBC_PREFIX}/etc/ld.so.conf ;\
    echo "/lib" >> /root/dest${GLIBC_PREFIX}/etc/ld.so.conf; \
    cd /root/dest${GLIBC_PREFIX} ; \
    rm -rf etc/rpc var include share bin "sbin/[^l]*"  \
	    lib/*.o lib/*.a lib/audit lib/gconv lib/getconf
