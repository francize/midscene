import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any, Dict, List

from mcp import server as mcp_server
from mcp import types as mcp_types

from browser_bridge.agent_cli_side import AgentOverChromeBridge

logger = logging.getLogger("MCPService")

class MCPMidSceneService:
    def __init__(self):
        self.mcp_server = mcp_server.Server(
            server_id="midscene-browser-mcp-service",
            lifespan=self.service_lifespan
        )
        self.browser_agent: Optional[AgentOverChromeBridge] = None
        self._register_mcp_tools()

    @asynccontextmanager
    async def service_lifespan(self, server: mcp_server.Server) -> AsyncIterator[Dict[str, Any]]:
        """Manage MCP service startup and shutdown lifecycle."""
        logger.info("MCP Service Lifespan: Initializing...")
        self.browser_agent = AgentOverChromeBridge(
            on_browser_connect=self._handle_browser_connect_status,
            on_browser_disconnect=self._handle_browser_disconnect_status
        )
        # The Socket.IO server part of browser_agent starts when its ASGI app is run.
        # No explicit start needed here for browser_agent itself.
        logger.info("AgentOverChromeBridge initialized within MCP service.")
        try:
            yield {"browser_agent": self.browser_agent, "mcp_instance": self}
        finally:
            logger.info("MCP Service Lifespan: Shutting down...")
            if self.browser_agent:
                await self.browser_agent.close()
                logger.info("AgentOverChromeBridge closed.")
            self.browser_agent = None
            logger.info("MCP Service Lifespan: Shutdown complete.")

    def _handle_browser_connect_status(self):
        logger.info("MCP Service notified: Browser connected.")
        # Here you could emit an MCP notification if desired, e.g., for client status updates

    def _handle_browser_disconnect_status(self, reason: str):
        logger.warning(f"MCP Service notified: Browser disconnected. Reason: {reason}")
        # Here you could emit an MCP notification if desired

    def _get_agent_from_context(self) -> AgentOverChromeBridge:
        ctx = self.mcp_server.get_context()
        agent = ctx.lifespan_context.get("browser_agent")
        if not agent or not isinstance(agent, AgentOverChromeBridge):
            raise RuntimeError("Browser agent not available in MCP context or incorrect type.")
        if not agent.is_connected:
            raise ConnectionError("Browser agent is not connected to the Chrome extension.")
        return agent

    def _register_mcp_tools(self):
        @self.mcp_server.call_tool()
        async def connect_new_tab_with_url(url: str, timeout: int = 30) -> Dict[str, Any]:
            logger.info(f"MCP Tool: connect_new_tab_with_url called with URL: {url}, timeout: {timeout}s")
            agent = self._get_agent_from_context()
            try:
                success = await agent.connect_new_tab_with_url(url, timeout * 1000) # agent uses ms
                return {"success": success, "url": url}
            except ConnectionError as ce:
                logger.error(f"ConnectionError in connect_new_tab_with_url: {ce}")
                return {"success": False, "error": str(ce), "details": "Browser not connected."}
            except TimeoutError as te:
                logger.error(f"TimeoutError in connect_new_tab_with_url: {te}")
                return {"success": False, "error": str(te), "details": f"Timeout connecting to {url}"}
            except Exception as e:
                logger.error(f"Error in connect_new_tab_with_url: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.mcp_server.call_tool()
        async def version() -> Dict[str, Any]:
            logger.info("MCP Tool: version called")
            agent = self._get_agent_from_context()
            try:
                ext_version = await agent.version()
                return {"extension_version": ext_version, "service_version": "0.1.0"}
            except ConnectionError as ce:
                logger.error(f"ConnectionError in version: {ce}")
                return {"error": str(ce), "details": "Browser not connected."}
            except Exception as e:
                logger.error(f"Error in version: {e}", exc_info=True)
                return {"error": str(e)}

        @self.mcp_server.call_tool()
        async def close_tab() -> Dict[str, Any]:
            logger.info("MCP Tool: close_tab called")
            agent = self._get_agent_from_context()
            try:
                result = await agent.close_tab()
                return {"success": True, "details": result if result else "Tab closed"}
            except ConnectionError as ce:
                logger.error(f"ConnectionError in close_tab: {ce}")
                return {"success": False, "error": str(ce), "details": "Browser not connected."}
            except Exception as e:
                logger.error(f"Error in close_tab: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.mcp_server.call_tool()
        async def get_tab_content() -> Dict[str, Any]:
            logger.info("MCP Tool: get_tab_content called")
            agent = self._get_agent_from_context()
            try:
                content = await agent.get_tab_content()
                return content
            except ConnectionError as ce:
                logger.error(f"ConnectionError in get_tab_content: {ce}")
                return {"error": str(ce), "details": "Browser not connected."}
            except Exception as e:
                logger.error(f"Error in get_tab_content: {e}", exc_info=True)
                return {"error": str(e)}

    def sse_app(self):
        """Returns the MCP SSE ASGI application."""
        return self.mcp_server.create_sse_app()

    def get_socketio_app(self):
        """Returns the Socket.IO ASGI application from the browser agent."""
        if not self.browser_agent:
            # This should ideally not happen if lifespan management is correct
            logger.error("Attempted to get Socket.IO app before browser_agent is initialized.")
            # Fallback or raise critical error
            self.browser_agent = AgentOverChromeBridge() # Emergency init, may not be fully configured
        return self.browser_agent.sio_app

# Global instance of the service
mcp_service = MCPMidSceneService() 