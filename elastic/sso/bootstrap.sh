#!/usr/bin/env bash
# testing (not fini)
set -e

GENERATED_KEYSTORE=/usr/share/elasticsearch/config/elasticsearch.keystore
OUTPUT_KEYSTORE=/secrets/keystore/elasticsearch.keystore
GENERATED_SERVICE_TOKENS=/usr/share/elasticsearch/config/service_tokens
OUTPUT_SERVICE_TOKENS=/secrets/service_tokens
OUTPUT_KIBANA_TOKEN=/secrets/.env.kibana.token

if [ x${ELASTIC_PASSWORD} == x ]; then
  echo "Set the ELASTIC_PASSWORD environment variable in the .env file"
  exit 1
elif [ x${KIBANA_SYSTEM_PASSWORD} == x ]; then
  echo "Set the KIBANA_SYSTEM_PASSWORD environment variable in the .env file"
  exit 1
fi

elasticsearch-keystore create >> /dev/null
echo ${ELASTIC_PASSWORD} | elasticsearch-keystore add -x "bootstrap.password"

# create new kibana token
/usr/share/elasticsearch/bin/elasticsearch-service-tokens delete elastic/kibana default &> /dev/null || true
TOKEN=$(/usr/share/elasticsearch/bin/elasticsearch-service-tokens create elastic/kibana default | cut -d '=' -f2 | tr -d ' ')

echo "Kibana Service Token is: $TOKEN"
echo "KIBANA_SERVICE_ACCOUNT_TOKEN=$TOKEN" > $OUTPUT_KIBANA_TOKEN

# OIDC Service Token into keystore
if [ x${SERVICE_TOKEN} == x ]; then
  echo "Set the SERVICE_TOKEN environment variable in the .env file"
  exit 1
elif
  echo "${SERVICE_TOKEN}" \
  | bin/elasticsearch-keystore add -x \
  'xpack.security.authc.realms.oidc.$(echo ${OIDC_PROVIDER}).rp.client_secret'
fi

if [ -f "$OUTPUT_KEYSTORE" ]; then
    echo "Remove old elasticsearch.keystore"
    rm $OUTPUT_KEYSTORE
fi

echo "Saving new elasticsearch.keystore"
mkdir -p "$(dirname $OUTPUT_KEYSTORE)"
mv $GENERATED_KEYSTORE $OUTPUT_KEYSTORE
chmod 0644 $OUTPUT_KEYSTORE

if [ -f "$OUTPUT_SERVICE_TOKENS" ]; then
    echo "Remove old service_tokens file"
    rm $OUTPUT_SERVICE_TOKENS;
fi

echo "Saving new service_tokens file"
mv $GENERATED_SERVICE_TOKENS $OUTPUT_SERVICE_TOKENS
chmod 0644 $OUTPUT_SERVICE_TOKENS

printf "=====================================================\n";
printf "Your Kibana Service Token is: $TOKEN\n";
printf "=====================================================\n";

if [ ! -f certs/ca.zip ]; then
  echo "Creating CA";
  bin/elasticsearch-certutil ca --silent --pem -out config/certs/ca.zip
  unzip config/certs/ca.zip -d config/certs
fi;

if [ ! -f certs/certs.zip ]; then
  echo "Creating certs"
  echo -ne \
  "instances:\n"\
  "  - name: elasticsearch\n"\
  "    dns:\n"\
  "      - elasticsearch\n"\
  "      - localhost\n"\
  "    ip:\n"\
  "      - 127.0.0.1\n"\
  "  - name: kibana\n"\
  "    dns:\n"\
  "      - kibana\n"\
  "      - localhost\n"\
  "    ip:\n"\
  "      - 127.0.0.1\n"\
  "  - name: fleet-server\n"\
  "    dns:\n"\
  "      - fleet-server\n"\
  "      - localhost\n"\
  "    ip:\n"\
  "      - 127.0.0.1\n"\
  > config/certs/instances.yml

  bin/elasticsearch-certutil cert --silent \
    --pem -out config/certs/certs.zip \
    --in config/certs/instances.yml \
    --ca-cert config/certs/ca/ca.crt \
    --ca-key config/certs/ca/ca.key

  unzip config/certs/certs.zip -d config/certs
  cat config/certs/elasticsearch/elasticsearch.crt config/certs/ca/ca.crt > config/certs/elasticsearch/elasticsearch.chain.pem
fi

echo "Setting file permissions"
  chown -R root:root config/certs
  find . -type d -exec chmod 750 \{\} \;
  find . -type f -exec chmod 640 \{\} \;

echo "Waiting for Elasticsearch availability"
  until curl -s --cacert config/certs/ca/ca.crt https://elasticsearch:9200 \
  | grep -q "missing authentication credentials"; do sleep 30; done

echo "Setting kibana_system password"
  until curl -s -X POST --cacert config/certs/ca/ca.crt \
  -u elastic:${ELASTIC_PASSWORD} -H "Content-Type: application/json" \
  https://elasticsearch:9200/_security/user/kibana_system/_password \
  -d "{\"password\":\"${KIBANA_SYSTEM_PASSWORD}\"}" | grep -q "^{}"; do sleep 10; done

echo "All done!"