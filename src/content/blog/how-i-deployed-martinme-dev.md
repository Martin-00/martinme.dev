---
title: 'How I deployed martinme.dev on AWS for $0.51/month'
description: 'S3, CloudFront, Terraform, OIDC, and zero-trust CI/CD. The hard way that teaches you everything.'
pubDate: 'Mar 10 2026'
updatedDate: 'Mar 16 2026'
---

I built my personal website on AWS from scratch. Not on Vercel, not on Netlify, not on Cloudflare Pages. On S3, CloudFront, ACM, Route 53, Terraform, and GitHub Actions with OIDC authentication. The whole thing costs $0.51/month.

This post explains the architecture, the decisions behind each component, the problems I ran into, and how I solved them. If you're thinking about building your own, everything here is replicable. The [source code is on GitHub](https://github.com/Martin-00/martinme.dev).

## Why the hard way?

I'm a Data Engineer at [Caylent](https://caylent.com), an AWS consulting company. I build cloud infrastructure for clients every day. Deploying my personal site on a managed platform would have taken five minutes, but it would have taught me nothing.

One personal website that touches S3, CloudFront, ACM, Route 53, IAM, OIDC, Terraform, and GitHub Actions covers half the AWS Solutions Architect exam. I wanted the knowledge, not just the result.

## Prerequisites

