#!/bin/bash
aws s3 ls s3://bucket/nifi-backup-$(date +%Y%m%d).tar.gz || {
    echo 'Backup for $(date +%Y%m%d) not found!' | mail -s 'NiFi Backup Failure' admin@example.com
}