#!/bin/sh
# postdeploy hook for purchasing-advice-demo (see azure.yaml).
# The hosted agent calls embeddings as its own agent identity, which `azd deploy` creates,
# so Bicep can't grant it. Give it Cognitive Services OpenAI User on the account (model
# inference only). Safe to re-run. Never fails the deploy: without the role, policy search
# falls back to keywords and the trace's fallback_reason says why.
set -u
SERVICE="purchasing-advice-demo"
ROLE="5e0bd9bd-7b93-4f28-af87-19fc36ad61bd" # Cognitive Services OpenAI User

warn() {
  echo "WARNING: $1 Policy search will fall back to keywords." >&2
  exit 0
}

# azd prints "key not found" on stdout, so only use its output when it succeeds.
PROJECT_ID="${AZURE_AI_PROJECT_ID:-$(azd env get-value AZURE_AI_PROJECT_ID 2>/dev/null || true)}"
case "$PROJECT_ID" in /subscriptions/*) ;; *) PROJECT_ID="" ;; esac
[ -n "$PROJECT_ID" ] || warn "AZURE_AI_PROJECT_ID is not set."

PRINCIPAL="$(azd ai agent show "$SERVICE" --output json 2>/dev/null | python3 -c \
  'import json, sys; print(json.load(sys.stdin)["instance_identity"]["principal_id"])' \
  2>/dev/null)"
[ -n "$PRINCIPAL" ] || warn "could not read the agent identity from 'azd ai agent show'."

if az role assignment create --assignee-object-id "$PRINCIPAL" \
  --assignee-principal-type ServicePrincipal --role "$ROLE" \
  --scope "${PROJECT_ID%/projects/*}" --output none; then
  echo "Agent identity $PRINCIPAL has Cognitive Services OpenAI User on the account (a new grant takes a few minutes)."
else
  warn "granting the embedding role to $PRINCIPAL failed."
fi
