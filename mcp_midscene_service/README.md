# MidScene Browser MCP Service

This service exposes browser interaction capabilities via the Model Context Protocol (MCP).
It uses Socket.IO to communicate with the MidScene Chrome Extension.

## Prerequisites

- Python 3.8+
- MidScene Chrome Extension installed and active

## Setup

1.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Service

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

This will start the MCP service, which also includes the Socket.IO server for the Chrome extension to connect to.

## MCP Tools

Refer to `tools.json` for a list of available MCP tools and their schemas. 