# app/mcp.py

from fastmcp import FastMCP

""" MCP server wrapper for GraphRAG tools """

class MCPServer:
    mcp: FastMCP

    def __init__(self):
        self.mcp = FastMCP(title="GraphRAG MCP")