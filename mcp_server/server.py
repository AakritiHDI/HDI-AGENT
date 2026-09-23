#!/usr/bin/env python3
"""
HANA HDI Agent — MCP Server

Exposes all HDI agent tools as MCP tools so any MCP-compatible client
(Cline, Claude Desktop, etc.) can use it directly.

Run:
    python mcp_server/server.py

Add to cline_mcp_settings.json:
    {
      "mcpServers": {
        "hana-hdi-agent": {
          "command": "python",
          "args": ["/absolute/path/to/hana-hdi-agent/mcp_server/server.py"]
        }
      }
    }
"""
from __future__ import annotations

import sys
import os

# Add the project root to sys.path so we can import agent/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp import types
except ImportError:
    print(
        "ERROR: mcp package not installed.\n"
        "Run: pip install mcp",
        file=sys.stderr,
    )
    sys.exit(1)

from agent.hana_client import HANAClient
from agent.tools import TOOL_DEFINITIONS, dispatch

# ── Server setup ───────────────────────────────────────────────────────────────

server = Server("hana-hdi-agent")
_hana_client = HANAClient()

# Optional: read username from env var so MCP clients also get user-prefixed naming.
# Set HDI_USERNAME=AAKRITI in your .env (or environment) to enable.
_MCP_USERNAME = os.environ.get("HDI_USERNAME", "").strip().upper()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return all tools from the same TOOL_DEFINITIONS used by the agent."""
    return [
        types.Tool(
            name=t["toolSpec"]["name"],
            description=t["toolSpec"]["description"],
            # MCP expects a plain JSON Schema; Bedrock wraps it in {"json": {...}}
            inputSchema=t["toolSpec"]["inputSchema"]["json"],
        )
        for t in TOOL_DEFINITIONS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Execute a tool and return its result as MCP TextContent."""
    result = dispatch(_hana_client, name, arguments, username=_MCP_USERNAME)
    return [types.TextContent(type="text", text=result)]


# ── Entry point ────────────────────────────────────────────────────────────────

async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(_run())