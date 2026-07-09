# acm-certificate

Provides an ACM Certificate resource

Example Usage
-----------------

### Route53 Hosted Domain

This configuration creates an ACM certificate for `bar.example.com` with `foo.example.com` as a subject
alternative name (SAN). This example will automatically create DNS validation records in the example.com
Route53 zone.

```hcl
module "route53" {
    source = "git@github.com:techservicesillinois/terraform-aws-acm-certificate"

    domain   = "example.com"
    hostname = "bar"

    subject_alternative_names = [
      "foo.some.domain.name"
    ]

}
```

### Domain not hosted by Route53

This configuration creates an ACM certificate for `authman.example.org` with `authbot.example.org` as a subject
alternative name (SAN). This example requires manual creation of DNS records for certificate validations.

```hcl
module "not_route53" {
    source = "git@github.com:techservicesillinois/terraform-aws-acm-certificate"

    domain   = "example.org"
    hostname = "foo"

    subject_alternative_names = [
      "bar.some.domain.name"
    ]

   skip_route53_validation = true
}
```

Argument Reference
-----------------

The following arguments are supported:

* `domain` - (Required) Domain name of the certificate.

* `hostname` - (Required) Hostname of the certificate.

* `validation_method` - Which method to use for validation. DNS or EMAIL are valid, NONE can be used for certificates that were imported into ACM and then into Terraform.

* `subject_alternative_names` - A list of domains that should be SANs in the issued certificate

* `skip_route53_validation` - Set to true to disable Route53 domain validation record creation. This is useful for zones not hosted in Route53 (Default is false).

* `create_route53_record` - Create Route53 record if true. Set to false if Route53 record already exists (Default is true).

* `tags` - A mapping of tags.

Attributes Reference
--------------------

The following attributes are exported:

* `arn` - The ARN of the certificate
* `domain_validation_options ` - A list of attributes to used to complete certificate validation

Import
--------------------

A certificate can be imported using its ARN:

```
terraform import aws_acm_certificate.default arn:aws:acm:us-east2-1:123456789012:certificate/7e7a28d2-163f-4b8f-b9cd-822f96c08d6a
```


Route53 Records can be imported using the ID of the record. The ID is made up as ZONEID_RECORDNAME_CNAME:

```
terraform import aws_route53_record.default ZE2XGDR9HNNCQ__6f02f830b9c923aca5a897d8ca5ba83b.multi-service.as-test.techservices.illinois.edu_CNAME
```

Credits
--------------------

**Nota bene** the vast majority of the verbiage on this page was
taken directly from the Terraform manual, and in a few cases from
Amazon's documentation.
