source /.env

# replicate to local
replicate_s3()
{
    /usr/bin/mc config host add minio ${MINIO_ENDPOINT} ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}
    /usr/bin/mc config host add aws-s3 ${AWS_ENDPOINT} ${AWS_ACCESS_KEY_ID} ${AWS_SECRET_ACCESS_KEY}
    /usr/bin/mc batch generate minio/ replicate > replication.yaml
    /usr/bin/mc batch start minio/ ./replication.yaml
    /usr/bin/mc diff aws-s3/${AWS_BUCKET} minio/${AWS_BUCKET}
}

<<comment
create and set (commands to test later)
#
/usr/bin/mc rm -r --force aws-s3/${AWS_BUCKET}
#
make_bucket()
    {
    /usr/bin/mc mb -p aws-s3/${AWS_BUCKET}
    /usr/bin/mc policy set download aws-s3/${AWS_BUCKET}
    /usr/bin/mc anonymous set upload aws-s3/${AWS_BUCKET}
    /usr/bin/mc anonymous set download aws-s3/${AWS_BUCKET}
    }
#
# Configure User Accounts and Policies for Lifecycle Management
cycle_mgmt()
    {
    wget -O - https://min.io/docs/minio/linux/examples/LifecycleManagementAdmin.json | \
    /usr/bin/mc admin policy create Alpha LifecycleAdminPolicy /dev/stdin
    echo "$(openssl rand -base64 64)" | /usr/bin/mc admin user add Alpha alphaLifecycleAdmin
    /usr/bin/mc admin policy attach Alpha LifecycleAdminPolicy --user=alphaLifecycleAdmin
    }
#
# Configure the Remote Storage Tier
config_remote()
    {
    /usr/bin/mc ilm tier add s3 minio s3-tier \
        --endpoint ${AWS_ENDPOINT} \
        --access-key ${AWS_ACCESS_KEY_ID} \
        --secret-key ${AWS_SECRET_ACCESS_KEY} \
        --bucket ${AWS_BUCKET} \
        --storage-class Standard-IA \
        --region us-west-1
    }
#
# Create and Apply the Transition Rule
apply_rule()
    {
    /usr/bin/mc ilm rule add minio/${AWS_BUCKET} \
        --transition-tier s3-tier \
        --transition-days 30 \
        --noncurrent-transition-days 90 \
        --noncurrent-transition-tier s3-tier
    }

mc ilm rule ls minio/${AWS_BUCKET} --transition

# \
comment

replicate_s3