import asyncio
import logging
import socketio
from typing import Any, Callable, Dict, Optional, List

# 移除: from django.conf import settings

# 从 midscene_python_bridge/bridge_mode/common.py 借鉴事件名和常量
# (在实际项目中，这些常量可以放在一个共享的 common 模块中)
class BridgeEvent:
    Call = "bridge-call"
    CallResponse = "bridge-call-response"
    Connected = "bridge-connected"
    Refused = "bridge-refused"
    # Add other events from midscene_python_bridge.bridge_mode.common if needed

BRIDGE_VERSION = "0.1.0-fastapi" # 版本更新
BridgeCallTimeout = 30000  # 30秒
BridgeErrorCodeNoClientConnected = "no-client-connected"

logger = logging.getLogger('fastapi_extension_controller.socketio') # 更新 logger 名称

class SocketIOManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SocketIOManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, sio_server: Optional[socketio.AsyncServer] = None):
        if not hasattr(self, 'initialized'): # 防止重复初始化
            if sio_server:
                self.sio = sio_server
                logger.info(f"SocketIOManager using provided sio_server: {id(sio_server)}")
            else:
                # FastAPI 中，AsyncServer 通常在主应用中创建并传递进来，或者在这里创建
                # 但为了更好地集成，通常建议在 FastAPI 应用级别创建 sio 然后挂载
                self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
                logger.info(f"SocketIOManager created new sio_server: {id(self.sio)}")
            
            # FastAPI 中，ASGIApp 的挂载通常在主 app 文件中完成，这里不再需要 self.app
            # self.app = socketio.ASGIApp(self.sio, socketio_path='socket.io') 
            
            self.connected_socket_id: Optional[str] = None
            self.call_id_counter = 0
            self.pending_calls: Dict[str, asyncio.Future] = {}

            self._on_connect_cb: Optional[Callable[[str], None]] = None
            self._on_disconnect_cb: Optional[Callable[[str, str], None]] = None # sid, reason
            
            self._register_handlers()
            self.initialized = True
            logger.info(f"SocketIOManager initialized for FastAPI. Instance: {id(self)}, SIO: {id(self.sio)}")

    def _register_handlers(self):
        logger.info("Registering Socket.IO event handlers...")
        
        @self.sio.event
        async def connect(sid, environ, auth=None):
            client_query = environ.get('QUERY_STRING', '')
            client_version = 'unknown'
            if 'version=' in client_query:
                try:
                    client_version = dict(qc.split('=') for qc in client_query.split('&')).get('version', 'unknown')
                except ValueError:
                    pass

            logger.info(f"Chrome extension client attempting to connect: sid={sid}, version={client_version}, auth={auth}")
            logger.info(f"Current connected_socket_id: {self.connected_socket_id}")
            
            if self.connected_socket_id is not None and self.connected_socket_id != sid:
                logger.warning(f"Existing client {self.connected_socket_id} connected, rejecting new connection {sid}")
                await self.sio.emit(BridgeEvent.Refused, {"reason": "Server already connected by another client"}, room=sid)
                await self.sio.disconnect(sid)
                return False

            self.connected_socket_id = sid
            logger.info(f"Chrome extension client connected: sid={sid}")
            
            if self._on_connect_cb:
                self._on_connect_cb(sid)

            await self.sio.emit(BridgeEvent.Connected, {"version": BRIDGE_VERSION, "sid": sid}, room=sid)
            logger.info(f"SocketIOManager (FastAPI) v{BRIDGE_VERSION} connected to client v{client_version} (sid: {sid})")
            return True

        @self.sio.event
        async def disconnect(sid):
            logger.info(f"Chrome extension client disconnected: {sid}")
            if self.connected_socket_id == sid:
                self.connected_socket_id = None
                reason = "Client disconnected"
                for call_id, future in list(self.pending_calls.items()):
                    if not future.done():
                        future.set_exception(ConnectionAbortedError(f"Client {sid} disconnected. Call {call_id} aborted."))
                self.pending_calls.clear()
                if self._on_disconnect_cb:
                    self._on_disconnect_cb(sid, reason)
            else:
                logger.warning(f"Disconnected SID {sid} was not the active connected_socket_id ({self.connected_socket_id})")

        @self.sio.on(BridgeEvent.CallResponse)
        async def on_call_response(sid, data: Dict):
            logger.debug(f"SocketIOManager received CallResponse from {sid}: {data}")
            call_id = data.get("id")
            response = data.get("response")
            error = data.get("error")

            if call_id in self.pending_calls:
                future = self.pending_calls.pop(call_id)
                if not future.done():
                    if error:
                        future.set_exception(RuntimeError(f"Chrome extension call error: {error}"))
                    else:
                        future.set_result(response)
                else:
                    logger.warning(f"Future for call_id {call_id} was already done.")
            else:
                logger.warning(f"Received unknown call response ID: {call_id}")
        
        @self.sio.event
        async def ping_from_client(sid, data=None):
            logger.debug(f"Ping received from client {sid}, data: {data}")
            await self.sio.emit('pong_from_server', {'server_time': asyncio.get_event_loop().time()}, room=sid)
            
        logger.info("Socket.IO event handlers registered successfully")

    def set_connect_callback(self, callback: Callable[[str], None]):
        self._on_connect_cb = callback

    def set_disconnect_callback(self, callback: Callable[[str, str], None]):
        self._on_disconnect_cb = callback

    async def call_on_browser(self, method: str, args: Optional[List] = None, timeout: int = BridgeCallTimeout) -> Any:
        if self.connected_socket_id is None:
            logger.error(f"Cannot call '{method}': No Chrome extension client connected. ({BridgeErrorCodeNoClientConnected})")
            raise ConnectionError(f"Cannot call '{method}': No Chrome extension client connected. ({BridgeErrorCodeNoClientConnected})")

        args_list = args if args is not None else []
        self.call_id_counter += 1
        call_id = str(self.call_id_counter)
        
        loop = asyncio.get_running_loop() # Python 3.7+
        future = loop.create_future()
        self.pending_calls[call_id] = future

        payload = {
            "id": call_id,
            "method": method,
            "args": args_list,
        }
        logger.debug(f"SocketIOManager sending BridgeEvent.Call to {self.connected_socket_id}: {payload}")
        await self.sio.emit(BridgeEvent.Call, payload, room=self.connected_socket_id)

        try:
            return await asyncio.wait_for(future, timeout / 1000.0)
        except asyncio.TimeoutError:
            self.pending_calls.pop(call_id, None)
            logger.error(f"Call to browser method '{method}' (id: {call_id}) timed out after {timeout}ms.")
            raise TimeoutError(f"Call to browser method '{method}' (id: {call_id}) timed out after {timeout}ms.")
        except Exception as e:
            self.pending_calls.pop(call_id, None)
            logger.error(f"Error during call to browser method '{method}' (id: {call_id}): {e}", exc_info=True)
            raise

    def is_client_connected(self) -> bool:
        return self.connected_socket_id is not None

# 全局 SocketIOManager 实例的创建方式需要调整
# 在 FastAPI 中，我们通常在主应用模块创建 sio 实例，然后传递给 SocketIOManager
# 或者让 SocketIOManager 自己创建一个，然后 FastAPI 主应用获取这个 sio 实例并挂载

# 方案1: SocketIOManager 自己创建 sio (如下)，主应用再获取 sio 实例
# socket_manager = SocketIOManager()

# 方案2: 主应用创建 sio，然后传递给 SocketIOManager (更推荐的方式，以便主应用控制 AsyncServer 的创建)
# 例如，在 main.py:
# sio_server = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
# socket_manager = SocketIOManager(sio_server=sio_server)
# app.mount("/socket.io", socketio.ASGIApp(sio_server))

# 暂时采用方案1，如果后续需要更灵活控制，可以改为方案2
# 注意：如果采用这种方式，main.py 中需要从这里导入 socket_manager，并从中获取 .sio 实例来挂载。
# 为了简单起见，这里不立即实例化，而是在 main.py 中创建并传入。
# 因此，SocketIOManager 将期望在构造时传入一个 sio_server 实例。
# 如果没有传入，它会自己创建一个（这对于独立测试可能有用）。 