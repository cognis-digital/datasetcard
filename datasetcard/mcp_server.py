"""DATASETCARD MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from datasetcard.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-datasetcard[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-datasetcard[mcp]'")
        return 1
    app = FastMCP("datasetcard")

    @app.tool()
    def datasetcard_scan(target: str) -> str:
        """Auto Dataset Cards / datasheets with Croissant + provenance. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
