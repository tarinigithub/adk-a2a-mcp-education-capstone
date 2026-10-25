# Education Insights & Resource Recommender

Agents for Impact capstone. A conversational multi-agent system that helps **parents,
educators and public officials** find needs, compare resources and prioritize
interventions for California public schools.

Built with **Google ADK + Gemini**, with agent-to-agent communication over **A2A** and
database tools served over **MCP**.

> Companion repo: **[voice-agent-adk-a2a](https://github.com/tarinigithub/voice-agent-adk-a2a)**,
> a voice front end that delegates school questions to this capstone over A2A, finding it through
> an Agent Registry. Its [DESIGN.md](https://github.com/tarinigithub/voice-agent-adk-a2a/blob/main/DESIGN.md)
> covers how the two projects fit together. Slides: [presentation/](presentation/).

```
                    ┌──────────────────────┐
  user ──▶ adk web ─▶│ education_root_agent │  greets, interprets, routes
                    └──────────┬───────────┘
                ┌──────────────┴──────────────┐
                ▼                             ▼  (A2A over HTTP, port 8001)
        ┌──────────────┐              ┌────────────────┐
        │  data_agent  │              │ insights_agent │  patterns, comparisons,
        │ MCP + charts │              │ evidence_check │  evidence-based recommendations
        └──────┬───────┘              └───────┬────────┘
               │ MCP (stdio)                  │
        ┌──────▼─────────────┐                │
        │ schools MCP server │                │
        │ get_schema·run_sql │                │
        └──────┬─────────────┘                │
               └──────────┬───────────────────┘
                          ▼
                  data/schools.db  (SQLite, ~10.3k CA schools)
```

## Assignment checklist

| Required step | How it's done here |
|---|---|
| Find your data | Urban Institute Education Data API (NCES CCD, CRDC, EdFacts), loaded by `data/build_db.py` |
| Leverage BigQuery | **Substituted** with a local SQLite database (no GCP project). The data agent writes SQL the same way it would for BigQuery |
| Create agents using ADK | `agents/education_agent/`: root, data and insights agents (`google-adk` 2.13) |
| Deploy to Agent Engine | **Not done.** Needs a GCP project. Runs locally with `adk web` instead |
| Show A2A | `insights_agent` runs as its own A2A server (`to_a2a`); the root agent calls it with `RemoteA2aAgent` |

Stretch goals: charts (`create_chart` saves a PNG that shows in `adk web`), evidence-based
interventions (`evidence_check` computes correlations and quartile comparisons), combined
datasets (the `school_profile` view joins 6 tables), image input (Gemini reads uploaded
report cards or screenshots), an **MCP server** for the database tools, an **Agent Registry**
for A2A discovery, and a **voice front end** (`../voice-agent-adk-a2a`).

## Layout

| Path | Purpose |
|---|---|
| `data/build_db.py` | Downloads California school data and builds `data/schools.db` |
| `agents/education_agent/agent.py` | `root_agent`, `data_agent` (with the MCP `McpToolset`), and the `RemoteA2aAgent` link to insights |
| `agents/education_agent/insights.py` | `insights_agent` and its `evidence_check` statistics tool |
| `agents/education_agent/a2a_server.py` | Serves `insights_agent` over A2A on port 8001 |
| `mcp_server/schools_mcp.py` | **MCP server**: `get_schema` and `run_sql` (read-only) over the school database |
| `agents/education_agent/tools.py` | Local data agent tool: `create_chart` |
| `agents/education_agent/db.py` | SQLite access and the schema description given to the model |
| `agents/education_agent/config.py` | Loads `.env`; Gemini model with retry on free-tier rate limits |
| `streamlit_app.py` | Demo UI: sample-question buttons, agent trace, inline charts |
| `run.sh` | Starts the A2A server and the ADK web UI |
| `start_a2a.sh` | Starts only the A2A servers: insights on 8001, root agent on 8002 (for the voice agent) |
| `agents/education_agent/root_a2a_server.py` | Serves the root agent over A2A on port 8002 |
| `agents/education_agent/registry.py` | Self-registration with the Agent Registry on startup |
| `multiagent/`, `main.py` | Earlier LangGraph + Groq skeleton (not used by the capstone) |

## Setup

```bash
git clone https://github.com/tarinigithub/adk-a2a-mcp-education-capstone.git
cd adk-a2a-mcp-education-capstone
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your GOOGLE_API_KEY (from aistudio.google.com/apikey)
python data/build_db.py       # ~2-3 min; skip if data/schools.db already exists
```

## Run

### Demo UI (Streamlit), recommended for presenting

```bash
streamlit run streamlit_app.py
```

Opens http://localhost:8501 and starts the A2A insights server for you. The sidebar has
one-click sample questions for public officials, educators and parents. Each answer has an
**Agent trace** panel showing the hand-offs between agents (including the A2A call) and the
SQL that ran. Charts appear inline.

### ADK web UI

```bash
./run.sh
```

Then open http://localhost:8000 and pick **education_agent**. To run the pieces by hand:

```bash
uvicorn education_agent.a2a_server:app --app-dir agents --port 8001   # terminal 1
adk web agents --port 8000                                            # terminal 2
```

Try these questions:
- *Identify the five schools in Fresno County with the highest rate of low-income students and the lowest per-pupil technology spending, to prioritize grant funding.*
- *Find high schools with high graduation rates despite below-average funding.*
- *Find high schools with strong STEM programs and low class sizes.*
- *Do smaller class sizes go with higher graduation rates? What would you recommend?*
- *Show a bar chart of the 10 Los Angeles County high schools with the most AP courses.*

### MCP server (database tools)

The data agent's SQL tools come from an **MCP server**, `mcp_server/schools_mcp.py` (MCP Python
SDK). ADK's `McpToolset` starts it as a subprocess and talks to it over stdio, so there is
nothing extra to run. Both tools are read-only (`readOnlyHint=True`, and writes are rejected).

Try the server with any MCP client:

```bash
npx @modelcontextprotocol/inspector .venv/bin/python mcp_server/schools_mcp.py   # MCP Inspector UI
python mcp_server/schools_mcp.py --http                                           # streamable HTTP on :8004/mcp
```

### Voice front end (A2A)

`./start_a2a.sh` serves the insights agent on port 8001 and the **root agent** on port 8002
(`agents/education_agent/root_a2a_server.py`). The voice agent in `../voice-agent-adk-a2a`
delegates school questions to it over A2A, so you can ask the capstone questions by voice.
That project's `start.sh` runs `start_a2a.sh` for you.

Both A2A servers **register themselves with the Agent Registry** (`AGENT_REGISTRY_URL`, default
`http://localhost:8003`, provided by `../voice-agent-adk-a2a/registry`) on startup, using the
`register_on_startup(port)` lifespan hook in `agents/education_agent/registry.py`. Without a
registry they still run normally, just unregistered.

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_API_KEY` | (required) | Gemini API key from AI Studio |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | Use the AI Studio key, not Vertex AI |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Lite models have higher free-tier rate limits |
| `INSIGHTS_A2A_URL` | `http://localhost:8001` | Where the root agent finds the insights agent |

## Data notes and limitations

- **Coverage:** California public schools. Data is from 2017 (the latest year where funding, STEM and graduation data line up); internet and device data is from 2020.
- **Technology spending:** no dataset reports tech spending per school. The agent uses `per_pupil_nonpersonnel` (non-salary spending per student) together with `wifi_devices_per_student` instead, and says so.
- **Spending figures** are school-level salaries plus non-personnel spending reported to CRDC. They are lower than total district spending. Values under $1,000 or over $60,000 per pupil are treated as reporting errors and stored as missing.
- **Graduation rates** are the midpoint of the range EdFacts reports, for high schools only.
- **Class size** is approximated by `student_teacher_ratio`.
- **Free-tier limits:** the Gemini free tier allows only a few requests per minute. One question can take 3 to 6 model calls, so the agents retry automatically, and answers can sometimes take 30 to 60 seconds.

## Data Sources

> **Instructor-provided dataset:** the "we've provided" link in the assignment PDF can't be recovered because the PDF is a scan. Ask the instructor for the original digital copy, or check the course portal.

| Source | URL | Useful for |
|---|---|---|
| Urban Institute Education Data Portal (likely the PDF's "educationdata.gov"; **used here**) | https://educationdata.urban.org/data-explorer | Combined NCES, CRDC and EdFacts data with a free API |
| data.gov | https://data.gov ([education datasets](https://catalog.data.gov/dataset?groups=education2168)) | General government datasets |
| U.S. Dept. of Education Open Data | https://data.ed.gov | Federal education datasets |
| NCES Common Core of Data | https://nces.ed.gov/ccd/files.asp | School demographics, free/reduced lunch (low-income), staffing |
| Civil Rights Data Collection | https://civilrightsdata.ed.gov/data | STEM course offerings, class sizes, staffing |
| EDFacts | https://www.ed.gov/data/edfacts-initiative | Graduation rates |
| Census School Finances | https://www.census.gov/programs-surveys/school-finances.html | Per-pupil spending and funding |
| BigQuery Public Datasets | https://console.cloud.google.com/marketplace/browse?filter=solution-type:dataset | Search "education" / "NCES" for data that's already loaded |
