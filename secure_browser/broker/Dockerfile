# Network broker for the secure travel browser — the ONLY thing the browser
# container can reach. It owns the entire path off the machine:
#
#   browser (internal net, no routes) --SOCKS5--> broker --[filtered DoH DNS,
#   optional WireGuard]--> pasta pinned to the wifi adapter --> hostile LAN
#
# Components:
#   * dante (sockd): SOCKS5 choke point with connect/disconnect logging — every flow
#     leaving the browser is brokered and visible here.
#   * dnscrypt-proxy: DNS-over-HTTPS to Quad9/Cloudflare-security with a
#     StevenBlack-derived blocklist baked at build time — name resolution never
#     touches the hotel resolver, and known ad/malware domains die at the broker
#     (compensating for the browser's no-add-ons STIG policy: no uBlock).
#   * wireguard (optional, bring-your-own endpoint): when a wg0.conf is mounted, ALL
#     egress is routed through the tunnel and the entrypoint refuses to serve if the
#     handshake fails — fail closed, never leak to the hostile LAN.
FROM docker.io/library/alpine:3.24

RUN apk add --no-cache \
        dante-server dnscrypt-proxy \
        wireguard-tools-wg iproute2 drill \
        ca-certificates

# Domain blocklist baked at build time (image rebuilds refresh it). Build fails if
# the list looks broken — a silently-empty blocklist would un-harden DNS.
ADD https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts /tmp/hosts
RUN awk '$1 == "0.0.0.0" && $2 != "0.0.0.0" {print $2}' /tmp/hosts | sort -u \
        > /etc/dnscrypt-proxy/blocked-names.txt \
    && rm /tmp/hosts \
    && count=$(wc -l < /etc/dnscrypt-proxy/blocked-names.txt) \
    && [ "$count" -gt 10000 ] \
    && [ "$(grep -c '^doubleclick\.net$' /etc/dnscrypt-proxy/blocked-names.txt)" -ge 1 ] \
    && echo "blocklist OK (${count} domains)"

COPY dnscrypt-proxy.toml /etc/dnscrypt-proxy/dnscrypt-proxy.toml
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# Build-time smoke test: config must parse, or DNS filtering silently never starts.
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && dnscrypt-proxy -check -config /etc/dnscrypt-proxy/dnscrypt-proxy.toml

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
