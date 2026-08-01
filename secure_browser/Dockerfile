# Secure travel browser — an isolated Firefox for browsing from untrusted networks
# (hotel/airport wifi) with no path onto the host filesystem.
#
# Security posture (layered — each holds even if another fails):
#   * NETWORK: egress goes through pasta bound to the host's WIRELESS adapter only
#     (auto-detected by run.sh), with the container→host gateway mapping disabled —
#     the container cannot reach services listening on the host.
#   * DISK: the container runs with a read-only root filesystem; the profile,
#     downloads, /tmp and shm are tmpfs, destroyed on exit. No host path is mounted
#     writable, so nothing the browser touches can land on the host machine.
#   * BROWSER: DISA Mozilla Firefox STIG-aligned enterprise policy (policies.json) —
#     no add-ons, no telemetry, no password manager/autofill, no sync, no dev tools,
#     TLS 1.2 floor, pop-ups blocked, sanitize on shutdown — plus hostile-LAN
#     hardening: HTTPS-Only mode and DoH pinned to Quad9 (see policies.json comments).
#
# Rendering: the host's Wayland socket (or X11 socket as fallback) is bind-mounted so
# the window appears on the desktop while the process stays contained.
FROM docker.io/library/alpine:3.24

# firefox-esr = the ESR channel the STIG targets. The rest are the Wayland/X11/font
# runtime bits Firefox needs to render through a bind-mounted display socket.
RUN apk add --no-cache \
        firefox-esr \
        ttf-dejavu font-noto font-noto-emoji \
        dbus-x11 xauth \
        mesa-gl mesa-egl mesa-dri-gallium libpciaccess \
        ca-certificates python3 \
    && mkdir -p /usr/lib/firefox-esr/distribution /etc/firefox/policies

# Enterprise policy (machine-wide, not user-overridable). Installed to both paths
# Firefox reads so the controls apply regardless of build layout.
COPY policies.json /usr/lib/firefox-esr/distribution/policies.json
COPY policies.json /etc/firefox/policies/policies.json
COPY launch.sh /usr/local/bin/launch.sh
RUN chmod +x /usr/local/bin/launch.sh

# Build-time smoke test: firefox present and the policy is valid JSON with the
# hostile-LAN controls — a malformed policy would silently un-harden the browser.
RUN firefox-esr --version \
    && python3 -c "\
import json; p = json.load(open('/usr/lib/firefox-esr/distribution/policies.json'))['policies']; \
assert p['InstallAddonsPermission']['Default'] is False, 'add-on installs not blocked'; \
assert p['DisableTelemetry'] is True, 'telemetry not disabled'; \
assert p['PasswordManagerEnabled'] is False, 'password manager not disabled'; \
assert p['DisableDeveloperTools'] is True, 'dev tools not disabled'; \
assert p['DNSOverHTTPS']['Enabled'] is True and 'quad9' in p['DNSOverHTTPS']['ProviderURL'], 'DoH not pinned to trusted resolver'; \
assert p['Preferences']['dom.security.https_only_mode']['Value'] is True, 'HTTPS-Only mode off'; \
assert p['Preferences']['media.peerconnection.enabled']['Value'] is False, 'WebRTC not disabled'; \
assert p['Preferences']['browser.cache.disk.enable']['Value'] is False, 'disk cache not disabled'; \
assert p['Preferences']['security.tls.version.min']['Value'] >= 3, 'TLS floor below 1.2'; \
assert p['Preferences']['browser.download.dir']['Value'].startswith('/home/browser'), 'download dir not contained'; \
assert p['SanitizeOnShutdown']['Cache'] is True, 'sanitize-on-shutdown off'; \
print('firefox STIG policy OK')"

# Runs as container-root, which under ROOTLESS podman maps to the invoking
# unprivileged host user — it is not host root, and it is what lets the process open
# the bind-mounted display socket. Privilege is still stripped at run time:
# cap_drop ALL + no-new-privileges + read-only rootfs (see run.sh).
ENV HOME=/home/browser
RUN mkdir -p /home/browser

ENTRYPOINT ["/usr/local/bin/launch.sh"]
