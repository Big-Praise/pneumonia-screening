#!/usr/bin/env bash
# Stage exactly the files the Hugging Face Space needs into $1 (default: deploy/.space).
# Uploading a staged folder (not the repo) guarantees no model weights, database,
# uploads, tests, frontend or local config ever reach the Space.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/deploy/.space}"
rm -rf "${OUT:?}"
mkdir -p "$OUT/api"
cp "$ROOT/Dockerfile" "$ROOT/requirements-api.txt" "$OUT/"
cp "$ROOT/deploy/space-README.md" "$OUT/README.md"
for f in "$ROOT"/*.py; do
  case "$(basename "$f")" in app.py) ;; *) cp "$f" "$OUT/" ;; esac   # app.py = Streamlit UI, not needed
done
cp "$ROOT"/api/*.py "$OUT/api/"
echo "Staged Space files in $OUT:"
(cd "$OUT" && find . -type f | sort)
