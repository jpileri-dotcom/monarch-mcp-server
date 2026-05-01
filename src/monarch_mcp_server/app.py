"""FastMCP application instance and entry point."""

import logging
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Transport: "stdio" for Claude Desktop (default), "streamable-http" for remote
_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")

# Port: cloud hosts (Railway, Render, Fly) inject PORT; default to 8000 locally
_PORT = int(os.environ.get("PORT", 8000))

# Bind to all interfaces when running as a remote HTTP server
_HOST = "0.0.0.0" if _TRANSPORT != "stdio" else "127.0.0.1"

# Initialize FastMCP server
mcp = FastMCP("Monarch Money MCP Server", host=_HOST, port=_PORT)

# Import tools package to trigger @mcp.tool() registration
import monarch_mcp_server.tools  # noqa: E402, F401

# Export for `mcp run`
app = mcp


def main() -> None:
    """Main entry point for the server."""
    logger.info(f"Starting Monarch Money MCP Server (transport={_TRANSPORT}, port={_PORT})...")
    try:
        mcp.run(transport=_TRANSPORT)
    except Exception as e:
        logger.error(f"Failed to run server: {str(e)}")
        raise


if __name__ == "__main__":
    main()
