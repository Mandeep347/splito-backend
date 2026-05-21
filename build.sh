#!/usr/bin/env bash
# Render build script — runs on every deploy
set -e  # exit immediately on any error

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Running database migrations ==="
alembic upgrade head

echo "=== Build complete ==="