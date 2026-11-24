#!/usr/bin/env bash
# Deploy demo/dist to Vercel. Usage: vercel-deploy.sh preview|production
# Skips (successfully) when the Vercel secrets are not configured, e.g. on
# pull requests from forks.
set -euo pipefail

if [ -z "${VERCEL_TOKEN:-}" ] || [ -z "${VERCEL_ORG_ID:-}" ] || [ -z "${VERCEL_PROJECT_ID:-}" ]; then
    echo "Vercel secrets are not set; skipping deployment." | tee -a "$GITHUB_STEP_SUMMARY"
    exit 0
fi

case "$1" in
    production) flags=(--prod); label="Production" ;;
    preview)    flags=();       label="Preview" ;;
    *) echo "usage: $0 preview|production" >&2; exit 2 ;;
esac

url=$(npx --yes vercel@latest deploy demo/dist "${flags[@]}" --yes --token "$VERCEL_TOKEN")
echo "$label deployment: $url" | tee -a "$GITHUB_STEP_SUMMARY"
