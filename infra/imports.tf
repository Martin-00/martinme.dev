# =============================================================================
# One-time adoption of the hand-made resources in security.tf into state.
# Once applied these blocks do nothing; this whole file can be deleted after.
# The account ID comes from the caller (declared in visits.tf) so it stays out of this public repo.
# =============================================================================

import {
  to = aws_iam_openid_connect_provider.github
  id = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

import {
  to = aws_iam_role.deploy
  id = "github-actions-martinme-deploy"
}

import {
  to = aws_iam_role_policy.deploy
  id = "github-actions-martinme-deploy:martinme-dev-deploy"
}

import {
  to = aws_iam_role_policies_exclusive.deploy
  id = "github-actions-martinme-deploy"
}

import {
  to = aws_iam_role_policy_attachments_exclusive.deploy
  id = "github-actions-martinme-deploy"
}

import {
  to = aws_s3_account_public_access_block.account
  id = data.aws_caller_identity.current.account_id
}
