locals {
  fqdn                    = var.hostname != "" ? format("%s.%s", var.hostname, var.domain) : var.domain
  san                     = formatlist("%s.%s", var.subject_alternative_names, var.domain)
  skip_route53_validation = var.validation_method == "EMAIL" ? true : var.skip_route53_validation
  create_route53_record   = var.create_route53_record && (!local.skip_route53_validation)
}

data "aws_route53_zone" "default" {
  for_each = toset((local.create_route53_record) ? [var.domain] : [])

  name         = each.key
  private_zone = false
}

resource "aws_acm_certificate" "default" {
  domain_name               = local.fqdn
  subject_alternative_names = local.san
  validation_method         = var.validation_method

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

locals {
  dvo_data = (!local.create_route53_record) ? {} : {
    for dvo in aws_acm_certificate.default.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }
}

resource "aws_route53_record" "default" {
  for_each = local.dvo_data
  name     = each.value.name
  records  = [each.value.record]
  ttl      = 60
  type     = each.value.type
  zone_id  = data.aws_route53_zone.default[var.domain].zone_id
}

resource "aws_acm_certificate_validation" "default" {
  for_each = toset((local.skip_route53_validation) ? [] : [aws_acm_certificate.default.domain_name])

  certificate_arn         = aws_acm_certificate.default.arn
  validation_record_fqdns = [for record in aws_route53_record.default : record.fqdn]
}
