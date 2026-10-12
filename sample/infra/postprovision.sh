#!/bin/sh
# postprovision hook (see azure.yaml). Provisioning (main.bicep) created the GitHub Actions
# identity; this points GitHub at it: if the GitHub CLI is signed in, create the `demo`
# environment in GITHUB_REPOSITORY and set its seven variables. Never fails the provision.
# Re-run on its own (for example after `gh auth login`): azd hooks run postprovision
set -u
# azd prints "key not found" on stdout, so only use its output when it succeeds.
v() { out="$(azd env get-value "$1" 2>/dev/null)" && printf '%s' "$out"; }
REPO="$(v GITHUB_REPOSITORY)"
CLIENT_ID="$(v githubClientId)"  # camelCase: see the outputs in main.bicep
if [ -z "$REPO" ] || [ -z "$CLIENT_ID" ]; then
  echo "WARNING: GITHUB_REPOSITORY or githubClientId missing; was main.bicep provisioned?" >&2
  exit 0
fi
if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
  echo "WARNING: GitHub CLI not signed in. After 'gh auth login', run: azd hooks run postprovision" >&2
  exit 0
fi
if ! gh api -X PUT "repos/$REPO/environments/demo" --silent; then
  echo "WARNING: couldn't create the 'demo' environment in $REPO (are you an admin?)." >&2
  exit 0
fi
set_var() { gh variable set "$1" --env demo --repo "$REPO" --body "$2"; }
set_var AZURE_CLIENT_ID "$CLIENT_ID"
set_var AZURE_TENANT_ID "$(v githubTenantId)"
for key in AZURE_SUBSCRIPTION_ID AZURE_ENV_NAME AZURE_LOCATION AZURE_AI_PROJECT_ID \
  FOUNDRY_PROJECT_ENDPOINT; do
  set_var "$key" "$(v "$key")"
done
echo "GitHub environment 'demo' in $REPO has all seven variables (identity $CLIENT_ID)."
