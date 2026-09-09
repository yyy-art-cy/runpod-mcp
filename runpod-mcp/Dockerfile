# 基于 Ollama 官方镜像 (内置 CUDA + ollama 二进制)，叠加 Python 3 + MCP server。
# 容器启动后并行跑：ollama serve (11434) + uvicorn (8000)，
# 这样 Cherry Studio 既能通过 OpenAI 兼容端点调模型，又能通过 MCP 调工具。
#
# 构建上下文仅 ./runpod-mcp/
# 推送到: ghcr.io/<owner>/runpod-mcp/runpod-mcp:latest
FROM ollama/ollama:latest

# Ollama 镜像基于 Ubuntu 22.04，自带 python3 但需要装 pip
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装 Python 依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# 复制 MCP server 代码与启动脚本
COPY server.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Ollama 镜像默认用户 ollama (uid 1000)；保留其对 /app 与 ~/.ollama 的写权限
RUN mkdir -p /home/ollama/.ollama && chown -R ollama:ollama /app /home/ollama/.ollama
USER ollama

# MCP 在 8000，Ollama 在 11434
EXPOSE 8000 11434

# 默认启 Ollama + MCP server；可选通过 env OLLAMA_PRESET_MODELS=llama3.1:8b-instruct-fp16,... 预拉模型
ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_KEEP_ALIVE=10m \
    OLLAMA_MODELS=/home/ollama/.ollama/models \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]