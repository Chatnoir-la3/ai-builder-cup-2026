#!/usr/bin/env bash
# One-time platform setup: Model Armor template (guardrail) and BigQuery dataset (audit trail).
# Safe to re-run: the template is created or updated in place.
# Usage: PROJECT_ID=... infra/bootstrap-platform.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"

# Model Armor: prompt-injection/jailbreak and responsible-AI filters.
# The malicious-URL filter is not offered in asia-southeast1 (checked 2026-10-02).
# Sensitive-data (SDP) filtering is left off so demo account numbers are not blocked.
MA="https://modelarmor.${GUARD_LOCATION}.rep.googleapis.com/v1/projects/${PROJECT_ID}/locations/${GUARD_LOCATION}/templates"
TOKEN="$(gcloud auth print-access-token)"
if curl -sf -H "Authorization: Bearer $TOKEN" "$MA/$MODEL_ARMOR_TEMPLATE_ID" >/dev/null; then
  METHOD=PATCH URL="$MA/$MODEL_ARMOR_TEMPLATE_ID?updateMask=filterConfig"
else
  METHOD=POST URL="$MA?templateId=$MODEL_ARMOR_TEMPLATE_ID"
fi
curl -sSf -X "$METHOD" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$URL" -d '{
  "filterConfig": {
    "piAndJailbreakFilterSettings": {"filterEnforcement": "ENABLED", "confidenceLevel": "MEDIUM_AND_ABOVE"},
    "raiSettings": {"raiFilters": [
      {"filterType": "DANGEROUS", "confidenceLevel": "MEDIUM_AND_ABOVE"},
      {"filterType": "HARASSMENT", "confidenceLevel": "MEDIUM_AND_ABOVE"},
      {"filterType": "HATE_SPEECH", "confidenceLevel": "MEDIUM_AND_ABOVE"},
      {"filterType": "SEXUALLY_EXPLICIT", "confidenceLevel": "MEDIUM_AND_ABOVE"}
    ]}
  }
}' >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$AGENT_SA" --role=roles/modelarmor.user --condition=None >/dev/null

# Audit trail: the ADK BigQuery Agent Analytics plugin creates its table on first write.
BQ="https://bigquery.googleapis.com/bigquery/v2/projects/${PROJECT_ID}/datasets"
curl -sf -H "Authorization: Bearer $TOKEN" "$BQ/$AUDIT_DATASET" >/dev/null \
  || curl -sSf -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$BQ" \
    -d "{\"datasetReference\": {\"datasetId\": \"$AUDIT_DATASET\"}, \"location\": \"$GUARD_LOCATION\"}" >/dev/null
for role in roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$AGENT_SA" --role="$role" --condition=None >/dev/null
done

echo "platform bootstrap done: $MODEL_ARMOR_TEMPLATE, dataset $AUDIT_DATASET"
