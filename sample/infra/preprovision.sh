#!/bin/sh
# preprovision hook (see azure.yaml). main.bicep requires githubRepository, bound to the azd
# environment value GITHUB_REPOSITORY. If it isn't set yet, ask once (suggesting this clone's
# origin) and save it, so every later provision reuses it without asking.
set -eu
# azd prints "key not found" on stdout, so test the exit code, not the output.
azd env get-value GITHUB_REPOSITORY >/dev/null 2>&1 && exit 0

SUGGESTED="$(git remote get-url origin 2>/dev/null \
  | sed -E 's#^(https://github.com/|git@github.com:)##; s#\.git$##' || true)"
REPO=""
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
