# FastAPI Extension Controller

这个 FastAPI 项目作为 Chrome 扩展和后端服务 (例如 MCP 服务) 之间的桥梁。
它通过 Socket.IO 与 Chrome 扩展通信，并提供 HTTP API 端点供后端服务调用。

## 主要功能

-   接收来自后端服务的 HTTP 请求 (例如，来自 `west/midscene_mcp_plugin`)
-   通过 Socket.IO 将指令转发给已连接的 Chrome 扩展
-   将 Chrome 扩展的执行结果返回给后端服务
-   详细的请求/响应日志记录 (通过中间件或日志配置)

## 项目结构

-   `main.py`: FastAPI 应用主文件，包含 API 端点和 Socket.IO 集成。
-   `socketio_manager.py`: Socket.IO 服务器逻辑，管理与 Chrome 扩展的连接和通信。
-   `requirements.txt`: 项目依赖。
-   `README.md`: 本文档。

## 设置与运行

1.  **创建并激活虚拟环境** (推荐):
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate    # Windows
    ```

2.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行服务**:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 3766 --reload
    ```
    这会启动 FastAPI 应用，并通过 Uvicorn 监听 `0.0.0.0:3766`。Socket.IO 服务也会在此端口上可用 (通常在 `/socket.io/` 路径)。
    `--reload` 选项可以在开发时代码更改后自动重载服务。

## API 端点

-   **POST** `/controller/api/execute`
    -   接收来自 MCP 服务的指令。
    -   请求体示例:
        ```json
        {
            "username": "user123",
            "action": "navigate",
            "params": {"url": "https://example.com"}
        }
        ```
    -   成功时返回: `{"success": true, "data": "..."}`
    -   失败时返回: `{"success": false, "error": "..."}`

-   **GET** `/controller/health`
    -   健康检查端点。
    -   返回: `{"status": "ok", "service": "FastAPI Extension Controller", "socketio_client_connected": true/false, "socketio_sid": "..."}`

## Chrome 扩展集成

Chrome 扩展应配置为连接到此 FastAPI 服务的 Socket.IO 端点 (例如 `ws://localhost:3766/socket.io/`)。
扩展需要处理 `bridge-call` 事件并发送 `bridge-call-response` 事件。 