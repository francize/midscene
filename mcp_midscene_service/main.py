import logging
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import PlainTextResponse 

# Import the global service instance from server.py
from server import mcp_service 

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MainApp")

async def health_check(request):
    # Basic health check endpoint
    logger.info("Health check endpoint called.")
    # You can add more sophisticated checks here, e.g., check browser_agent connectivity
    if mcp_service.browser_agent and mcp_service.browser_agent.is_connected:
        return PlainTextResponse("OK - MCP Service is running and browser agent is connected.")
    elif mcp_service.browser_agent:
        return PlainTextResponse("OK - MCP Service is running but browser agent is NOT connected.")
    return PlainTextResponse("OK - MCP Service is running (browser agent status unknown - likely pre-init).", status_code=200)

# Create the main Starlette application
app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_service.sse_app()), # Mount MCP SSE app under /mcp
        Mount("/socket.io", app=mcp_service.get_socketio_app()), # Mount Socket.IO app
        Route("/health", endpoint=health_check) # Basic health check
    ],
    on_startup=[lambda: logger.info("Starlette application starting...")],
    on_shutdown=[lambda: logger.info("Starlette application shutting down...")]
)

if __name__ == "__main__":
    logger.info("Starting Uvicorn server for MidScene MCP Service...")
    # The MCP server (and its lifespan including AgentOverChromeBridge) 
    # will be managed by the Starlette app's lifecycle when Uvicorn runs it.
    # Uvicorn will also handle the Socket.IO server via the mounted ASGI app.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info") 