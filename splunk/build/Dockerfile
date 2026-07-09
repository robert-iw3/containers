FROM registry.access.redhat.com/ubi9/ubi-minimal as splunk_base

WORKDIR /build

COPY --chmod=755 build/packages.sh /build

RUN /build/packages.sh

COPY --chmod=755 build/busybox.sh /build

RUN /build/busybox.sh

COPY --chmod=755 build/python.sh /build

RUN /build/python.sh

COPY --chmod=755 build/base_cleanup.sh /build

RUN build/base_cleanup.sh

FROM splunk_base as package

ARG SPLUNK_BUILD_URL

COPY common-files/make-minimal-exclude.py /tmp

COPY --chmod=755 build/download.sh /build

RUN /build/download.sh

COPY common-files/apps /extras/splunk-etc/apps/

FROM splunk_base as final

COPY --chmod=755 common-files/updateetc.sh /sbin

COPY --chmod=755 build/user.sh /build

RUN /build/user.sh

COPY --from=package --chown=splunk:splunk /minimal /opt

FROM final

ARG SPLUNK_DEFAULTS_URL

ENV SPLUNK_HOME=/opt/splunkforwarder \
    TMPSPLUNKDIR=${SPLUNK_HOME}/tmp \
    TMPETCDIR=${TMPSPLUNKDIR}/etc \
    SPLUNK_ROLE=splunk_standalone \
    SPLUNK_DEFAULTS_URL=${SPLUNK_DEFAULTS_URL}

COPY --chmod=755 common-files/entrypoint.sh /sbin
COPY --chmod=755 common-files/createdefaults.py /sbin
COPY --chmod=755 common-files/checkstate.sh /sbin
COPY --chmod=755 build/ansible.sh /build
COPY --chmod=755 build/el9-container-hardening.sh /build
COPY --chmod=755 build/scap_av.sh /build

RUN /build/ansible.sh
RUN /build/el9-container-hardening.sh

ARG SUBSCRIPTION_USER
ARG SUBSCRIPTION_PASS

# if building container from rhel host os, with subscription activated, pass following volume mounts to container runtime
# podman run --rm -it \
#  -v "$PWD/entitlement:/run/secrets/etc-pki-entitlement" \
#  -v "$PWD/rhsm:/run/secrets/rhsm" \
#  -v "$PWD/redhat.repo:/run/secrets/redhat.repo" \
#  -d splunk

RUN \
    sed -i 's/\(def in_container():\)/\1\n    return False/g' /usr/lib64/python*/*-packages/rhsm/config.py; \
    subscription-manager register --username "${SUBSCRIPTION_USER}" --password "${SUBSCRIPTION_PASS}" --auto-attach

RUN /build/scap_av.sh

EXPOSE 8000 8065 8088 8089 8191 9887 9997
VOLUME [ "/opt/splunk/etc", "/opt/splunk/var" ]
USER ansible
WORKDIR /opt/ansible
HEALTHCHECK --interval=30s --timeout=30s --start-period=3m --retries=5 CMD /sbin/checkstate.sh || exit 1
ENTRYPOINT [ "/sbin/entrypoint.sh" ]
CMD [ "start-service" ]