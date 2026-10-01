#!/usr/bin/env bash
# One-time project setup: project, billing, APIs, service accounts, budget alert.
# Usage: PROJECT_ID=... BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX [BUDGET_USD=50] infra/bootstrap.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
BILLING_ACCOUNT="${BILLING_ACCOUNT:?set BILLING_ACCOUNT}"
BUDGET_USD="${BUDGET_USD:-50}"

gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 || gcloud projects create "$PROJECT_ID"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  aiplatform.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com logging.googleapis.com \
  firestore.googleapis.com bigquery.googleapis.com modelarmor.googleapis.com \
  iamcredentials.googleapis.com billingbudgets.googleapis.com

for sa in agent-runtime web-runtime; do
  gcloud iam service-accounts describe "$sa@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1 \
    || gcloud iam service-accounts create "$sa"
done
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$AGENT_SA" --role=roles/aiplatform.user --condition=None >/dev/null

gcloud billing budgets create --billing-account="$BILLING_ACCOUNT" \
  --display-name="$PROJECT_ID budget" --budget-amount="${BUDGET_USD}USD" \
  --filter-projects="projects/$PROJECT_ID" \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0

echo "bootstrap done: $PROJECT_ID ($REGION)"
