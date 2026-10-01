#!/usr/bin/env bash
# Smoke-test that the model answers from the given location (e.g. global, asia-southeast1).
# Usage: PROJECT_ID=... infra/check-model.sh [location]
set -euo pipefail
source "$(dirname "$0")/config.sh"
LOC="${1:-$MODEL_LOCATION}"
HOST=$([[ "$LOC" == global ]] && echo aiplatform.googleapis.com || echo "$LOC-aiplatform.googleapis.com")
curl -sS -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "Content-Type: application/json" \
  "https://$HOST/v1/projects/$PROJECT_ID/locations/$LOC/publishers/google/models/$GEMINI_MODEL:generateContent" \
  -d '{"contents":[{"role":"user","parts":[{"text":"Reply with OK"}]}]}' | head -c 600; echo
