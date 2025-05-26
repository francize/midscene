import asyncio
import logging
import socketio
from typing import Any, Callable, Dict, Optional

from .common import (
    BridgeCallTimeout,
    BridgeEvent,
    BridgeErrorCodeNoClientConnected,
    BRIDGE_VERSION,
    DefaultBridgeServerPort,
)

logger = logging.getLogger("BridgeServer")

class BridgeServer:
    # Handles Socket.IO server-side logic for Chrome extension bridge.
    def __init__(
        self,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
    ):
        self.sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
        self.app = socketio.ASGIApp(self.sio)

        self.connected_socket_id: Optional[str] = None
        self.call_id_counter = 0
        self.pending_calls: Dict[str, asyncio.Future] = {}

        self._on_connect_cb = on_connect
        self._on_disconnect_cb = on_disconnect
        
        self._register_handlers()

    def _register_handlers(self):
        @self.sio.event
        async def connect(sid, environ):
            client_query = environ.get('QUERY_STRING', '')
            client_version = 'unknown'
            if 'version=' in client_query:
                try:
                    client_version = dict(qc.split('=') for qc in client_query.split('&')).get('version', 'unknown')
                except ValueError:
                    pass # Ignore malformed query string

            logger.info(f"Chrome extension client connected: sid={sid}, version={client_version}")
            
            if self.connected_socket_id is not None and self.connected_socket_id != sid:
                logger.warning(f"Existing client {self.connected_socket_id} connected, rejecting new connection {sid}")
                await self.sio.emit(BridgeEvent.Refused, {"reason": "Server already connected by another client"}, room=sid)
                await self.sio.disconnect(sid)
                return False # Reject connection

            self.connected_socket_id = sid
            
            if self._on_connect_cb:
                self._on_connect_cb()

            await self.sio.emit(BridgeEvent.Connected, {"version": BRIDGE_VERSION}, room=sid)
            logger.info(f"BridgeServer v{BRIDGE_VERSION} connected to client v{client_version} (sid: {sid})")

        @self.sio.event
        async def disconnect(sid):
            logger.info(f"Chrome extension client disconnected: {sid}")
            if self.connected_socket_id == sid:
                self.connected_socket_id = None
                for call_id, future in list(self.pending_calls.items()):
                    if not future.done():
                        future.set_exception(ConnectionAbortedError(f"Client {sid} disconnected. Call {call_id} aborted."))
                self.pending_calls.clear()
                if self._on_disconnect_cb:
                    self._on_disconnect_cb("Client disconnected")

        @self.sio.on(BridgeEvent.CallResponse)
        async def on_call_response(sid, data: Dict):
            logger.debug(f"Server received CallResponse from {sid}: {data}")
            call_id = data.get("id")
            response = data.get("response")
            error = data.get("error")

            if call_id in self.pending_calls:
                future = self.pending_calls.pop(call_id)
                if error:
                    future.set_exception(Exception(f"Chrome extension call error: {error}"))
                else:
                    future.set_result(response)
            else:
                logger.warning(f"Received unknown call response ID: {call_id}")
                
    async def close(self):
        logger.info("BridgeServer closing...")
        if self.connected_socket_id:
            await self.sio.disconnect(self.connected_socket_id)
            self.connected_socket_id = None

    async def call_on_browser(self, method: str, args: list = None, timeout: int = BridgeCallTimeout) -> Any:
        if self.connected_socket_id is None:
            raise ConnectionError(f"Cannot call '{method}': No Chrome extension client connected. ({BridgeErrorCodeNoClientConnected})")

        if args is None:
            args = []

        self.call_id_counter += 1
        call_id = str(self.call_id_counter)
        
        future = asyncio.get_running_loop().create_future()
        self.pending_calls[call_id] = future

        payload = {
            "id": call_id,
            "method": method,
            "args": args,
        }
        logger.debug(f"Server sending BridgeEvent.Call to {self.connected_socket_id}: {payload}")
        await self.sio.emit(BridgeEvent.Call, payload, room=self.connected_socket_id)

        try:
            return await asyncio.wait_for(future, timeout / 1000.0)
        except asyncio.TimeoutError:
            self.pending_calls.pop(call_id, None)
            logger.error(f"Call to browser method '{method}' (id: {call_id}) timed out.")
            raise TimeoutError(f"Call to browser method '{method}' (id: {call_id}) timed out.")
        except Exception as e:
            self.pending_calls.pop(call_id, None)
            raise e 