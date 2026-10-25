"""Local tools for the data agent: charts.

Schema lookup and SQL queries (get_schema, run_sql) are served by the MCP server in
mcp_server/schools_mcp.py and reach the agent through McpToolset (see agent.py).
"""

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from google.adk.tools import ToolContext
from google.genai import types

from . import db


async def create_chart(
    sql: str,
    x_column: str,
    y_column: str,
    title: str,
    chart_type: str,
    tool_context: ToolContext,
) -> dict:
    """Run a SELECT query and save the result as a PNG chart the user can view.

    Args:
        sql: SQLite SELECT returning at least the x and y columns (max 50 rows).
        x_column: Column for the x-axis (category labels for 'bar', numbers for 'scatter').
        y_column: Numeric column for the y-axis.
        title: Chart title.
        chart_type: 'bar' (horizontal bars, good for ranking schools) or
            'scatter' (relationship between two numeric columns).
    """
    try:
        rows = db.query(sql)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    rows = [r for r in rows if r.get(x_column) is not None and r.get(y_column) is not None]
    if not rows:
        return {"status": "error", "error": "Query returned no plottable rows."}

    xs = [r[x_column] for r in rows]
    ys = [r[y_column] for r in rows]
    fig, ax = plt.subplots(figsize=(9, max(4, 0.35 * len(rows)) if chart_type == "bar" else 6))
    if chart_type == "scatter":
        ax.scatter(xs, ys, alpha=0.6)
        ax.set_xlabel(x_column)
    else:
        ax.barh([str(x)[:40] for x in xs][::-1], ys[::-1])
    ax.set_ylabel(y_column if chart_type == "scatter" else "")
    if chart_type != "scatter":
        ax.set_xlabel(y_column)
    ax.set_title(title)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    filename = "chart.png"
    version = await tool_context.save_artifact(
        filename, types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")
    )
    return {"status": "success", "artifact": filename, "version": version, "points": len(rows)}
