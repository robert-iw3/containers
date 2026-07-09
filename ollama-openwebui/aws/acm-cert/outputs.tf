output "arn" {
  description = "The ARN of the certificate"
  value       = aws_acm_certificate.default.arn
}

output "domain_validation_options" {
  description = "A list of attributes to used to complete certificate validation."
  value       = aws_acm_certificate.default.domain_validation_options
}

output "_create_route53_record" {
  value = var._debug ? local.create_route53_record : null
}

output "_local_skip_route53_validation" {
  value = var._debug ? local.skip_route53_validation : null
}
