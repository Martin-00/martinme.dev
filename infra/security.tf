# =============================================================================
# GitHub Actions deploy role — OIDC, so the workflow holds no AWS keys
# Made by hand on 2026-10-20 and adopted with imports.tf; plan now flags any hand edit.
# =============================================================================

# AWS no longer checks thumbprints for GitHub's OIDC, so thumbprint_list is left to AWS.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # Tags as set in the console, so the import changes nothing
  tags = {
    Project     = "martinme.dev"
    Environment = "cicd"
    Owner       = "martin"
    ManagedBy   = "console"
  }
}

# Only workflow runs on main in this repo can assume the role. The subject is GitHub's
# immutable form, pinned to the owner and repo IDs, so a rename can't break or spoof it.
resource "aws_iam_role" "deploy" {
  name = "github-actions-martinme-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = "repo:martinme-dev@43385005/martinme.dev@1168199808:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  tags = {
    Project     = "martinme.dev"
    Environment = "cicd"
    Owner       = "martin"
    ManagedBy   = "console"
  }
}

# Least privilege: sync the site bucket and invalidate the CDN, nothing else.
# If a deploy needs a new AWS call, add it here. Never attach AdministratorAccess instead.
resource "aws_iam_role_policy" "deploy" {
  name = "martinme-dev-deploy"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListSiteBucket"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.website.arn
      },
      {
        Sid      = "WriteSiteObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.website.arn}/*"
      },
      {
        Sid      = "InvalidateSiteCache"
        Effect   = "Allow"
        Action   = "cloudfront:CreateInvalidation"
        Resource = aws_cloudfront_distribution.website.arn
      }
    ]
  })
}

# The inline policy above is the role's only permission. Anything added by hand
# (AdministratorAccess re-attached, a second inline policy) shows up in plan, and apply removes it.
resource "aws_iam_role_policies_exclusive" "deploy" {
  role_name    = aws_iam_role.deploy.name
  policy_names = [aws_iam_role_policy.deploy.name]
}

resource "aws_iam_role_policy_attachments_exclusive" "deploy" {
  role_name   = aws_iam_role.deploy.name
  policy_arns = []
}

# =============================================================================
# S3 Block Public Access for the whole account (every bucket, tfstate included)
# =============================================================================

resource "aws_s3_account_public_access_block" "account" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
