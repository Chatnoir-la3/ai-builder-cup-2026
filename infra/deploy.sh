#!/usr/bin/env bash
# Build from source and deploy both services to Cloud Run.
# The agent is private; only the web service account may invoke it.
# The web is public via --no-invoker-iam-check, which works under domain-restricted-sharing org policies.
# Usage: PROJECT_ID=... infra/deploy.sh [agent|web|all]
set -euo pipefail
source "$(dirname "$0")/config.sh"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-all}"

if [[ "$TARGET" == agent || "$TARGET" == all ]]; then
  gcloud run deploy "$AGENT_SERVICE" --project="$PROJECT_ID" --region="$REGION" \
    --source="$ROOT/agent" --service-account="$AGENT_SA" --no-allow-unauthenticated \
    --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$MODEL_LOCATION,GEMINI_MODEL=$GEMINI_MODEL"
  gcloud run services add-iam-policy-binding "$AGENT_SERVICE" --project="$PROJECT_ID" --region="$REGION" \
    --member="serviceAccount:$WEB_SA" --role=roles/run.invoker >/dev/null
fi

if [[ "$TARGET" == web || "$TARGET" == all ]]; then
  AGENT_URL="$(gcloud run services describe "$AGENT_SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"
  gcloud run deploy "$WEB_SERVICE" --project="$PROJECT_ID" --region="$REGION" \
    --source="$ROOT/web" --service-account="$WEB_SA" --no-invoker-iam-check \
    --set-env-vars="AGENT_URL=$AGENT_URL"
fi
