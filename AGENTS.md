# AGENTS.md — AtlasFabric

AtlasFabric classifies modern admin polygons into historical polities for a given year
and outputs MapLibre GL JS boundary configs via a REST API.

For full architecture and code specs read **PLAN.md** first.

---

## Commands

```bash
make setup                                         # venv + install deps
make generate ARGS="--year 800 --region europe"    # run pipeline
make generate ARGS="--year 800 --dry-run"          # run without writing to MongoDB
make run-api                                       # FastAPI on :8080
make test-unit                                     # no external deps required
make test-integration                              # requires MongoDB + API key
make evals                                         # run LLM judge eval suite
make lint                                          # ruff + mypy
```

---

## What Is Already Built

Do not rewrite these. They are complete and working.

```
agents/model_factory.py       — model-agnostic LLM factory
agents/state.py               — AtlasState TypedDict
agents/orchestrator.py        — generator → reviewer retry loop (max 3)
agents/generator/graph.py     — LangGraph StateGraph, 10 tools
agents/generator/tools.py     — all 10 generator tools implemented
agents/generator/prompts.py   — system prompt + retry template
agents/reviewer/tools.py      — all 6 reviewer tools implemented
agents/reviewer/prompts.py    — adversarial system prompt
geo/                          — Natural Earth loader, union, validator, regions
knowledge/polities.json       — historical polities knowledge base
storage/                      — Motor async MongoDB client + Pydantic schema
api/                          — FastAPI app, auth middleware, rate limiting
cli/main.py                   — Typer CLI
```

What is missing and must be built:

```
agents/reviewer/graph.py      — has a bug, see below
agents/tracing.py             — OTel → MongoDB tracing
evals/                        — LLM judge eval suite
```

---

## Known Bug — Fix Before Running

`agents/reviewer/graph.py` has a conflicting edge. The unconditional `add_edge`
conflicts with `tools_condition`. Fix:

```python
# WRONG — current code
graph.add_conditional_edges("agent", tools_condition)
graph.add_edge("agent", "extract_decision")   # conflicts

# CORRECT
graph.add_conditional_edges("agent", tools_condition, {
    "tools": "tools",
    "__end__": "extract_decision",
})
graph.add_edge("tools", "agent")
graph.add_edge("extract_decision", END)
```

---

## Hard Rules

**Model agnosticism.** Agent files never import provider classes directly.

```python
# Always
from agents.model_factory import get_model
llm = get_model(role="generator")

# Never — not in any file inside agents/
from langchain_anthropic import ChatAnthropic
```

`agents/model_factory.py` is the only file that imports provider-specific classes.
This rule applies to `agents/tracing.py` and `evals/` too — use `get_model()`.

**Pipeline order.** Union runs after validation. `store_config` runs only after
the reviewer approves. Both already enforced in existing code — do not bypass.

**Tools never raise.** Return `{"error": str}` on failure. Raising inside a
`ToolNode` crashes the graph with no useful trace.

**Tool docstrings are LLM instructions.** The phrasing "Call this FIRST",
"ONLY call after", "NEVER" is load-bearing. Do not rewrite for style.

---

## Tracing

No extra services. No API keys. OTel spans write directly to the existing
MongoDB instance in a `traces` collection alongside `map_configs`.

### Dependencies

Add to `pyproject.toml`:

```toml
"opentelemetry-sdk>=1.20.0",
"openinference-instrumentation-langchain>=0.1.0",
"pymongo>=4.0.0",
```

### Implementation

Create `agents/tracing.py`:

```python
# agents/tracing.py
"""
OTel tracing → MongoDB traces collection.
No extra services. Uses existing MONGODB_URI.
Off by default — set TRACING_ENABLED=true to activate.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.resources import Resource


class MongoSpanExporter(SpanExporter):
    """Exports OTel spans to MongoDB traces collection."""

    def __init__(self, collection):
        self._col = collection

    def export(self, spans):
        docs = []
        for span in spans:
            docs.append({
                "trace_id":      format(span.context.trace_id, "032x"),
                "span_id":       format(span.context.span_id, "016x"),
                "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                "name":          span.name,
                "status":        span.status.status_code.name,
                "start_time":    datetime.fromtimestamp(span.start_time / 1e9, tz=timezone.utc),
                "end_time":      datetime.fromtimestamp(span.end_time / 1e9, tz=timezone.utc),
                "duration_ms":   round((span.end_time - span.start_time) / 1e6, 2),
                "attributes":    dict(span.attributes or {}),
                "events":        [
                    {"name": e.name, "attributes": dict(e.attributes or {})}
                    for e in span.events
                ],
            })
        if docs:
            import asyncio
            asyncio.run(self._col.insert_many(docs))
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def configure_tracing(run_name: Optional[str] = None) -> None:
    """
    Wire OTel → MongoDB. Call once at process startup.
    Auto-instruments all LangChain + LangGraph calls — no per-node code needed.
    No-ops silently if TRACING_ENABLED != "true".
    """
    if os.environ.get("TRACING_ENABLED", "").lower() != "true":
        return

    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from opentelemetry import trace
    from pymongo import MongoClient

    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    col = MongoClient(mongo_uri)["atlas_fabric"]["traces"]

    # Indexes for the queries you'll actually run
    col.create_index("trace_id")
    col.create_index("start_time")
    col.create_index([("attributes.year", 1), ("attributes.region", 1)])

    resource = Resource({"service.name": "atlas-fabric", "run.name": run_name or ""})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(MongoSpanExporter(col)))
    trace.set_tracer_provider(provider)

    LangChainInstrumentor().instrument()  # covers LangGraph automatically
```

