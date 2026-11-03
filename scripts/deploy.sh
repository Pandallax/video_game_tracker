#!/usr/bin/env bash
# Polls origin/main for new commits and redeploys if found. Run from cron on the VM.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

git fetch origin main --quiet

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

echo "[$(date -Is)] New commits detected: $LOCAL -> $REMOTE"

CHANGED_FILES=$(git diff --name-only "$LOCAL" "$REMOTE")

git merge --ff-only origin/main

if echo "$CHANGED_FILES" | grep -q '^backend/'; then
  echo "[$(date -Is)] Backend changed, reinstalling deps and restarting service"
  (cd backend && ./.venv/bin/pip install -q -e .)
  sudo systemctl restart video-game-tracker-backend
fi

if echo "$CHANGED_FILES" | grep -q '^frontend/'; then
  echo "[$(date -Is)] Frontend changed, rebuilding"
  (cd frontend && npm ci --silent && npm run build)
fi

echo "[$(date -Is)] Deploy complete: now at $REMOTE"
