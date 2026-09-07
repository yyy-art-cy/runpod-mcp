# 基于 slim 基础镜像, 体积小、启动快
FROM python:3.12-slim

WORKDIR /app

# 非 root 用户运行 (容器卫生习惯)
RUN useradd --create-home --shell /bin/bash mcp

# 先装依赖再拷代码, 利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

USER mcp

# 与 server.py 中监听的端口保持一致
EXPOSE 8000

CMD ["python", "server.py"]
