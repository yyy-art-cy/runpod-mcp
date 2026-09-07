#!/usr/bin/env python3
"""自定义 MCP Server（mcp Python SDK 2.x / MCPServer）—— 部署到 RunPod GPU Pod。

对外以 stateless streamable-http 模式提供 /mcp 端点，适配 RunPod 反向代理
以及 WorkBuddy / Claude / Cursor / Windsurf 等 MCP 客户端。

⚠️ 安全：本服务要求环境变量 AUTH_TOKEN 非空，所有请求必须带
   `Authorization: Bearer <AUTH_TOKEN>` 头，否则返回 401。
   未设置 AUTH_TOKEN 时服务拒绝启动（fail-closed），防止误配公网裸奔。

扩展方式：
    1. 在 @mcp.tool() 函数里添加业务逻辑（如加载模型做推理）。
    2. 在 Dockerfile / requirements.txt 里安装 PyTorch / CUDA 等依赖。

环境变量：
    AUTH_TOKEN : 必填。Bearer 访问令牌，客户端请求头需携带。
    HOST       : 监听地址，默认 0.0.0.0
    PORT       : 监听端口，默认 8000
"""

import hmac
import os
import subprocess
import sys

import uvicorn
from mcp.server.mcpserver import MCPServer

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "").strip()
if not AUTH_TOKEN:
    sys.stderr.write(
        "[FATAL] 环境变量 AUTH_TOKEN 未设置。为安全起见服务拒绝启动。\n"
        "  请在 RunPod Pod 的 Environment Variables 里配置 AUTH_TOKEN 后再启动。\n"
    )
    sys.exit(1)

# -------------- MCP 工具定义 --------------

mcp = MCPServer(name="my-runpod-mcp")


@mcp.tool()
def echo(text: str) -> str:
    """回显文本，用于验证 MCP 通道是否连通。"""
    return text


@mcp.tool()
def gpu_status() -> str:
    """返回当前 Pod 上 nvidia-smi 的输出，验证 GPU 是否可用。"""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout or result.stderr or "nvidia-smi 无输出"
    except Exception as exc:  # noqa: BLE001
        return f"执行 nvidia-smi 失败: {exc}"


# -------------- 鉴权中间件 + 启动入口 --------------

def make_app():
    """构建 Starlette app 并包一层 Bearer Token 鉴权中间件。"""
    inner = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,   # 纯 JSON 响应，比 SSE 更省资源
        stateless_http=True,  # 无会话状态，适合反向代理 / 多副本
        host=HOST,
    )
    expected = AUTH_TOKEN.encode("utf-8")

    async def auth_middleware(scope, receive, send):
        if scope["type"] != "http":
            await inner(scope, receive, send)
            return

        authorized = False
        for key, value in scope.get("headers") or []:
            if key.lower() == b"authorization":
                scheme, _, credential = value.partition(b" ")
                if scheme.lower() == b"bearer" and hmac.compare_digest(credential, expected):
                    authorized = True
                break

        if authorized:
            await inner(scope, receive, send)
            return

        body = b'{"error": "unauthorized"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return auth_middleware


if __name__ == "__main__":
    uvicorn.run(make_app(), host=HOST, port=PORT, log_level="info")
