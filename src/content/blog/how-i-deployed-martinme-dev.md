---
title: 'How I deployed martinme.dev on AWS for $0.51/month'
description: 'S3, CloudFront, Terraform, OIDC, and zero-trust CI/CD. The hard way that teaches you everything.'
pubDate: 'Mar 10 2026'
---

I finally built my personal website. Not on Vercel. Not on Netlify. Not on Cloudflare Pages. On **AWS**, from scratch, with Terraform, because I wanted to actually *learn* the infrastructure, not just click a deploy button.

This post is the story of how I did it, what I learned, and why I chose the hard path.

## Why not the easy way?

I'm a Data Engineer at [Caylent](https://caylent.com), an AWS consulting company. I spend my days building cloud infrastructure for clients. So when it came time to build my own site, deploying on a managed platform felt like a chef eating instant ramen at home.

I wanted this project to be a learning accelerator. One personal website that touches **S3, CloudFront, ACM, Route 53, IAM, OIDC, Terraform, and GitHub Actions**. That's half the AWS Solutions Architect exam right there.

## The architecture

```
GitHub (push to main)
    │
    ▼ (OIDC, no keys!)
GitHub Actions
    │
    ├─→ npm run build (Astro → static files)
    ├─→ aws s3 sync (upload to S3)
    └─→ CloudFront invalidation (refresh cache)

User → CloudFront (CDN + SSL) → S3 (private bucket)
```

Every component earns its place:

- **S3** stores the static files. The bucket is completely private, no public access, no website hosting enabled. Only CloudFront can read from it via Origin Access Control (OAC).
- **CloudFront** serves the content globally with HTTPS, compression, and edge caching. It also handles the `index.html` rewrites that S3 can't do natively with OAC.
- **ACM** provides a free SSL certificate for both `martinme.dev` and `www.martinme.dev`.
- **Route 53** manages DNS. The domain is registered on Porkbun, but the nameservers point to Route 53.
- **Terraform** defines all of this as code. One `tofu apply` and the entire infrastructure exists. One `tofu destroy` and it's gone.

## The tricky parts

### S3 + OAC doesn't resolve subdirectory indexes

This one surprised me. When you use Origin Access Control (the modern, secure way to connect CloudFront to S3), requesting `/blog` doesn't automatically serve `/blog/index.html`. S3 just returns a 403.

The fix is a CloudFront Function that rewrites URIs:

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

Small function, but without it the site is broken. This is the kind of thing you only learn by doing it yourself.

### ACM certificate validation blocks everything

Terraform creates the ACM certificate and the Route 53 DNS validation records, then waits for the certificate to validate. But if your domain's nameservers haven't been updated to Route 53 yet, it just... sits there. Waiting.

The trick: while Terraform is blocking on ACM validation, quickly update your registrar's nameservers to the Route 53 ones. Once DNS propagates, ACM validates, and Terraform continues creating everything else.

### Two-pass deploys

Astro puts all CSS, JS, and images into `_astro/` with content hashes in the filename. These files never change, so browsers can cache them forever. HTML files change on every deploy, so they should never be cached.

```bash
# Immutable assets, cache for 1 year
aws s3 sync dist/_astro s3://bucket/_astro \
  --cache-control "public,max-age=31536000,immutable"

# HTML, always fetch fresh
aws s3 sync dist s3://bucket --delete \
  --cache-control "no-cache,no-store,must-revalidate"
```

## Zero-trust CI/CD

The deployment pipeline uses **OIDC federation**. GitHub Actions exchanges a short-lived token with AWS for temporary credentials. No access keys stored anywhere. No secrets to rotate. The IAM role's trust policy is scoped to my exact repository and branch.

Push to `main`, GitHub Actions builds the site, syncs to S3, invalidates CloudFront. That's it. The entire pipeline.

## What it costs

| Service | Monthly |
|---------|---------|
| S3 | ~$0.01 |
| CloudFront | Free tier |
| Route 53 | $0.50 |
| ACM | Free |
| DynamoDB (state lock) | Free tier |
| **Total** | **~$0.51** |

## What I learned

Building infrastructure the "hard way" forced me to understand things I would have glossed over with a one-click deploy:

- How OAC actually works vs the old OAI approach
- Why CloudFront Functions exist and when you need them
- How OIDC federation eliminates the need for long-lived credentials
- The relationship between registrars, nameservers, hosted zones, and DNS records
- How Terraform state locking prevents corruption with DynamoDB

None of this shows up in a Vercel deploy. All of it shows up in an AWS certification exam, a job interview, or a client engagement.

The site is built with [Astro](https://astro.build/), and the source code is on [GitHub](https://github.com/Martin-00/martinme.dev). If you're thinking about building your own, skip the easy way. You'll learn more in one weekend of debugging CloudFront than in a month of reading documentation.
