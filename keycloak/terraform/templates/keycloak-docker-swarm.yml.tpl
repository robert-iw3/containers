version: '3.9'

x-default-opts:
  &default-opts
  logging:
    options:
      max-size: "10m"

networks:
  keycloak-network:
    driver: overlay

services:
  keycloak:
    <<: *default-opts
    image: quay.io/keycloak/keycloak:${image_tag}
    command: start
    environment:
      KC_DB: postgres
      KC_DB_URL_HOST: ${db_host}
      KC_DB_URL_DATABASE: ${db_name}
      KC_DB_USERNAME: ${db_username}
      KC_DB_PASSWORD: ${db_password}
      KC_DB_SCHEMA: public
      KEYCLOAK_ADMIN: ${admin_user}
      KEYCLOAK_ADMIN_PASSWORD: ${admin_user_password}
      KC_HEALTH_ENABLED: 'true'
      KC_HOSTNAME: ${trusted_domain}
      KC_HTTP_ENABLED: 'true'
      KC_PROXY_HEADERS: 'xforwarded'
      PROXY_ADDRESS_FORWARDING: 'true'
    networks:
      - keycloak-network
    ports:
      - "8080:8080"
      - "9000:9000"
    healthcheck:
      test:
      - "CMD-SHELL"
      - |
        exec 3<>/dev/tcp/localhost/9000 &&
        echo -e 'GET /health/ready HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' >&3 &&
        cat <&3 | tee /tmp/healthcheck.log | grep -q '200 OK'
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 90s
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      resources:
        limits:
          cpus: '1.55'
          memory: 6G
        reservations:
          cpus: '0.55'
          memory: 2G
