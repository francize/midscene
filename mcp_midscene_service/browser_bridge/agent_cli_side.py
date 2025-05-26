"""Agent客户端代理实现，专为MCP服务定制"""

import asyncio
import logging
from typing import Any, Optional, Callable, Dict, Union

from .common import (
    BridgeEvent,
    BridgeCallTimeout,
)
from .io_server import BridgeServer
from .types import WebUIContext # Keep only used types

logger = logging.getLogger("AgentBridge")

class AgentOverChromeBridge:
    """
    Manages communication with a MidScene Chrome Extension via Socket.IO.
    This version is stripped down for MCP service integration, focusing on browser control.
    """
    def __init__(
        self,
        on_browser_connect: Optional[Callable[[], None]] = None,
        on_browser_disconnect: Optional[Callable[[str], None]] = None,
    ):
        self.bridge_server = BridgeServer(
            on_connect=self._handle_browser_connect,
            on_disconnect=self._handle_browser_disconnect,
        )
        self.sio_app = self.bridge_server.app  # Expose the ASGI app

        self._on_browser_connect_cb = on_browser_connect
        self._on_browser_disconnect_cb = on_browser_disconnect
        self.is_connected = False # Track connection status

        logger.info("AgentOverChromeBridge initialized for MCP service.")

    def _handle_browser_connect(self):
        self.is_connected = True
        logger.info("Browser client connected to AgentOverChromeBridge.")
        if self._on_browser_connect_cb:
            self._on_browser_connect_cb()

    def _handle_browser_disconnect(self, reason: str):
        self.is_connected = False
        logger.warning(f"Browser client disconnected from AgentOverChromeBridge. Reason: {reason}")
        if self._on_browser_disconnect_cb:
            self._on_browser_disconnect_cb(reason)

    async def close(self):
        """Closes the connection to the browser extension."""
        logger.info("AgentOverChromeBridge closing connection...")
        await self.bridge_server.close()
        self.is_connected = False
        logger.info("AgentOverChromeBridge connection closed.")

    async def call_on_browser(
        self,
        method: str,
        args: Optional[list] = None,
        timeout: int = BridgeCallTimeout
    ) -> Any:
        """
        Calls a method on the connected Chrome extension client.
        """
        if not self.is_connected:
            raise ConnectionError("Browser not connected. Cannot make call.")
        
        # The actual call logic is now within BridgeServer
        return await self.bridge_server.call_on_browser(method, args, timeout)

    # --- Core Browser Interaction Methods ---

    async def connect_new_tab_with_url(self, url: str, timeout: int = BridgeCallTimeout) -> bool:
        """
        Asks the Chrome extension to open a new tab, navigate to the URL,
        and establish a connection with it.
        """
        logger.info(f"Attempting to connect to new tab with URL: {url}")
        response = await self.call_on_browser(
            BridgeEvent.ConnectNewTabWithUrl,
            [url],
            timeout=timeout
        )
        if isinstance(response, dict) and response.get("success"):
            logger.info(f"Successfully connected to new tab: {url}")
            return True
        logger.error(f"Failed to connect to new tab {url}. Response: {response}")
        return False

    async def version(self, timeout: int = BridgeCallTimeout) -> str:
        """Gets the version of the connected MidScene Chrome Extension."""
        logger.info("Requesting extension version.")
        # The extension exposes its version via a global __MIDSCENE_VERSION__ variable.
        # We use 'evaluateJavaScript' which is a generic method provided by the extension's bridge.
        response = await self.call_on_browser(
            "evaluateJavaScript",
            ["window.__MIDSCENE_EXTENSION_VERSION__ || 'unknown'"], # Access global var or default
            timeout=timeout
        )
        version_str = str(response) if response is not None else "unknown"
        logger.info(f"Extension version: {version_str}")
        return version_str

    async def close_tab(self, timeout: int = BridgeCallTimeout) -> Any:
        """Closes the currently active tab in the browser."""
        logger.info("Requesting to close current tab.")
        # Assuming the extension has a 'closeActiveTab' method or similar.
        # If not, this will need to be implemented in the extension and bridge.
        response = await self.call_on_browser(
            "closeActiveTab", 
            [], 
            timeout=timeout
        )
        logger.info(f"Close tab response: {response}")
        return response

    async def get_tab_content(self, timeout: int = BridgeCallTimeout) -> Dict[str, Any]:
        """
        Gets content details (title, URL, focused element text) of the current tab.
        This is a simplified version. The actual implementation depends on what the
        Chrome extension's 'getTabContent' method returns.
        """
        logger.info("Requesting current tab content.")
        # This assumes the extension has a method like 'getCurrentTabContent'
        # that returns a dictionary with title, url, and possibly focusedElementText.
        response = await self.call_on_browser(
            "getCurrentTabContent", 
            [], 
            timeout=timeout
        )
        
        if isinstance(response, dict):
            logger.info(f"Current tab content received: {response}")
            return {
                "title": response.get("title", "N/A"),
                "url": response.get("url", "N/A"),
                "focused_element_text": response.get("focusedElementText", "N/A") # Example field
            }
        
        logger.warning(f"Received unexpected format for tab content: {response}")
        return {"title": "Error", "url": "Error", "focused_element_text": "Error"}

    # --- Helper methods (can be expanded or kept minimal) ---
    async def evaluate(self, js_code: str, timeout: int = BridgeCallTimeout) -> Any:
        """
        Evaluates arbitrary JavaScript code in the context of the current page.
        """
        logger.debug(f"Evaluating JS: {js_code[:100]}{'...' if len(js_code) > 100 else ''}")
        response = await self.call_on_browser("evaluateJavaScript", [js_code], timeout=timeout)
        logger.debug(f"JS evaluation response: {response}")
        return response

    # --- Other browser control methods as needed by MCP tools ---
    # Add methods like navigate, get_url, get_title, etc.
    # based on what tools.json will define.
    # These methods should largely map to call_on_browser with appropriate method names
    # that the Chrome extension is expected to handle.

    async def get_url(self, timeout: int = BridgeCallTimeout) -> str:
        """Gets the URL of the current tab."""
        logger.info("Requesting current URL.")
        response = await self.call_on_browser("evaluateJavaScript", ["window.location.href"], timeout=timeout)
        return str(response) if response else ""

    async def get_title(self, timeout: int = BridgeCallTimeout) -> str:
        """Gets the title of the current tab."""
        logger.info("Requesting current title.")
        response = await self.call_on_browser("evaluateJavaScript", ["document.title"], timeout=timeout)
        return str(response) if response else ""

    async def navigate(self, url: str, timeout: int = BridgeCallTimeout):
        """Navigates the current tab to a new URL."""
        logger.info(f"Navigating to: {url}")
        await self.call_on_browser("evaluateJavaScript", [f"window.location.href = '{url}'"], timeout=timeout)
        logger.info(f"Navigation to {url} initiated.")

    async def get_ui_context(self, action: Optional[str] = None) -> WebUIContext:
        """
        Retrieves the UI context from the browser.
        This is a placeholder and might need to call a specific method on the extension
        that returns structured UI data.
        """
        logger.info(f"Requesting UI context (action: {action}).")
        # This assumes the extension provides a method like 'getFullWebUIContext'
        # or 'getAccessibilityTreeAndSnapshot'
        raw_context = await self.call_on_browser("getFullWebUIContext", [], timeout=BridgeCallTimeout * 2) # Longer timeout
        
        # Basic conversion/validation. This needs to align with what the extension sends.
        if isinstance(raw_context, dict) and "url" in raw_context and "title" in raw_context:
            # Ensure basic fields are present
            # The actual transformation to WebUIContext would be more complex
            # and depend on the exact structure from the extension.
            # For now, we'll just cast and log.
            logger.info("Received UI context. Further parsing/validation would be needed.")
            return raw_context # type: ignore 
        
        logger.warning(f"Received unexpected format for UI context: {raw_context}")
        # Return a default/empty WebUIContext if parsing fails
        return WebUIContext(content=[], tree={}, size={}, screenshotBase64="", url="error", title="error") 