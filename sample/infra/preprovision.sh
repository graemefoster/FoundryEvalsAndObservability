#!/bin/sh
# preprovision hook (see azure.yaml).
# 1. main.bicep requires githubRepository, bound to GITHUB_REPOSITORY. If it isn't set yet, ask
#    once (suggesting this clone's origin) and save it; later provisions reuse it.
# 2. GitHub's OIDC token subject now includes owner and repository IDs
#    (repo:owner@123/name@456:environment:demo). If the GitHub CLI is signed in, look them up
#    and save the exact subject as GITHUB_OIDC_SUBJECT, so the identity trusts what GitHub sends.
# 3. Save your user object ID as AZURE_PRINCIPAL_ID, so main.bicep gives you account-level
#    Foundry User: evaluations call the judge models as you.
set -eu
# azd prints "key not found" on stdout, so only use its output when it succeeds.
v() { out="$(azd env get-value "$1" 2>/dev/null)" && printf '%s' "$out"; }

REPO="$(v GITHUB_REPOSITORY || true)"
if [ -z "$REPO" ]; then
  SUGGESTED="$(git remote get-url origin 2>/dev/null \
    | sed -E 's#^(https://github.com/|git@github.com:)##; s#\.git$##' || true)"
  if (exec </dev/tty >/dev/tty) 2>/dev/null; then  # a terminal we can really open
    printf 'GitHub repository for the CI/CD workflows (owner/name) [%s]: ' "$SUGGESTED" > /dev/tty
    read -r REPO < /dev/tty || REPO=""
  fi
  REPO="${REPO:-$SUGGESTED}"
  if [ -z "$REPO" ]; then
    echo "ERROR: set the GitHub repository first: azd env set GITHUB_REPOSITORY <owner>/<name>" >&2
    exit 1
  fi
  azd env set GITHUB_REPOSITORY "$REPO"
  echo "Saved GITHUB_REPOSITORY=$REPO."
fi

if command -v gh >/dev/null 2>&1 && IDS="$(gh api "repos/$REPO" --jq '"\(.owner.login)@\(.owner.id)/\(.name)@\(.id)"' 2>/dev/null)"; then
  SUBJECT="repo:$IDS:environment:demo"
  if [ "$(v GITHUB_OIDC_SUBJECT || true)" != "$SUBJECT" ]; then
    azd env set GITHUB_OIDC_SUBJECT "$SUBJECT"
    echo "Saved GITHUB_OIDC_SUBJECT=$SUBJECT."
  fi
else
  echo "WARNING: couldn't look up $REPO with the GitHub CLI; the identity will trust the classic subject repo:$REPO:environment:demo." >&2
fi

if ME="$(az ad signed-in-user show --query id -o tsv 2>/dev/null)" && [ -n "$ME" ]; then
  if [ "$(v AZURE_PRINCIPAL_ID || true)" != "$ME" ]; then
    azd env set AZURE_PRINCIPAL_ID "$ME"
    echo "Saved AZURE_PRINCIPAL_ID=$ME (you run the evaluations)."
  fi
else
  echo "WARNING: couldn't read your user from 'az ad signed-in-user show'; run 'az login' or evaluations can't call the judges." >&2
fi
