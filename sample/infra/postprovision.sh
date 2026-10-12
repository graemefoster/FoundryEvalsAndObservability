#!/bin/sh
# postprovision hook (see azure.yaml). Runs after every `azd provision` / `azd up`; to run it
# on its own: `azd hooks run postprovision`. Safe to re-run.
#
# 1. Asks once for the GitHub repository (owner/name) the CI/CD workflows run in, and saves
#    it as GITHUB_REPOSITORY in the azd environment. Later runs reuse it without asking.
# 2. Deploys infra/monitoring.bicep: Application Insights, evaluator access for you, and the
#    managed identity GitHub Actions signs in as (OIDC, environment `demo`).
# 3. If the GitHub CLI is signed in, creates the `demo` environment and sets its seven
#    variables. Otherwise prints the one command to finish that later.
set -eu

env_value() { azd env get-value "$1" 2>/dev/null || true; }
warn() { echo "WARNING: $1" >&2; }

ENV_NAME="${AZURE_ENV_NAME:-$(env_value AZURE_ENV_NAME)}"
PROJECT_ID="${AZURE_AI_PROJECT_ID:-$(env_value AZURE_AI_PROJECT_ID)}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-$(env_value AZURE_RESOURCE_GROUP)}"
[ -n "$PROJECT_ID" ] && [ -n "$RESOURCE_GROUP" ] || {
  echo "ERROR: AZURE_AI_PROJECT_ID or AZURE_RESOURCE_GROUP is not set; was the project provisioned?" >&2
  exit 1
}
ACCOUNT_ID="${PROJECT_ID%/projects/*}"

# 1. GitHub repository: saved value, else ask (suggesting this clone's origin).
REPO="$(env_value GITHUB_REPOSITORY)"
if [ -z "$REPO" ]; then
  SUGGESTED="$(git remote get-url origin 2>/dev/null \
    | sed -E 's#^(https://github.com/|git@github.com:)##; s#\.git$##' || true)"
  if [ -r /dev/tty ]; then
    printf 'GitHub repository for the CI/CD workflows (owner/name) [%s]: ' "$SUGGESTED" > /dev/tty
    read -r ANSWER < /dev/tty || ANSWER=""
    REPO="${ANSWER:-$SUGGESTED}"
  else
    REPO="$SUGGESTED"
  fi
  if [ -n "$REPO" ]; then
    azd env set GITHUB_REPOSITORY "$REPO"
    echo "Saved GITHUB_REPOSITORY=$REPO in azd environment $ENV_NAME."
  else
    warn "no GitHub repository given; skipping the GitHub identity (monitoring only)."
  fi
fi

# 2. Monitoring, evaluator access and the GitHub identity.
EVALUATOR="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)"
[ -n "$EVALUATOR" ] || {
  echo "ERROR: sign in to Azure CLI as a user (az login): the evaluator role is granted to you." >&2
  exit 1
}
# Azure rejects a role assignment that already exists under another ID. Foundry grants the
# project identity Monitoring Reader itself when App Insights is connected, so check first.
PROJECT_PRINCIPAL="$(az resource show --ids "$PROJECT_ID" --query identity.principalId -o tsv)"
INSIGHTS_ID="/subscriptions/${ACCOUNT_ID#/subscriptions/}"
INSIGHTS_ID="${INSIGHTS_ID%%/providers/*}/providers/Microsoft.Insights/components/appi-$ENV_NAME"
READER_EXISTS=false
if [ -n "$(az role assignment list --assignee "$PROJECT_PRINCIPAL" --role "Monitoring Reader" \
  --scope "$INSIGHTS_ID" --query "[0].id" -o tsv 2>/dev/null)" ]; then
  READER_EXISTS=true
fi
echo "Deploying infra/monitoring.bicep (Application Insights, evaluator access, GitHub identity)..."
CLIENT_ID="$(az deployment group create --name demo-monitoring \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/monitoring.bicep \
  --parameters environmentName="$ENV_NAME" accountName="${ACCOUNT_ID##*/}" \
    projectName="${PROJECT_ID##*/}" evaluatorPrincipalId="$EVALUATOR" \
    githubRepository="$REPO" projectTraceReaderExists="$READER_EXISTS" \
  --query properties.outputs.githubClientId.value -o tsv)"
[ -n "$REPO" ] || exit 0
echo "GitHub Actions identity: client ID $CLIENT_ID, trusted for $REPO environment 'demo'."

# 3. GitHub environment and variables.
if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
  warn "GitHub CLI not installed or not signed in. After 'gh auth login', run: azd hooks run postprovision"
  exit 0
fi
gh api -X PUT "repos/$REPO/environments/demo" --silent \
  || { warn "couldn't create the 'demo' environment in $REPO (are you an admin?)."; exit 0; }
set_var() { gh variable set "$1" --env demo --repo "$REPO" --body "$2"; }
set_var AZURE_CLIENT_ID "$CLIENT_ID"
set_var AZURE_TENANT_ID "$(az account show --query tenantId -o tsv)"
set_var AZURE_ENV_NAME "$ENV_NAME"
for key in AZURE_SUBSCRIPTION_ID AZURE_LOCATION AZURE_AI_PROJECT_ID FOUNDRY_PROJECT_ENDPOINT; do
  set_var "$key" "$(env_value "$key")"
done
echo "GitHub environment 'demo' in $REPO has all seven variables."
