#!/usr/bin/env bash
# Rebuild the CI replay caches with one live dev run over the fixture pages.
# Uses a separate database (rag_ci) so the real index is untouched, and fresh cache files so
# only entries this run needs are committed. Costs a few cents of DeepSeek calls.
# Usage: scripts/build_ci_cache.sh   (needs the local Postgres from docker compose on :5433,
# the embed extra installed and DEEPSEEK_API_KEY in .env)
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${CI_BUILD_DB_BASE:-postgresql://rag:rag@localhost:5433}
psql "$BASE/rag" -qc "DROP DATABASE IF EXISTS rag_ci" -c "CREATE DATABASE rag_ci"
export DATABASE_URL="$BASE/rag_ci"
rm -rf ci/fixtures/llm_cache ci/fixtures/embed_cache.sqlite
export EMBED_PROVIDER=local EMBED_CACHE_PATH=ci/fixtures/embed_cache.sqlite
export LLM_PROVIDER=live LLM_CACHE_DIR=ci/fixtures/llm_cache
.venv/bin/python -m src.ingest --fixtures ci/fixtures/docs --sizes 500
.venv/bin/python -m src.evaluate --split dev --name ci-dev