### Where to Call It

```python
# cli/main.py — top of generate()
from agents.tracing import configure_tracing
configure_tracing(run_name=f"generate-{year}-{region}")

# api/app.py — inside create_app()
from agents.tracing import configure_tracing
configure_tracing(run_name="api")
```

### What Lands in MongoDB

Every LLM call, tool execution, and graph node is captured automatically:

```json
{
  "trace_id": "abc123...",
  "span_id":  "def456...",
  "name":     "ChatOpenAI",
  "status":   "OK",
  "start_time": "2025-03-17T10:00:00Z",
  "duration_ms": 1843.2,
  "attributes": {
    "llm.model_name": "azure/kimi-prod",
    "llm.token_count.prompt": 1200,
    "llm.token_count.completion": 340
  }
}
```

### Useful Queries

```python
# Slowest spans in a run
db.traces.find({"attributes.run.name": "generate-800-europe"}).sort("duration_ms", -1).limit(10)

# Token usage per generation
db.traces.aggregate([
    {"$match": {"name": {"$regex": "Chat"}}},
    {"$group": {"_id": "$trace_id",
                "prompt_tokens": {"$sum": "$attributes.llm.token_count.prompt"},
                "completion_tokens": {"$sum": "$attributes.llm.token_count.completion"}}}
])

# All tool calls for a trace
db.traces.find({"trace_id": "<id>", "name": {"$regex": "tool"}})
```

### Env Vars

```bash
TRACING_ENABLED=true   # off by default — uses existing MONGODB_URI, no other config needed
```

---

## Evals

Create an `evals/` package with this structure:

```
evals/
├── __init__.py
├── fixtures.py    — fixed test cases (year, region, required_polities, forbidden_polities)
├── checks.py      — deterministic: anachronism KB lookup, coverage, required/forbidden
├── judge.py       — LLM-as-judge using get_model("reviewer"), returns score 0-10
├── runner.py      — runs each fixture through run_pipeline(dry_run=True), collects results
└── report.py      — prints pass/fail summary to stdout
```

**Fixture shape:**

```python
@dataclass
class EvalCase:
    year: int
    region: str
    required_polities: list[str]   # must appear — verify against polities.json first
    forbidden_polities: list[str]  # must NOT appear (anachronism check)
    description: str
```

**Minimum fixtures to implement:**

| year | region      | required                                    | forbidden                          | why                          |
|------|-------------|---------------------------------------------|------------------------------------|------------------------------|
| 800  | europe      | Frankish Empire, Byzantine Empire           | Holy Roman Empire, Kingdom of France | HRE founded 962              |
| 1200 | middle_east | Abbasid Caliphate, Crusader States          | Ottoman Empire                     | Ottomans founded ~1299       |
| 1500 | europe      | Holy Roman Empire, Kingdom of France        | German Empire, Austrian Empire     | those names are post-1800    |

**Pass criteria per case:** no anachronisms + no forbidden polities + all required
polities present + coverage ≥ 90% + LLM judge score ≥ 6/10.

**LLM judge** uses `get_model(role="reviewer")` — not a hardcoded provider.
Returns structured JSON only:

```json
{
  "score": 0,
  "historical_accuracy": "pass | fail | partial",
  "geographic_coherence": "pass | fail | partial",
  "major_errors": [],
  "reasoning": ""
}
```

**Entry point:** `python -m evals.runner` → `make evals`.

---

## Environment Variables

```bash
# Model selection
GENERATOR_MODEL=azure/kimi-prod
REVIEWER_MODEL=azure/kimi-prod
GENERATOR_TEMPERATURE=0.2
REVIEWER_TEMPERATURE=0.0

# Azure AI Foundry (for azure/ models, use deployment names)
AZURE_API_BASE=https://<your-resource>.services.ai.azure.com/openai/v1
AZURE_API_KEY=

# Other provider keys — only set what you use
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Infrastructure
MONGODB_URI=mongodb://localhost:27017
API_SECRET_KEY=
PORT=8080
NATURAL_EARTH_DATA_PATH=./data/ne_10m_admin_1_states_provinces.geojson

# Tracing — off by default, uses existing MONGODB_URI
TRACING_ENABLED=true
```

Supported model format: `provider/model-name`
Providers: `anthropic`, `openai`, `google`, `ollama`, `groq`, `mistral`, `azure`

---

## Never

- Import a provider class outside `agents/model_factory.py`
- Call `store_config` from the generator agent
- Run `union_geometries` before `validate_classifications` passes
- Set `required_polities` in a fixture to a polity not in `knowledge/polities.json`
- Rewrite tool docstrings for readability — they are prompts
- Add a tracing service to docker-compose — tracing uses existing MongoDB
