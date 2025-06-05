import asyncio
import logging
import json
from typing import Dict, Any, Optional

import socketio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware # 用于处理跨域
from pydantic import BaseModel # 导入 BaseModel

from socketio_manager import SocketIOManager, BridgeEvent, BridgeErrorCodeNoClientConnected, BRIDGE_VERSION

# --- 日志配置 ---
# 可以将日志配置移到单独的文件 logging_config.py 中，如果配置变得复杂
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_extension_controller.main")

# --- FastAPI 应用实例 ---
app = FastAPI(
    title="FastAPI Extension Controller",
    description="A bridge service between MCP and Chrome Extension via Socket.IO",
    version=BRIDGE_VERSION
)

# --- CORS 中间件 (如果你的 MCP 服务和此服务不在同源) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应配置为具体的源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Socket.IO 服务器实例 ---
# python-socketio AsyncServer
sio_server = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*' # 根据需要调整CORS策略
)
logger.info(f"Created Socket.IO AsyncServer: {id(sio_server)}")

# --- Socket.IO 管理器实例 ---
# 将 sio_server 传递给 SocketIOManager
socket_manager = SocketIOManager(sio_server=sio_server)
logger.info(f"Created SocketIOManager: {id(socket_manager)}")

# --- 将 Socket.IO ASGI 应用挂载到 FastAPI 应用 ---
# socketio_path='socket.io' 是标准的 Socket.IO 路径
socketio_asgi_app = socketio.ASGIApp(sio_server, socketio_path='socket.io')
app.mount("/socket.io", socketio_asgi_app)
logger.info(f"Mounted Socket.IO ASGI app at /socket.io, app: {id(socketio_asgi_app)}")

# --- 请求/响应日志中间件 (FastAPI 方式) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = asyncio.get_event_loop().time()
    request_log_data = {
        'method': request.method,
        'url': str(request.url),
        'headers': dict(request.headers), # 请求头通常比较规范，直接 dict() 问题不大
    }
    # body = await request.body() # 避免重复读取body
    # if body:
    #     try:
    #         request_log_data['body'] = json.loads(body.decode('utf-8'))
    #     except json.JSONDecodeError:
    #         request_log_data['body'] = body.decode('utf-8', errors='replace')
    
    logger.info(f"Request received: {json.dumps(request_log_data)}")
    
    response = await call_next(request)
    
    duration = asyncio.get_event_loop().time() - start_time
    
    # 安全地转换响应头
    response_headers_dict = {k.lower(): v for k, v in response.headers.items()}

    response_log_data = {
        'status_code': response.status_code,
        'headers': response_headers_dict, # 使用安全转换后的字典
        'duration_ms': round(duration * 1000, 2)
    }
    
    # response_body_bytes = await response.body() # 同样，读取响应体需要小心
    # if response_body_bytes:
    #     try:
    #         response_log_data['body'] = json.loads(response_body_bytes.decode('utf-8'))
    #     except json.JSONDecodeError:
    #         response_log_data['body'] = response_body_bytes.decode('utf-8', errors='replace')
    
    logger.info(f"Response sent: {json.dumps(response_log_data)}")
    return response

# --- API 端点 --- 
API_PREFIX = "/controller/api"

# 将 CommandPayload 修改为 Pydantic 模型
class CommandPayload(BaseModel):
    username: Optional[str] = None  # Pydantic 中可选字段建议提供默认值
    action: str
    params: Optional[Dict[str, Any]] = {} # Pydantic 中可选字典建议提供默认空字典

