# Backup runner for the Gitea stack: PostgreSQL client tools plus the extra
# utilities backup.sh needs — gpg for symmetric encryption and the AWS CLI
# for the MinIO (S3) upload. Built from the official postgres image (Debian,
# so bash and pg_dump are present); backup.sh is mounted in at run time.
FROM docker.io/postgres:17.10-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gnupg \
        awscli \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*
