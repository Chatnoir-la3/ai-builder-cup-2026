# Shared settings. Override any value via environment variables.
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast1}"
MODEL_LOCATION="${MODEL_LOCATION:-global}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"
AGENT_SERVICE="${AGENT_SERVICE:-agent}"
WEB_SERVICE="${WEB_SERVICE:-web}"
AGENT_SA="agent-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
WEB_SA="web-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
