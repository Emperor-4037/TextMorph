#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="${SCRIPT_DIR}/../models"
MODEL_FILE="${MODEL_DIR}/model.gguf"
HF_REPO="bartowski/Qwen2.5-7B-Instruct-GGUF"
HF_FILE="Qwen2.5-7B-Instruct-Q4_K_M.gguf"
DIRECT_URL="https://huggingface.co/${HF_REPO}/resolve/main/${HF_FILE}"

mkdir -p "${MODEL_DIR}"

if [ -f "${MODEL_FILE}" ]; then
    SIZE=$(du -h "${MODEL_FILE}" | cut -f1)
    echo "Model already exists at ${MODEL_FILE} (${SIZE})"
    echo "Delete it manually and re-run this script to re-download."
    exit 0
fi

echo "Downloading Qwen2.5-7B-Instruct Q4_K_M (~4.7 GB)..."
echo "Target: ${MODEL_FILE}"
echo ""

if command -v huggingface-cli &>/dev/null; then
    echo "Using huggingface-cli..."
    huggingface-cli download "${HF_REPO}" "${HF_FILE}" \
        --local-dir "${MODEL_DIR}" \
        --local-dir-use-symlinks False
    # Rename to model.gguf
    if [ -f "${MODEL_DIR}/${HF_FILE}" ]; then
        mv -f "${MODEL_DIR}/${HF_FILE}" "${MODEL_FILE}"
    fi
elif command -v curl &>/dev/null; then
    echo "Using curl..."
    curl -L -o "${MODEL_FILE}" "${DIRECT_URL}" --progress-bar
elif command -v wget &>/dev/null; then
    echo "Using wget..."
    wget -O "${MODEL_FILE}" "${DIRECT_URL}" --show-progress
else
    echo "Error: No download tool found. Install huggingface-cli, curl, or wget."
    exit 1
fi

if [ -f "${MODEL_FILE}" ]; then
    SIZE=$(du -h "${MODEL_FILE}" | cut -f1)
    echo ""
    echo "Download complete! (${SIZE})"
    echo "Model saved to: ${MODEL_FILE}"
else
    echo "Download failed!"
    exit 1
fi
