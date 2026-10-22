# =============================================================================
# Visit logs — CloudFront standard logging (v2) into a private bucket
# Only the fields /visits needs. No IP addresses, cookies, or query strings are ever
# written: CloudFront itself resolves the country (c-country), so the IP never leaves it.
# Delivery to S3 is free; storage is a few KB a day.
# =============================================================================

resource "aws_s3_bucket" "logs" {
  bucket = "martinme-dev-logs"
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket = aws_s3_bucket.logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Raw logs are deleted after 90 days. The counts on /visits live in the repo
# (src/data/visits.json), so the history outlives the raw logs.
resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id

  rule {
    id     = "expire-raw-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

# The account ID comes from the caller, so it stays out of this public repo. imports.tf uses it too.
data "aws_caller_identity" "current" {}

# Only the log delivery service may write, only from this account's delivery source,
# only under cloudfront/. Every request must use TLS.
resource "aws_s3_bucket_policy" "logs" {
  bucket = aws_s3_bucket.logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSLogDeliveryWrite"
        Effect    = "Allow"
        Principal = { Service = "delivery.logs.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.logs.arn}/cloudfront/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"      = "bucket-owner-full-control"
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:logs:us-east-1:${data.aws_caller_identity.current.account_id}:delivery-source:*"
          }
        }
      },
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.logs.arn, "${aws_s3_bucket.logs.arn}/*"]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      }
    ]
  })
}

resource "aws_cloudwatch_log_delivery_source" "cloudfront" {
  name         = "martinme-dev-cloudfront"
  log_type     = "ACCESS_LOGS"
  resource_arn = aws_cloudfront_distribution.website.arn
}

resource "aws_cloudwatch_log_delivery_destination" "logs" {
  name          = "martinme-dev-logs"
  output_format = "json"

  delivery_destination_configuration {
    destination_resource_arn = "${aws_s3_bucket.logs.arn}/cloudfront"
  }
}

# The field list is the privacy policy: change it only together with the note on /visits.
resource "aws_cloudwatch_log_delivery" "cloudfront" {
  delivery_source_name     = aws_cloudwatch_log_delivery_source.cloudfront.name
  delivery_destination_arn = aws_cloudwatch_log_delivery_destination.logs.arn

  record_fields = [
    "date",
    "time",
    "c-country",
    "asn",
    "cs-method",
    "cs-uri-stem",
    "sc-status",
    "cs(User-Agent)",
  ]

  depends_on = [aws_s3_bucket_policy.logs]
}
