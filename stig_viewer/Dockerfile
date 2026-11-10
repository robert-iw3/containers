# A minimal runtime for DISA STIG Viewer 3, which is an Electron application.
#
# THE VIEWER IS NOT BAKED IN. It is 219 MB of vendor binary that is not ours to
# redistribute, so it is bind-mounted read-only at run time. This image carries
# only the shared libraries the binary needs, which is what keeps it small and
# what makes its contents reviewable.
#
# THE LIBRARY LIST IS MEASURED, NOT GUESSED. It comes from ldd against the
# vendor binary; see run.sh, which re-checks inside the container and reports any
# library that did not resolve rather than letting Electron fail with a blank
# window.
#
# Electron is linked against glibc, so an Alpine base will not serve regardless
# of how much smaller it is.
FROM docker.io/library/debian:stable-slim

# --no-install-recommends throughout: the recommends of a GTK stack pull a
# desktop session, which this does not need and must not have.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgtk-3-0 \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libxinerama1 \
        libxi6 \
        libxcursor1 \
        libxrender1 \
        libxres1 \
        libexpat1 \
        libseccomp2 \
        libsystemd0 \
        libasound2 \
        fonts-dejavu-core \
        fontconfig \
        xdg-utils \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# A non-root account that owns nothing. chrome-sandbox needs setuid root, which a
# rootless container cannot provide, so the viewer runs with --no-sandbox and the
# container boundary is the sandbox instead. Running as root on top of that would
# remove the only isolation left.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin viewer
USER viewer
WORKDIR /home/viewer
ENV HOME=/home/viewer \
    XDG_CONFIG_HOME=/home/viewer/.config \
    XDG_CACHE_HOME=/home/viewer/.cache \
    ELECTRON_DISABLE_SECURITY_WARNINGS=1

ENTRYPOINT ["/bin/sh"]
