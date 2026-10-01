#!/usr/bin/env bash
# One-time CI setup: keyless GitHub Actions -> Google Cloud via Workload Identity Federation.
# Usage: PROJECT_ID=... GITHUB_REPO=owner/name infra/bootstrap-ci.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
GITHUB_REPO="${GITHUB_REPO:?set GITHUB_REPO}"
POOL=github
PROVIDER=github
DEPLOYER_SA="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

gcloud iam service-accounts describe "$DEPLOYER_SA" --project="$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create github-deployer --project="$PROJECT_ID"
# run.admin: deploy.sh also sets service IAM (agent invoker, web --no-invoker-iam-check).
for role in roles/run.sourceDeveloper roles/run.admin roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$DEPLOYER_SA" --role="$role" --condition=None >/dev/null
done
# Deployer may act as the runtime service accounts (and the compute SA used by source builds).
for sa in "$AGENT_SA" "$WEB_SA" "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"; do
  gcloud iam service-accounts add-iam-policy-binding "$sa" --project="$PROJECT_ID" \
    --member="serviceAccount:$DEPLOYER_SA" --role=roles/iam.serviceAccountUser >/dev/null
done

gcloud iam workload-identity-pools describe "$POOL" --project="$PROJECT_ID" --location=global >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools create "$POOL" --project="$PROJECT_ID" --location=global
gcloud iam workload-identity-pools providers describe "$PROVIDER" --project="$PROJECT_ID" --location=global \
  --workload-identity-pool="$POOL" >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --project="$PROJECT_ID" --location=global \
    --workload-identity-pool="$POOL" --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}' && assertion.ref=='refs/heads/main'"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" --project="$PROJECT_ID" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GITHUB_REPO}" >/dev/null

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
gh variable set GCP_PROJECT_ID --repo "$GITHUB_REPO" --body "$PROJECT_ID"
gh variable set GCP_WIF_PROVIDER --repo "$GITHUB_REPO" --body "$WIF_PROVIDER"
gh variable set GCP_DEPLOYER_SA --repo "$GITHUB_REPO" --body "$DEPLOYER_SA"
echo "CI bootstrap done: $WIF_PROVIDER"
