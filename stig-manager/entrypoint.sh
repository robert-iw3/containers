#!/bin/sh

# Create group and user if not exists
addgroup -g 1001 sftpgroup
adduser -D -G sftpgroup -h $SFTP_CHROOT_DIR -s /bin/false $SFTP_USER

# Set password (from env)
echo "$SFTP_USER:$SFTP_PASSWORD" | chpasswd

# Setup chroot dir permissions (must be owned by root)
mkdir -p $SFTP_CHROOT_DIR
chown root:root $SFTP_CHROOT_DIR
chmod 755 $SFTP_CHROOT_DIR

# Generate host keys if not present
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key -N ''
fi
if [ ! -f /etc/ssh/ssh_host_ecdsa_key ]; then
    ssh-keygen -t ecdsa -f /etc/ssh/ssh_host_ecdsa_key -N ''
fi
if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
    ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N ''
fi

# Start SSHD
exec /usr/sbin/sshd -D -e