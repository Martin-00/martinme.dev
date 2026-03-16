output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (needed for cache invalidation in CI/CD)"
  value       = aws_cloudfront_distribution.website.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.website.domain_name
}

output "s3_bucket_name" {
  description = "S3 bucket name (needed for s3 sync in CI/CD)"
  value       = aws_s3_bucket.website.id
}

output "route53_nameservers" {
  description = "Route53 nameservers — set these in Porkbun"
  value       = aws_route53_zone.main.name_servers
}
