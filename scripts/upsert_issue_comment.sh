#!/usr/bin/env bash
set -euo pipefail

ISSUE_URL="${1:?issue url required}"
BODY_FILE="${2:?body file required}"

if grep -qE '^•\s' "$BODY_FILE"; then
  sed -i 's/^•[ ]\{0,1\}//' "$BODY_FILE"
fi

ME="$(gh api user --jq .login)"

OWNER="$(printf '%s' "$ISSUE_URL" | awk -F/ '{print $4}')"
REPO="$(printf '%s' "$ISSUE_URL" | awk -F/ '{print $5}')"
NUMBER="$(printf '%s' "$ISSUE_URL" | awk -F/ '{print $NF}')"

if [ -z "$OWNER" ] || [ -z "$REPO" ] || [ -z "$NUMBER" ]; then
  echo "ERROR: failed to parse issue url: $ISSUE_URL" >&2
  exit 1
fi

COMMENTS_EP="repos/${OWNER}/${REPO}/issues/${NUMBER}/comments?per_page=100"

HAS_MY="0"
if gh api "$COMMENTS_EP" >/dev/null 2>&1; then
  HAS_MY="$(gh api "$COMMENTS_EP" --jq 'map(select(.user.login == "'"$ME"'")) | length')"
else
  HAS_MY="0"
fi

if [ "${HAS_MY:-0}" -gt 0 ]; then
  gh issue comment "$ISSUE_URL" --body-file "$BODY_FILE" --edit-last
  echo "OK: edited last comment ($ME)"
else
  gh issue comment "$ISSUE_URL" --body-file "$BODY_FILE"
  echo "OK: created new comment ($ME)"
fi