Before starting, you need:
- An **AWS account** with admin access
- A **domain name** (I used [Porkbun](https://porkbun.com), ~$10/year for a `.dev`)
- **AWS CLI v2** (`brew install awscli`) with SSO configured
- **OpenTofu** or **Terraform** (`brew install opentofu`)
- **Node.js 20+** and npm
- A **GitHub account** and repo

## The architecture

```
GitHub (push to main)
    │
    ▼  OIDC (no keys!)
GitHub Actions
    │
    ├─→ npm run build (Astro → static HTML/CSS/JS)
    ├─→ aws s3 sync (two-pass upload to S3)
    └─→ CloudFront cache invalidation

User → Route 53 (DNS) → CloudFront (CDN + SSL) → S3 (private bucket)
                              │
                         ACM (free SSL)
```

Every component earns its place. Here's why each one exists.

### S3: Private bucket, not a web server

The S3 bucket stores the static files. It is **completely private**: all four public access block settings are enabled, no bucket policy allows public reads, and static website hosting is not enabled.

Most tutorials tell you to make the bucket public or enable S3 website hosting. Both are wrong for production. Making the bucket public means anyone with the bucket URL can access your files directly, bypassing CloudFront (and your caching, analytics, and SSL). S3 website hosting doesn't support HTTPS.

Instead, we use Origin Access Control (OAC). Only CloudFront can read from the bucket, authenticated via SigV4 request signing. The bucket policy explicitly scopes access to one specific CloudFront distribution ARN.

### CloudFront: CDN, HTTPS, and the URI rewrite problem

CloudFront serves the content globally with HTTPS, gzip compression, and edge caching. It forces HTTP-to-HTTPS redirects and uses TLS 1.2 minimum.

CloudFront also solves a problem that S3 with OAC creates: **subdirectory index resolution**. When you request `/blog`, S3 doesn't know to serve `/blog/index.html`. It returns 403 Access Denied. This doesn't happen with S3 website hosting (which auto-resolves indexes), but we're not using website hosting because we want OAC.

The fix is a CloudFront Function on the Viewer Request event:

```javascript
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.endsWith('/')) {
    request.uri += 'index.html';
  } else if (!uri.includes('.')) {
    request.uri += '/index.html';
  }

  return request;
}
```

This runs on every request, at the edge, before CloudFront checks its cache. Without it, every path except the root would return 403.

CloudFront also handles **custom error responses**. S3 with OAC returns 403 for missing files (not 404), which would show users an ugly XML error page. We map both 403 and 404 responses to serve `/404.html` with a proper 404 status code.

### ACM: Free SSL for both domains

AWS Certificate Manager provides a free SSL certificate covering both `martinme.dev` and `www.martinme.dev` (as a Subject Alternative Name). The certificate uses DNS validation, with CNAME records managed automatically in Route 53 through Terraform.

The `www` SAN is easy to forget. Without it, anyone typing `www.martinme.dev` gets a certificate error. We also create a separate Route 53 A record (alias) for the `www` subdomain pointing to the same CloudFront distribution.

### Route 53: DNS with alias records

Route 53 manages the hosted zone and DNS records. The domain is registered on Porkbun (cheaper), but the nameservers are delegated to Route 53 (better integration with AWS services).

Both root (`martinme.dev`) and www (`www.martinme.dev`) use A records with CloudFront aliases. These are different from CNAME records: they work at the zone apex (which CNAMEs can't), they resolve at the DNS level (no extra hop), and they're free (Route 53 doesn't charge for alias queries to CloudFront).

### Terraform: Infrastructure as code, remotely locked

All infrastructure is defined in Terraform (we actually use [OpenTofu](https://opentofu.org/), the open-source fork, because Terraform 1.5.7's SSO cache format is incompatible with the newer AWS CLI v2 `sso-session` config). The files live in `infra/` in the repo.

State is stored in an S3 bucket with versioning enabled and public access blocked. A DynamoDB table provides state locking, preventing corruption if two processes run Terraform simultaneously.

The provider block specifies only the region. No profile, no access keys, no hardcoded credentials. Authentication comes from environment variables, which we manage with `direnv` (an `.envrc` file that auto-exports `AWS_PROFILE` when you `cd` into the project directory).

## AWS SSO: No access keys on your machine

Most tutorials have you run `aws configure` and paste long-lived access keys into `~/.aws/credentials`. Those keys never expire, sit in plaintext on your disk, and are a single leak away from a security incident.

Instead, we use **IAM Identity Center** (AWS SSO). You authenticate via browser, get temporary credentials that expire after hours, and never store secrets on your filesystem. When the session expires, you run `aws sso login` and click approve. That's it.

Combined with `direnv`, the workflow is: `cd` into the project directory, your AWS profile activates automatically. If the session expired, `aws sso login`, browser pops open, click approve, done.

This is how Caylent manages all client accounts. It's enterprise-grade, and there's no reason not to use it for personal projects too.

## OIDC: Zero-trust CI/CD

This is the part I find most interesting. The deployment pipeline uses **OIDC federation** instead of stored AWS credentials.

Here's how it works:

1. GitHub Actions starts a workflow run and requests an OIDC token from GitHub's identity provider
2. The token contains claims identifying the repo, branch, and workflow (`repo:Martin-00/martinme.dev:ref:refs/heads/main`)
3. GitHub Actions calls AWS `sts:AssumeRoleWithWebIdentity`, presenting the token
4. AWS validates the token against the OIDC provider registered in your account, checks the trust policy conditions (audience, subject), and if everything matches, returns temporary credentials
5. The workflow uses those credentials to deploy to S3 and invalidate CloudFront

The IAM role's trust policy is scoped to one specific repository and one specific branch. No other repo, no other branch, no other GitHub account can assume the role. The credentials are temporary (valid for one workflow run). Nothing is stored in GitHub Secrets except the role ARN (which is not a secret, it's an identifier).

**Gotcha we hit:** The OIDC provider's thumbprint can go stale if GitHub rotates their signing certificate. If you get `Not authorized to perform sts:AssumeRoleWithWebIdentity` and everything else looks correct, try deleting and recreating the OIDC identity provider in the IAM console. Let AWS fetch the current thumbprint.

**Another gotcha:** The role ARN in your GitHub secret must exactly match the ARN from IAM, including the double colon (`::`) before the account ID. IAM ARNs have no region field, so the format is `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`. A single missing colon causes authentication failure with no helpful error message.

## Two-pass deploys: Cache strategy

Astro puts all CSS, JS, and optimized images into `/_astro/` with content hashes in the filenames (e.g., `_slug_.DcDY_FhW.css`). These files are immutable: if the content changes, the filename changes. Browsers can cache them forever.

HTML files change on every deploy. If a browser caches an old `index.html`, the user sees stale content.

The deploy is two `aws s3 sync` commands with different cache headers:

```bash
# Pass 1: Immutable hashed assets, cache for 1 year
aws s3 sync dist/_astro s3://martinme.dev/_astro \
  --cache-control "public,max-age=31536000,immutable"

# Pass 2: HTML and everything else, never cache
aws s3 sync dist s3://martinme.dev --delete \
  --cache-control "no-cache,no-store,must-revalidate"
```

The `--delete` flag on the second pass removes files from S3 that no longer exist in the build output (old blog posts, renamed pages). The first pass runs separately to preserve the long cache headers on assets that the second pass would otherwise overwrite with `no-cache`.

After both syncs, a CloudFront cache invalidation ensures edge nodes pick up the new HTML immediately.

## What it costs

| Service | Monthly cost |
|---------|-------------|
| S3 (storage + requests) | ~$0.01 |
| CloudFront | Free tier (1 TB/month) |
| Route 53 hosted zone | $0.50 |
| ACM certificate | Free |
| DynamoDB (state lock) | Free tier |
| **Total** | **~$0.51** |

The Route 53 hosted zone is the only unavoidable cost. Everything else is either free tier or negligible at personal-site traffic levels.

## Problems I hit and how I solved them

**Terraform 1.5.7 can't read the newer AWS CLI SSO cache.** Homebrew installs Terraform 1.5.7 (the last open-source version before the BUSL license change). This version computes the SSO cache filename differently than AWS CLI v2 with `sso-session` config blocks. The fix: switch to [OpenTofu](https://opentofu.org/), the community fork. `brew install opentofu`, then use `tofu` instead of `terraform`. Drop-in compatible, supports the newer SSO format.

**ACM validation blocks `terraform apply`.** Terraform creates the ACM certificate and Route 53 DNS validation records, then blocks on `aws_acm_certificate_validation` until the cert is validated. But if your registrar's nameservers haven't been updated to Route 53 yet, DNS can't resolve the validation CNAMEs, and Terraform waits indefinitely. The solution: while Terraform is blocking, quickly update your registrar's nameservers to the Route 53 ones (visible in the AWS Console). Once DNS propagates (~15 minutes), ACM validates automatically and Terraform continues.

**S3 returns 403 instead of 404 for missing files.** With OAC, S3 returns `AccessDenied` (403) for files that don't exist, because the request is technically unauthorized for a non-existent key. CloudFront custom error responses map both 403 and 404 to your `/404.html` page with a 404 status code.

**OIDC thumbprint mismatch.** The OIDC identity provider's thumbprint can become stale. If the pipeline fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity` and the trust policy looks correct, delete the OIDC provider in IAM and recreate it. AWS fetches the current thumbprint automatically.

## The GitHub Actions workflow

The complete `.github/workflows/deploy.yml`:

```yaml
name: Deploy martinme.dev

on:
  push:
    branches: [main]

concurrency:
  group: "pages"
  cancel-in-progress: true

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - run: npm ci
      - run: npm run build

      - name: Deploy assets
        run: |
          aws s3 sync dist/_astro s3://martinme.dev/_astro \
            --cache-control "public,max-age=31536000,immutable"

      - name: Deploy HTML
        run: |
          aws s3 sync dist s3://martinme.dev --delete \
            --cache-control "no-cache,no-store,must-revalidate"

      - name: Invalidate cache
        run: |
          aws cloudfront create-invalidation \
            --distribution-id E39RCQ73MJ700B \
            --paths "/*"
```

`npm ci` (not `npm install`) requires `package-lock.json` in the repo. Make sure it's not in your `.gitignore`.

The `permissions.id-token: write` line is what enables OIDC. Without it, GitHub Actions can't request the token that AWS needs for authentication.

## What I learned

Building this the hard way forced me to understand things I would have glossed over with a one-click deploy:

- **OAC vs OAI**: Origin Access Control is the modern replacement for Origin Access Identity. OAC supports all S3 features, uses SigV4 signing, and works with SSE-KMS. OAI is legacy.
- **CloudFront Functions vs Lambda@Edge**: CloudFront Functions run in JavaScript at the edge, are cheaper, faster, and limited to viewer request/response events. Lambda@Edge is more powerful but slower and more expensive. For URI rewrites, CloudFront Functions are the right tool.
- **OIDC federation**: The trust chain from GitHub's identity provider to AWS STS is elegant. No secrets stored, no keys to rotate, scope locked to a specific repo and branch. This pattern works for any CI/CD system that supports OIDC, not just GitHub Actions.
- **DNS delegation**: Registrars manage the domain registration. Nameservers decide who answers DNS queries. Hosted zones contain the records. These are three separate concerns, and confusing them causes most DNS debugging pain.
- **Terraform state locking**: Without DynamoDB locking, two simultaneous `terraform apply` runs could corrupt the state file. With locking, the second run waits or fails cleanly. The DynamoDB table costs nothing on pay-per-request and prevents a class of problems that are very hard to recover from.

None of this shows up in a Vercel deploy. All of it shows up in an AWS certification exam, a job interview, or a client engagement.

The source code for this site, including all Terraform files and the GitHub Actions workflow, is at [github.com/Martin-00/martinme.dev](https://github.com/Martin-00/martinme.dev).
