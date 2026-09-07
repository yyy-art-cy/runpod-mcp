#!/usr/bin/env python3
"""自定义 MCP Server 模板 —— 部署到 RunPod GPU Pod。

对外以 stateless streamable-http 模式提供 /mcp 端点，适配 RunPod 反向代理
以及 WorkBuddy / Claude / Cursor / Windsurf 等 MCP 客户端。

扩展方式：
    1. 在 @mcp.tool() 函数里添加业务逻辑（如加载模型做推理）。
    2. 在 Dockerfile / requirements.txt 里安装 PyTorch / CUDA 等依赖。

环境变量：
    HOST  : 监听地址，默认 0.0.0.0
    PORT  : 监听端口，默认 8000
"""

import os
import subprocess

from mcp.server.fastmcp import FastMCP

# -------------- MCP 工具定义 --------------

mcp = FastMCP(
    "my-runpod-mcp",
    stateless_http=True,  # 无会话状态，适合反向代理 / 多副本
    json_response=True,   # 纯 JSON 响应，比 SSE 更省资源
)


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


# -------------- 启动入口 --------------

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
