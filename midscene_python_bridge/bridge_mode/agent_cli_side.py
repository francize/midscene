"""Agent客户端代理实现，参考原TypeScript版本"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union, Callable
import uvicorn # 用于运行ASGI应用

from .common import (
    BridgeEvent,
    BridgeCallTimeout,
    DefaultBridgeServerPort
)
from .io_server import BridgeServer # 导入新的BridgeServer

logger = logging.getLogger("AgentBridge")

class AgentOverChromeBridge:
    """
    通过Chrome扩展桥接与浏览器页面交互的代理。
    这个Python类现在将启动一个Socket.IO服务器，等待Chrome扩展连接。
    """

    def __init__(
        self,
        port: int = DefaultBridgeServerPort,
        on_browser_connect: Optional[Callable[[], None]] = None, # 当浏览器连接时回调
        on_browser_disconnect: Optional[Callable[[str], None]] = None, # 当浏览器断开时回调
    ):
        self.port = port
        self._server_task: Optional[asyncio.Task] = None
        self._server_running = asyncio.Event() # 用于等待服务器实际启动
        self._uvicorn_server: Optional[uvicorn.Server] = None

        # 创建BridgeServer实例
        self._bridge_server = BridgeServer(
            port=self.port,
            on_connect=self._handle_browser_connect, # 内部处理函数
            on_disconnect=self._handle_browser_disconnect # 内部处理函数
        )
        
        self._user_on_browser_connect = on_browser_connect
        self._user_on_browser_disconnect = on_browser_disconnect
        
        self.connected = False # 指示浏览器是否已连接到我们的服务器

    def _handle_browser_connect(self):
        logger.info("Browser client connected to Python BridgeServer.")
        self.connected = True
        if self._user_on_browser_connect:
            self._user_on_browser_connect()

    def _handle_browser_disconnect(self, reason: str):
        logger.info(f"Browser client disconnected from Python BridgeServer. Reason: {reason}")
        self.connected = False
        if self._user_on_browser_disconnect:
            self._user_on_browser_disconnect(reason)

    async def start(self):
        """启动Socket.IO服务器并等待浏览器连接。"""
        if self._server_task and not self._server_task.done():
            logger.warning("Server is already running or starting.")
            return

        logger.info(f"Python BridgeServer正在端口 {self.port} 启动...")
        
        config = uvicorn.Config(
            self._bridge_server.app, 
            host="127.0.0.1", 
            port=self.port, 
            log_level="warning" # uvicorn自身的日志级别，可以调整
        )
        self._uvicorn_server = uvicorn.Server(config)

        # 在一个任务中运行Uvicorn服务器，这样start可以是非阻塞的
        # 或者，如果希望start阻塞直到服务器停止，可以直接await self._uvicorn_server.serve()
        # 这里我们选择非阻塞启动，并用事件来同步
        
        async def serve():
            try:
                self._server_running.set() # 通知服务器已配置并即将启动
                await self._uvicorn_server.serve()
                logger.info("Python BridgeServer已停止.")
            except Exception as e:
                logger.error(f"Python BridgeServer 运行错误: {e}", exc_info=True)
            finally:
                self._server_running.clear()
                self.connected = False # 确保服务器停止后连接状态为False

        self._server_task = asyncio.create_task(serve())
        # 可以选择等待服务器真正开始监听，但这对于uvicorn有点复杂
        # uvicorn.Server.serve() 本身会阻塞直到服务器停止
        # 我们通过 self._server_running.wait() 来确保 serve() 至少已经开始执行
        await self._server_running.wait() 
        logger.info(f"Python BridgeServer应该已在 http://127.0.0.1:{self.port} 上运行")

    async def close(self):
        """关闭Socket.IO服务器。"""
        logger.info("正在关闭Python BridgeServer...")
        await self._bridge_server.close() # 首先尝试关闭BridgeServer内部逻辑（例如断开客户端）
        
        if self._uvicorn_server:
            # Uvicorn 服务器的优雅关闭
            self._uvicorn_server.should_exit = True 

        if self._server_task:
            if not self._server_task.done():
                try:
                    # 等待服务器任务完成 (Uvicorn停止)
                    await asyncio.wait_for(self._server_task, timeout=5.0) 
                except asyncio.TimeoutError:
                    logger.warning("关闭服务器任务超时，可能需要手动停止进程。")
                    self._server_task.cancel() # 如果超时则尝试取消
                except Exception as e:
                    logger.error(f"关闭服务器任务时发生错误: {e}")
            self._server_task = None
        
        self.connected = False
        logger.info("Python BridgeServer已关闭。")

    async def call(
        self, 
        method: str, 
        args: list = None, 
        timeout: int = BridgeCallTimeout
    ) -> Any:
        """在连接的Chrome浏览器中执行方法。"""
        if not self.connected:
            # 在TS版本中，如果未连接，call会尝试连接。
            # 在这个服务器模式下，我们需要浏览器主动连接到我们。
            # 所以如果Python服务器已启动但浏览器未连接，则调用应该失败。
            raise ConnectionError(
                "无法执行调用：Chrome浏览器未连接到Python BridgeServer。请确保浏览器扩展已启用并处于Bridge模式。"
            )
        
        # 使用BridgeServer的call_on_browser方法
        return await self._bridge_server.call_on_browser(method, args, timeout)

    # 保持与PageCliSide类似API的其他方法（如果需要的话）
    async def get_url(self, timeout: int = BridgeCallTimeout) -> str:
        return await self.call("url", timeout=timeout)

    async def get_title(self, timeout: int = BridgeCallTimeout) -> str:
        # evaluateJavaScript returns a more complex object
        response = await self.call("evaluateJavaScript", ["document.title"], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
            return response["result"].get("value", "")
        logger.warning(f"Could not parse title from response: {response}")
        return ""

    async def navigate(self, url: str, timeout: int = BridgeCallTimeout):
        js_code = f"window.location.href = '{url}';"
        # navigate doesn't typically return a meaningful value from evaluateJavaScript
        await self.call("evaluateJavaScript", [js_code], timeout=timeout)

    async def version(self, timeout: int = BridgeCallTimeout) -> str:
        # __VERSION__ is declared in the extension's context
        # This assumes evaluateJavaScript can access it.
        response = await self.call("evaluateJavaScript", ["__VERSION__"], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
            return response["result"].get("value", "unknown")
        logger.warning(f"Could not parse version from response: {response}")
        return "unknown"

    async def take_screenshot(self, timeout: int = BridgeCallTimeout) -> str:
        """获取页面截图（返回base64编码的图片数据）"""
        # screenshotBase64 is expected to return the base64 string directly
        return await self.call("screenshotBase64", timeout=timeout)

    async def get_content(self, timeout: int = BridgeCallTimeout) -> str:
        """获取页面HTML内容"""
        response = await self.call("evaluateJavaScript", ["document.documentElement.outerHTML"], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
            return response["result"].get("value", "")
        logger.warning(f"Could not parse content from response: {response}")
        return ""

    async def evaluate(self, js_code: str, timeout: int = BridgeCallTimeout) -> Any:
        """在页面上下文中执行JavaScript代码"""
        # The raw response from evaluateJavaScript might be complex.
        # For a generic evaluate, returning the somewhat raw "result" part might be best,
        # or the user might expect the direct "value" if simple.
        # Let's try to return result.value if available, else the result object.
        response = await self.call("evaluateJavaScript", [js_code], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response:
            if isinstance(response["result"], dict) and "value" in response["result"]:
                return response["result"]["value"]
            return response["result"] # Return the content of "result" if "value" is not present
        logger.warning(f"Could not parse evaluate from response: {response}")
        return None

    async def connect_new_tab_with_url(self, url: str, timeout: int = BridgeCallTimeout) -> bool:
        """指示Chrome扩展打开一个新标签页并导航到指定URL，并将其与当前桥接会话关联。"""
        success = False
        try:
            logger.info(f"尝试调用 connectNewTabWithUrl, URL: {url}")
            await self.call("connectNewTabWithUrl", [url], timeout=timeout)
            logger.info(f"命令 connectNewTabWithUrl 已发送。")
            await asyncio.sleep(3)
            success = True
        except Exception as e:
            logger.error(f"调用 connectNewTabWithUrl 失败: {e}", exc_info=False)

        if not success:
            logger.warning(f"connect_new_tab_with_url: 无法通过 connectNewTabWithUrl 初始化新标签页: {url}。后续页面操作可能因此失败。")
        
        return success

    # ... (可以添加更多快捷方法，如 take_screenshot, content 等)

# 注意：旧的 PageCliSide 和 BridgeClient 不再直接由此类使用。
# 这个类现在是服务器端。 