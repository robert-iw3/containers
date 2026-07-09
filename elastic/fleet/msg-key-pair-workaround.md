## Environment

Self-managed deployment.

## Cause

Kibana can only decrypt saved objects if the original encryption key is available.
Workaround

> [!NOTE]
> Before starting this workaround, check if tamper protection is enabled on the Agent policy and whether Elastic Defend integration is used.
>
> Check out this guide for more info.
>
> https://www.elastic.co/guide/en/security/current/agent-tamper-protection.html

Create a superuser to be able to delete kibana saved objects manually (run in Kibana console)

```yaml
POST _security/role/fleet_superuser
 {
    "indices": [
        {
            "names": [".fleet*",".kibana*"],
            "privileges": ["all"],
            "allow_restricted_indices": true
        }
    ]
  }

POST _security/user/fleet_superuser
 {
    "password": "password",
    "roles": ["superuser", "fleet_superuser"]
  }
```

Delete message singing key SO

```yaml
// query and save the original message signing key
GET .kibana_ingest/_search?q=type:fleet-message-signing-keys

// delete
curl -sk -XPOST --user fleet_superuser:password -H 'content-type:application/json' \
    -H'x-elastic-product-origin:fleet' \
   https://ES_HOST:PORT/.kibana_ingest/_delete_by_query \
   -d '{
    "query": {
      "bool": {"filter": [
        {"match": {"type": "fleet-message-signing-keys"}}
      ]}
    }
  }'
```

Delete uninstall token SOs

```yaml
// query and save the original uninstall tokens
GET .kibana_ingest/_search?q=type:fleet-uninstall-tokens

// delete them
curl -sk -XPOST --user fleet_superuser:password -H 'content-type:application/json' \
    -H'x-elastic-product-origin:fleet' \
   https://ES_HOST:PORT/.kibana_ingest/_delete_by_query \
   -d '{
    "query": {
      "bool": {"filter": [
        {"match": {"type": "fleet-uninstall-tokens"}}
      ]}
    }
  }'
```

Restart kibana (this is needed to regenerate the uninstall tokens)

Verify that there are no more decrypt or message signing key errors

Verify that the uninstall tokens and message signing key is regenerated

```yaml
GET .kibana_ingest/_search?q=type:fleet-uninstall-tokens
GET .kibana_ingest/_search?q=type:fleet-message-signing-keys
```

Verify that the latest agent policy revision is created in .fleet-policies and sent to agents.

```yaml
GET .kibana_ingest/_doc/ingest-agent-policies:<policy_id>

// revision_idx should match the revision of the SO above
GET .fleet-policies/_search?q=policy_id:<policy_id>
{
  "size": 1,
  "sort": [
    {
      "revision_idx": {
        "order": "desc"
      }
    }
  ]
}
```

Delete the superuser role and user

```yaml
DELETE _security/user/fleet_superuser
DELETE _security/role/fleet_superuser
```

If Elastic Defend is used, reinstall is needed:

Remove Elastic Defend integration, which will uninstall all Endpoints (wait for a while to confirm all are gone), then add the integration again

If tamper protection is enabled, reinstall of agents is needed too. For this, you need the original uninstall tokens used to install the agents.

Unenroll the agents with the uninstall tokens

Enroll the agents again
