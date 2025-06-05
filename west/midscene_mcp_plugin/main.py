 # main.py
from starlette.applications import Starlette
from starlette.routing import Mount
from server import mcp  # 引入你在 server.py 中创建的 MCP 实例

# 使用 Starlette 挂载 SSE 服务
app = Starlette(
    routes=[
        Mount("/", app=mcp.sse_app())
    ]
)