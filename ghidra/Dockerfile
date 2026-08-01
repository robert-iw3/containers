## build
FROM docker.io/gradle:jdk21 AS builder

RUN \
    apt-get update ; \
    apt-get install -y \
        curl \
        git \
        bison \
        flex \
        build-essential \
        unzip

ENV VERSION=12.1.2_PUBLIC
ENV GHIDRA_SHA=b62e81a0390618466c019c60d8c2f796ced2509c4c1aea4a37644a77272cf99d
ENV GHIDRA_URL=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.2_build/ghidra_12.1.2_PUBLIC_20260605.zip

RUN \
    apt-get update ; \
    apt-get install -y \
        fontconfig \
        libxrender1 \
        libxtst6 \
        libxi6 \
        wget \
        unzip \
        python3-requests --no-install-recommends ; \
    wget --progress=bar:force -O /tmp/ghidra.zip ${GHIDRA_URL} ; \
    echo "$GHIDRA_SHA /tmp/ghidra.zip" | sha256sum -c - ; \
    unzip /tmp/ghidra.zip ; \
    mv ghidra_${VERSION} /ghidra ; \
    chmod +x /ghidra/ghidraRun ; \
    echo "===> Clean up unnecessary files..." ; \
    apt-get purge -y --auto-remove wget unzip ; \
    apt-get clean ; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives /tmp/* /var/tmp/* /ghidra/docs /ghidra/Extensions/Eclipse /ghidra/licenses

WORKDIR /ghidra/support/gradle/

RUN gradle buildNatives

## runtime
FROM docker.io/alpine:3.24

RUN \
    apk add --no-cache openjdk21-jdk bash ; \
    apk add --no-cache fontconfig ttf-dejavu ; \
    apk add --no-cache -t .build-deps ca-certificates

COPY --from=builder /ghidra /ghidra
RUN \
    chmod +x /ghidra/ghidraRun  ; \
    echo "===> Clean up unnecessary files..." ; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives /tmp/* /var/tmp/* ; \
    rm -rf /ghidra/docs ; \
    rm -rf /ghidra/licenses ; \
    rm -rf /ghidra/Extensions/Ghidra ; \
    rm -rf /ghidra/Extensions/Eclipse ; \
    find /ghidra -type f -name "*src*.zip" -exec rm -f {} \; ; \
    apk del --purge .build-deps

# Pin the JDK path in Ghidra's own launcher config.
#
# The launcher searches for a JDK, and on not finding one it accepts it prompts for the path.
# It also SAVES the resolved path under the user's home and treats a home it cannot write to as
# "no JDK found", so a read-only or root-owned home turns into the same prompt. Recording the
# path here removes the search, and putting it in launch.properties rather than ~/.ghidra means
# it survives a container that mounts a fresh home over the built-in one.
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk
# The shipped file already contains an EMPTY `JAVA_HOME_OVERRIDE=` line. Appending a second one
# leaves two directives and makes the effective value depend on whether the launcher reads the
# first or the last — and the build's headless smoke test cannot tell the difference, because at
# build time /root is writable and the JDK search succeeds on its own. So the existing line is
# REPLACED and the result asserted: exactly one directive, carrying the path.
RUN set -eu; \
    test -x "${JAVA_HOME}/bin/java"; \
    sed -i "s|^JAVA_HOME_OVERRIDE=.*|JAVA_HOME_OVERRIDE=${JAVA_HOME}|" \
        /ghidra/support/launch.properties; \
    grep -q "^JAVA_HOME_OVERRIDE=${JAVA_HOME}$" /ghidra/support/launch.properties \
      || { echo "JAVA_HOME_OVERRIDE was not set" >&2; exit 1; }; \
    test "$(grep -c '^JAVA_HOME_OVERRIDE=' /ghidra/support/launch.properties)" -eq 1 \
      || { echo "more than one JAVA_HOME_OVERRIDE directive — the effective value is ambiguous" >&2; exit 1; }

# Prove the launcher runs, not just that its files are present.
#
# Checking that the decompiler native exists passes on an image whose Java is too old to start
# Ghidra at all — nothing reaches that binary except through the launcher. Importing a file with
# analyzeHeadless exercises the path a real invocation takes, so a wrong JDK, a native built for
# the wrong libc, or an unusable loader fails the build instead of the first analysis.
RUN set -eu; \
    tmp="$(mktemp -d)"; \
    head -c 4096 /dev/urandom > "${tmp}/smoke.bin"; \
    /ghidra/support/analyzeHeadless "${tmp}" smoke \
        -import "${tmp}/smoke.bin" \
        -processor x86:LE:64:default \
        -loader BinaryLoader -loader-baseAddr 0x400000 \
        -noanalysis > "${tmp}/out.log" 2>&1 \
      || { echo "analyzeHeadless failed to import:" >&2; tail -20 "${tmp}/out.log" >&2; exit 1; }; \
    test -f "${tmp}/smoke.gpr" \
      || { echo "no project created despite a successful import" >&2; exit 1; }; \
    echo "ghidra headless import OK"; rm -rf "${tmp}"

# Prove the GUI toolkit can initialise, not only the headless path.
#
# `analyzeHeadless` succeeding says nothing about whether a window can open: it never touches
# AWT. A missing X client library or absent fontconfig leaves an image where every build check
# passes and `client` mode dies on first launch, reporting a font or display error that reads as
# a problem with the host's X server rather than with this image.
RUN set -eu; \
    test -f "${JAVA_HOME}/lib/libawt_xawt.so" \
      || { echo "no libawt_xawt.so — this JDK cannot open a GUI at any DISPLAY" >&2; exit 1; }; \
    fc-list >/dev/null 2>&1 \
      || { echo "fontconfig unusable — Swing cannot initialise its font subsystem" >&2; exit 1; }; \
    test "$(fc-list 2>/dev/null | wc -l)" -gt 0 \
      || { echo "no fonts installed — the GUI renders nothing legible" >&2; exit 1; }; \
    tmp="$(mktemp -d)"; cd "${tmp}"; \
    printf 'public class G { public static void main(String[] a) throws Exception {\n' > G.java; \
    printf '  System.loadLibrary("awt_xawt");\n' >> G.java; \
    printf '  System.out.println("awt ok"); } }\n' >> G.java; \
    "${JAVA_HOME}/bin/javac" G.java && "${JAVA_HOME}/bin/java" G \
      || { echo "AWT X11 support failed to load" >&2; exit 1; }; \
    cd /; rm -rf "${tmp}"; \
    echo "ghidra GUI toolkit OK"

WORKDIR /ghidra

COPY entrypoint.sh /entrypoint.sh
COPY server.conf /ghidra/server/server.conf

EXPOSE 13100 13101 13102
RUN mkdir /repos
ENTRYPOINT ["/entrypoint.sh"]
CMD [ "client" ]