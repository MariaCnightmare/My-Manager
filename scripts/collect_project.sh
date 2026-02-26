#!/usr/bin/env bash
set -euo pipefail

OWNER="${OWNER:-@me}"
PROJECT_NUMBER="${PROJECT_NUMBER:-1}"
LIMIT="${LIMIT:-2000}"

mkdir -p data

gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" --format json -L "$LIMIT" > data/project_items.json

echo "OK: wrote data/project_items.json"
