#!/bin/sh -e

prop_replace 'nifi.security.user.oidc.discovery.url'                    "${NIFI_SECURITY_USER_OIDC_DISCOVERY_URL}"
prop_replace 'nifi.security.user.oidc.connect.timeout'                  "${NIFI_SECURITY_USER_OIDC_CONNECT_TIMEOUT}"
prop_replace 'nifi.security.user.oidc.read.timeout'                     "${NIFI_SECURITY_USER_OIDC_READ_TIMEOUT}"
prop_replace 'nifi.security.user.oidc.client.id'                        "${NIFI_SECURITY_USER_OIDC_CLIENT_ID}"
prop_replace 'nifi.security.user.oidc.client.secret'                    "${NIFI_SECURITY_USER_OIDC_CLIENT_SECRET}"
prop_replace 'nifi.security.user.oidc.preferred.jwsalgorithm'           "${NIFI_SECURITY_USER_OIDC_PREFERRED_JWSALGORITHM}"
prop_replace 'nifi.security.user.oidc.additional.scopes'                "${NIFI_SECURITY_USER_OIDC_ADDITIONAL_SCOPES}"
prop_replace 'nifi.security.user.oidc.claim.identifying.user'           "${NIFI_SECURITY_USER_OIDC_CLAIM_IDENTIFYING_USER}"
prop_replace 'nifi.security.user.oidc.claim.groups'                     "${NIFI_SECURITY_USER_OIDC_CLAIM_GROUPS}"
prop_replace 'nifi.security.user.oidc.fallback.claims.identifying.user' "${NIFI_SECURITY_USER_OIDC_FALLBACK_CLAIMS_IDENTIFYING_USER}"
prop_replace 'nifi.security.user.oidc.truststore.strategy'              "${NIFI_SECURITY_USER_OIDC_TRUSTSTORE_STRATEGY}"
prop_replace 'nifi.security.user.oidc.token.refresh.window'             "${NIFI_SECURITY_USER_OIDC_TOKEN_REFRESH_WINDOW}"
