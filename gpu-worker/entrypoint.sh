#!/usr/bin/env bash
set -euo pipefail

echo "[gpu-worker] Starting local ComfyUI server on 127.0.0.1:8188..."
python3 /opt/ComfyUI/main.py \
  --listen 127.0.0.1 \
  --port 8188 \
  --disable-auto-launch \
  > /tmp/comfyui.log 2>&1 &

COMFY_PID=$!
cleanup() {
  if kill -0 "${COMFY_PID}" 2>/dev/null; then
    kill "${COMFY_PID}" || true
  fi
}
trap cleanup EXIT

for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8188/system_stats > /dev/null; then
    echo "[gpu-worker] ComfyUI ready after ${i}s"
    break
  fi
  if ! kill -0 "${COMFY_PID}" 2>/dev/null; then
    echo "[gpu-worker] ComfyUI exited unexpectedly:"
    cat /tmp/comfyui.log
    exit 1
  fi
  sleep 1
done

python3 /worker/runner.py
