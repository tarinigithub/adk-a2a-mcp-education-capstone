"""MCP server exposing the California schools database as tools.

Tools (both read-only):
    get_schema()  -> tables, columns and how to join them
    run_sql(sql)  -> rows from a read-only SQLite SELECT (max 50)

The capstone's data_agent uses these through ADK's McpToolset, which starts this server as a
subprocess and talks to it over stdio. Any other MCP client can use it too:

    python mcp_server/schools_mcp.py           # stdio (default; e.g. Claude Desktop, ADK)
    python mcp_server/schools_mcp.py --http    # streamable HTTP on http://localhost:8004/mcp

Note: in stdio mode stdout carries the MCP protocol, so this file never prints.
"""

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

# Reuse the capstone's read-only database access (db.py has no package imports).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "education_agent"))
import db  # noqa: E402

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

mcp = MCPServer(
    name="california-schools",
    instructions="Read-only SQL access to 10,323 California public schools (NCES CCD, CRDC, EdFacts).",
)


@mcp.tool(annotations=READ_ONLY)
def get_schema() -> str:
    """Return the tables and columns in the school database and how to join them.

    Call this before writing SQL if you are unsure of a column name.
    """
    return db.SCHEMA_DOC


@mcp.tool(annotations=READ_ONLY)
def run_sql(sql: str) -> dict:
    """Run a read-only SQLite SELECT query against the school database.

    Args:
        sql: A single SQLite SELECT (or WITH ... SELECT) statement. At most 50 rows are
            returned, so use ORDER BY and LIMIT.

    Returns:
        status and the result rows, or an error message to fix the query and retry.
    """
    try:
        rows = db.query(sql)
    except Exception as exc:  # surface SQL errors so the model can retry
        return {"status": "error", "error": str(exc)}
    return {"status": "success", "row_count": len(rows), "rows": rows}


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", port=8004)
    else:
        mcp.run()
