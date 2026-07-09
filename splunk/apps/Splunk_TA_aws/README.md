# Patches for [Splunk_TA_aws](https://splunkbase.splunk.com/app/1876)

- Add a new sourcetype aws:firehose:waf
  - Map fields to [Web data model](https://docs.splunk.com/Documentation/CIM/5.3.2/User/Web)
  - [Example stack](https://gitlab.com/curben/aws-scripts/-/tree/main/waf-firehose-splunk).
- Add a new sourcetype aws:firehose:cloudtrail
  - Firehose sends a bundle of Cloudtrail events that need to be sliced into separate events using [`LINE_BREAKER`](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Propsconf).
  - The sourcetype is then restored to aws:cloudtrail during search-time to utilise existing field extractions and CIM mapping.
  - [Example stack](https://gitlab.com/curben/aws-scripts/-/tree/main/cloudtrail-firehose-splunk).

## Cloudtrail event

Firehose sends a bundle of the following events without whitespace. `tlsDetails` may not exist in some events.

```json
{
  "version": "0",
  "id": "uuid",
  "detail-type": "AWS API Call via CloudTrail",
  "source": "aws.sts",
  "account": "111111111111",
  "time": "2024-01-02T12:34:56Z",
  "region": "us-east-1",
  "resources": [],
  "detail": {
    "eventVersion": "1.08",
    "userIdentity": {
      "type": "AssumedRole",
      "principalId": "AROAVXF7D5K4U11TPRL57:example@example.com",
      "arn": "arn:aws:sts::111111111111:assumed-role/AWSReservedSSO_AmazonS3ReadOnlyAccess_8jndlndseu21jqn5/example@example.com",
      "accountId": "111111111111",
      "accessKeyId": "ASIAPONVPLPDAYRE495Z",
      "sessionContext": {
        "sessionIssuer": {
          "type": "Role",
          "principalId": "AROAVXF7D5K4U11TPRL57",
          "arn": "arn:aws:sts::111111111111:assumed-role/AWSReservedSSO_AmazonS3ReadOnlyAccess_8jndlndseu21jqn5/",
          "accountId": "111111111111",
          "userName": "AWSReservedSSO_AmazonS3ReadOnlyAccess_8jndlndseu21jqn5"
        },
        "webIdFederationData": {},
        "attributes": {
          "creationDate": "2024-01-02T12:34:55Z",
          "mfaAuthenticated": "false"
        }
      }
    },
    "eventTime": "2024-01-02T12:34:56Z",
    "eventSource": "sts.amazonaws.com",
    "eventName": "GetCallerIdentity",
    "awsRegion": "us-east-1",
    "sourceIPAddress": "1.2.3.4",
    "userAgent": "aws-sdk-nodejs/2.1586.0 linux/v20.15.1 aws-cdk/2.135.0 promise",
    "requestParameters": null,
    "responseElements": null,
    "requestID": "uuid",
    "eventID": "uuid",
    "readOnly": true,
    "eventType": "AwsApiCall",
    "managementEvent": true,
    "recipientAccountId": "111111111111",
    "eventCategory": "Management",
    "tlsDetails": {
      "tlsVersion": "TLSv1.3",
      "cipherSuite": "TLS_AES_128_GCM_SHA256",
      "clientProvidedHostHeader": "sts.us-east-1.amazonaws.com"
    }
  }
}
{
  "another": "event"
}
{
  "another": "event"
}
```

### Processed event

`detail` object may have `resources` key, so top-level `"resources": []` is removed to avoid conflict. Every objects of `detail` are moved to parent.

```json
{
  "version": "0",
  "id": "uuid",
  "detail-type": "AWS API Call via CloudTrail",
  "source": "aws.sts",
  "account": "111111111111",
  "time": "2024-01-02T12:34:56Z",
  "region": "us-east-1",
  "eventVersion": "1.08",
  "userIdentity": {
    "type": "AssumedRole",
    "principalId": "AROAVXF7D5K4U11TPRL57:example@example.com",
    "arn": "arn:aws:sts::111111111111:assumed-role/AWSReservedSSO_AmazonS3ReadOnlyAccess_8jndlndseu21jqn5/example@example.com",
    "accountId": "111111111111",
    "accessKeyId": "ASIAPONVPLPDAYRE495Z",
    "sessionContext": {
      "sessionIssuer": {
        "type": "Role",
        "principalId": "AROAVXF7D5K4U11TPRL57",
        "arn": "arn:aws:sts::111111111111:assumed-role/AWSReservedSSO_AmazonS3ReadOnlyAccess_8jndlndseu21jqn5/",
        "accountId": "111111111111",
        "userName": "AWSReservedSSO_AmazonS3ReadOnlyAccess_8jndlndseu21jqn5"
      },
      "webIdFederationData": {},
      "attributes": {
        "creationDate": "2024-01-02T12:34:55Z",
        "mfaAuthenticated": "false"
      }
    }
  },
  "eventTime": "2024-01-02T12:34:56Z",
  "eventSource": "sts.amazonaws.com",
  "eventName": "GetCallerIdentity",
  "awsRegion": "us-east-1",
  "sourceIPAddress": "1.2.3.4",
  "userAgent": "aws-sdk-nodejs/2.1586.0 linux/v20.15.1 aws-cdk/2.135.0 promise",
  "requestParameters": null,
  "responseElements": null,
  "requestID": "uuid",
  "eventID": "uuid",
  "readOnly": true,
  "eventType": "AwsApiCall",
  "managementEvent": true,
  "recipientAccountId": "111111111111",
  "eventCategory": "Management",
  "tlsDetails": {
    "tlsVersion": "TLSv1.3",
    "cipherSuite": "TLS_AES_128_GCM_SHA256",
    "clientProvidedHostHeader": "sts.us-east-1.amazonaws.com"
  }
}
```
