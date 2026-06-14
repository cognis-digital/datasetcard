"""DATASETCARD MCP server — exposes profile() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
import json


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-datasetcard[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-datasetcard[mcp]'")
        return 1
    from datasetcard.core import profile_dataset, build_croissant
    app = FastMCP("datasetcard")

    @app.tool()
    def datasetcard_scan(target: str) -> str:
        """Dataset Cards / datasheets with Croissant + provenance. Returns JSON."""
        try:
            profile = profile_dataset(target)
            return json.dumps(build_croissant(profile), indent=2, default=str)
        except (FileNotFoundError, ValueError) as exc:
            return json.dumps({"error": str(exc)})

    app.run()
    return 0
