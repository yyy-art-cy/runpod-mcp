#!/bin/bash
# RunPod MCP + Ollama 启动脚本
# - 后台启动 ollama serve (11434)
# - 可选预拉模型（env: OLLAMA_PRESET_MODELS=llama3.1:8b-instruct-fp16,qwen2.5:14b）
# - 前台启动 MCP server (8000)
#
# 关键: 任意子进程崩溃 → 容器整体退出 → RunPod 标记 pod 异常，避免假死
set -euo pipefail

log() { echo "[entrypoint $(date +%H:%M:%S)] $*"; }

log "OLLAMA_HOST=${OLLAMA_HOST:-0.0.0.0:11434}"
log "AUTH_TOKEN set: $([ -n "${AUTH_TOKEN:-}" ] && echo yes || echo NO)"

# 启动 Ollama（后台），健康检查最多等 60s
log "starting ollama serve ..."
OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}" ollama serve >/tmp/ollama.log 2>&1 &
OLLAMA_PID=$!
log "ollama pid=$OLLAMA_PID"

cleanup() {
        log "received signal, shutting down ..."
        kill -TERM "$OLLAMA_PID" 2>/dev/null || true
        wait "$OLLAMA_PID" 2>/dev/null || true
        exit 0
}
trap cleanup TERM INT

# 等 Ollama 健康
for i in $(seq 1 60); do
        if curl -sS --max-time 2 "${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
                log "ollama ready (took ${i}s)"
                break
        fi
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
                log "FATAL: ollama died early, log tail:"
                tail -30 /tmp/ollama.log
                exit 1
        fi
        sleep 1
done

# 预拉模型（如果配置了）
if [ -n "${OLLAMA_PRESET_MODELS:-}" ]; then
        IFS=',' read -ra MODELS <<< "$OLLAMA_PRESET_MODELS"
        for m in "${MODELS[@]}"; do
                m="$(echo "$m" | xargs)"
                [ -z "$m" ] && continue
                log "pulling model: $m"
                if ! ollama pull "$m"; then
                        log "WARN: failed to pull $m, continuing"
                fi
        done
fi

# 安全闸: AUTH_TOKEN 必填，否则 server.py 会退出
if [ -z "${AUTH_TOKEN:-}" ]; then
        log "FATAL: AUTH_TOKEN env not set"
        exit 1
fi

log "starting MCP server on :8000 ..."
exec python3 /app/server.py