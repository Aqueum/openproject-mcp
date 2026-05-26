#!/usr/bin/env bash
# update-mcp.sh — rebuild and redeploy openproject-mcp on this host
# Run from the repo root: ./deploy/update-mcp.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE_NAME="openproject-mcp"
ARCHIVE="/tmp/${IMAGE_NAME}.tar"

echo "==> Building image..."
docker build -t "${IMAGE_NAME}" "${REPO_ROOT}"

echo "==> Saving image to archive..."
docker save -o "${ARCHIVE}" "${IMAGE_NAME}"

echo "==> Loading image (no-op on same host, useful for remote transfer)..."
docker load -i "${ARCHIVE}"

echo "==> Restarting services..."
cd "${REPO_ROOT}/deploy"
docker compose up -d --build

echo "==> Done. Check health:"
echo "    curl http://127.0.0.1:\${MCP_PORT:-8091}/healthz"
