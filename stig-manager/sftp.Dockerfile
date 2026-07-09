FROM docker.io/alpine:latest

RUN apk update && \
    apk add --no-cache openssh-server shadow && \
    rm -rf /var/cache/apk/*

# Create SFTP user and group (configurable via env)
ENV SFTP_USER=sftpuser \
    SFTP_PASSWORD=changeme \
    SFTP_CHROOT_DIR=/upload

# Setup SSHD config for SFTP-only
RUN echo "PermitRootLogin no" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "Subsystem sftp internal-sftp" >> /etc/ssh/sshd_config && \
    echo "Match User \$SFTP_USER" >> /etc/ssh/sshd_config && \
    echo "    ChrootDirectory \$SFTP_CHROOT_DIR" >> /etc/ssh/sshd_config && \
    echo "    ForceCommand internal-sftp" >> /etc/ssh/sshd_config && \
    echo "    AllowTcpForwarding no" >> /etc/ssh/sshd_config && \
    echo "    X11Forwarding no" >> /etc/ssh/sshd_config

# Entry point script to create user and start SSHD
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose SSH port
EXPOSE 22

# Volume for upload (chroot dir)
VOLUME ["/upload"]

# Run as non-root if possible, but SSHD needs root for chroot
ENTRYPOINT ["/entrypoint.sh"]