@app.post(f"{API_PREFIX}/execute", tags=["Commands"])
async def execute_command_view(payload: CommandPayload): # 现在 payload 会被正确解析为 Pydantic 模型
    logger.info(f"Received command from MCP service: {payload.model_dump()}") # 使用 Pydantic 的 .model_dump()

    action = payload.action
    params = payload.params if payload.params is not None else {}

    if not action:
        logger.error("'action' field is missing in request from MCP service")
        raise HTTPException(status_code=400, detail={"success": False, "error": "Missing 'action' field"})

    if not socket_manager.is_client_connected():
        logger.warning(f"Cannot execute action '{action}': Chrome extension client not connected.")
        raise HTTPException(status_code=503, detail={"success": False, "error": "Chrome extension client not connected."})

    method_to_call_on_browser: Optional[str] = None
    args_for_browser: list = []

    # 与 Django 版本类似的 action/params 映射逻辑
    if action == "click" or action == "aiTap": # Allow "click" for backward compatibility or specific use, and "aiTap" for clarity
        method_to_call_on_browser = "aiTap" # Directly use the string 'aiTap'
        
        natural_language_prompt = params.get('selector') or params.get('prompt') # Accept 'selector' or 'prompt' for the text
        if not natural_language_prompt:
            raise HTTPException(status_code=400, detail={"success": False, "error": "Missing 'selector' or 'prompt' for aiTap action"})
        
        # The Chrome extension's PageAgent.aiTap expects the prompt directly.
        # The ExtensionBridgePageBrowserSide's onBridgeCall for AiTap expects a single string argument.
        args_for_browser = [natural_language_prompt]

    elif action == "getPageContent":
        method_to_call_on_browser = "getPageContent"
        include_screenshot = params.get('includeScreenshot', False)
        args_for_browser = [{"includeScreenshot": include_screenshot}]

    elif action == "version":
        method_to_call_on_browser = "version"
        args_for_browser = []

    elif action == "evaluateJavaScript":
        method_to_call_on_browser = "evaluateJavaScript"
        script = params.get('script')
        if not script:
            raise HTTPException(status_code=400, detail={"success": False, "error": "Missing 'script' for evaluateJavaScript action"})
        args_for_browser = [script]
    
    elif action == "connectNewTabWithUrl" or action == "navigate":
        method_to_call_on_browser = "connectNewTabWithUrl"
        url = params.get('url')
        if not url:
            raise HTTPException(status_code=400, detail={"success": False, "error": "Missing 'url' for connectNewTabWithUrl action"})
        args_for_browser = [url]
        
    # ... 在此添加更多 action 映射 ...

    else:
        logger.warning(f"Unknown action '{action}' received from MCP service.")
        raise HTTPException(status_code=400, detail={"success": False, "error": f"Unknown action: {action}"})

    try:
        logger.info(f"Calling browser method '{method_to_call_on_browser}' with args: {args_for_browser}")
        result = await socket_manager.call_on_browser(method_to_call_on_browser, args_for_browser)
        logger.info(f"Result from browser for action '{action}': {result}")
        return JSONResponse(content={"success": True, "data": result})
    
    except ConnectionError as e:
        logger.error(f"ConnectionError while calling browser for action '{action}': {e}")
        raise HTTPException(status_code=503, detail={"success": False, "error": str(e)})
    except TimeoutError as e:
        logger.error(f"TimeoutError while calling browser for action '{action}': {e}")
        raise HTTPException(status_code=504, detail={"success": False, "error": str(e)})
    except RuntimeError as e: 
        error_message = str(e)
        logger.error(f"RuntimeError from browser for action '{action}': {error_message}")
        
        # 检查是否是 "no tab is connected" 错误
        if "no tab is connected" in error_message.lower():
            detailed_error = {
                "success": False, 
                "error": "Chrome extension error: No tab is connected",
                "details": "The Chrome extension is connected but no browser tab is available for automation. Please ensure:",
                "suggestions": [
                    "1. Open a browser tab in Chrome",
                    "2. Make sure the extension has permission to access the tab",
                    "3. Try refreshing the page if the extension was recently installed",
                    "4. Use the /controller/api/open-tab endpoint to open a new tab first"
                ],
                "original_error": error_message
            }
            raise HTTPException(status_code=422, detail=detailed_error)  # 422 Unprocessable Entity
        else:
            raise HTTPException(status_code=500, detail={"success": False, "error": error_message})
    except Exception as e:
        logger.error(f"Unexpected error calling browser for action '{action}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"success": False, "error": f"An unexpected error occurred: {str(e)}"})

@app.get("/controller/health", tags=["Health"])
async def health_check_view():
    client_connected = socket_manager.is_client_connected()
    return JSONResponse(content={
        "status": "ok", 
        "service": "FastAPI Extension Controller",
        "socketio_client_connected": client_connected,
        "socketio_sid": socket_manager.connected_socket_id if client_connected else None
    })

@app.get("/controller/extension-status", tags=["Health"])
async def extension_status_view():
    """检查 Chrome 扩展的详细状态"""
    if not socket_manager.is_client_connected():
        return JSONResponse(content={
            "success": False,
            "error": "Chrome extension not connected to Socket.IO server",
            "socketio_connected": False
        }, status_code=503)
    
    try:
        # 尝试调用扩展的状态检查方法
        result = await socket_manager.call_on_browser("getStatus", [], timeout=5000)
        return JSONResponse(content={
            "success": True,
            "socketio_connected": True,
            "extension_status": result
        })
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "socketio_connected": True,
            "error": f"Failed to get extension status: {str(e)}"
        }, status_code=500)

@app.post("/controller/api/open-tab", tags=["Commands"])
async def open_tab_view(payload: dict):
    """打开一个新标签页并导航到指定URL，同时建立连接"""
    if not socket_manager.is_client_connected():
        raise HTTPException(status_code=503, detail={"success": False, "error": "Chrome extension client not connected."})
    
    url = payload.get('url', 'about:blank')
    
    try:
        # 使用 connectNewTabWithUrl 而不是 openTab，这样可以同时打开标签页、导航和建立连接
        result = await socket_manager.call_on_browser("connectNewTabWithUrl", [url])
        return JSONResponse(content={"success": True, "data": result})
    except Exception as e:
        logger.error(f"Error opening and connecting to tab: {e}")
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})

# --- Uvicorn 启动 (如果直接运行此文件) ---
if __name__ == "__main__":
    import uvicorn
    # 端口 3766 与你的要求一致
    # 日志级别等可以通过 uvicorn 参数或 FastAPI 的 log_config 进行更细致的控制
    uvicorn.run(app, host="0.0.0.0", port=3766, log_level="info") 