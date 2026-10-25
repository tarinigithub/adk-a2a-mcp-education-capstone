"""Education Insights & Resource Recommender - root agent.

root_agent ──▶ data_agent      (SQL via the schools MCP server, charts)
           └─▶ insights_agent  (remote over A2A: patterns + evidence-based recommendations)
"""

import sys
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from . import db
from .config import INSIGHTS_A2A_URL, gemini
from .tools import create_chart

MCP_SERVER = Path(__file__).resolve().parents[2] / "mcp_server" / "schools_mcp.py"

# get_schema and run_sql come from the MCP server; ADK launches it as a subprocess (stdio).
schools_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command=sys.executable, args=[str(MCP_SERVER)]),
        timeout=30,
    ),
    tool_filter=["get_schema", "run_sql"],
)

data_agent = LlmAgent(
    name="data_agent",
    model=gemini(),
    description=(
        "Queries the California school database (demographics, funding, staffing, STEM, "
        "graduation, technology) with SQL and draws charts."
    ),
    instruction=f"""You are a data analyst with read-only SQL access to a SQLite database of
California public schools.

{db.SCHEMA_DOC}

How to work:
- Translate the question into ONE SQLite query; prefer the `school_profile` view.
- Always filter out NULLs for the columns you rank or compare on.
- "Below-average" means below the statewide (or county, if one is named) average:
  compute it with a subquery, e.g. per_pupil_expenditure < (SELECT AVG(per_pupil_expenditure) FROM finance).
- "Highest rate of low-income students" -> low_income_pct; "class size" -> student_teacher_ratio;
  "technology spending" -> per_pupil_nonpersonnel (say it's a proxy) and wifi_devices_per_student.
- Ignore tiny schools (enrollment < 100) unless asked, they make rankings noisy.
- If a query errors, read the error, fix it and retry.
- When the user asks for a chart or visual, call `create_chart`.
- Present results as a compact markdown table with school name, district, county and the
  metrics used, then state the SQL logic in one sentence. Round numbers sensibly.
- If a follow-up asks "why", for patterns or for recommendations, transfer to `insights_agent`
  and include the relevant rows in your handoff.""",
    tools=[schools_mcp, create_chart],
)

insights_agent = RemoteA2aAgent(
    name="insights_agent",
    description=(
        "Remote insights analyst (A2A). Summarizes patterns in school data, compares schools, "
        "and recommends evidence-based interventions backed by statistics."
    ),
    agent_card=f"{INSIGHTS_A2A_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

root_agent = LlmAgent(
    name="education_root_agent",
    model=gemini(),
    description="Front door for the Education Insights & Resource Recommender.",
    instruction="""You are the Education Insights & Resource Recommender. You help parents,
educators and public officials find needs, compare resources and prioritize interventions
for California public schools.

- On the first message, greet the user briefly and give 2-3 example questions, such as
  "Which 5 schools in Fresno County have the most low-income students and the lowest
  technology spending?" or "Find high schools with high graduation rates despite
  below-average funding."
- For any question needing numbers, rankings, lists of schools or charts: transfer to
  `data_agent`.
- For "why", "what works", patterns, recommendations or interventions: transfer to
  `insights_agent`. If it needs specific school data, get it from `data_agent` first,
  then pass the results to `insights_agent`.
- If the user shares an image (e.g. a school report card or budget screenshot), read the
  relevant figures from it and use them in the question you route.
- Politely decline questions unrelated to education.
- Data covers California, 2017 (technology data 2020). Mention this when relevant.""",
    sub_agents=[data_agent, insights_agent],
)
