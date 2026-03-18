"""
OTel tracing -> MongoDB traces collection.
No extra services. Uses existing MONGODB_URI.
Off by default - set TRACING_ENABLED=true to activate.
"""

import os
from datetime import UTC, datetime
from typing import Any

_OTEL_IMPORT_ERROR: Exception | None = None

try:
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
except ImportError as exc:  # pragma: no cover - depends on optional runtime deps
    _OTEL_IMPORT_ERROR = exc

    class SpanExporter:  # type: ignore[no-redef]
        pass

    class _SpanExportResult:
        SUCCESS = "SUCCESS"

    SpanExportResult = _SpanExportResult()  # type: ignore[assignment]
    Resource = Any  # type: ignore[assignment]
    TracerProvider = Any  # type: ignore[assignment]


class MongoSpanExporter(SpanExporter):
    """Exports OTel spans to MongoDB traces collection."""

    def __init__(self, collection: Any):
        self._col = collection

    def export(self, spans: list[Any]):
        docs = []
        for span in spans:
            docs.append(
                {
                    "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_span_id": (
                        format(span.parent.span_id, "016x") if span.parent else None
                    ),
                    "name": span.name,
                    "status": span.status.status_code.name,
                    "start_time": datetime.fromtimestamp(
                        span.start_time / 1e9,
                        tz=UTC,
                    ),
                    "end_time": datetime.fromtimestamp(
                        span.end_time / 1e9,
                        tz=UTC,
                    ),
                    "duration_ms": round((span.end_time - span.start_time) / 1e6, 2),
                    "attributes": dict(span.attributes or {}),
                    "events": [
                        {"name": event.name, "attributes": dict(event.attributes or {})}
                        for event in span.events
                    ],
                }
            )

        if docs:
            self._col.insert_many(docs)

        return SpanExportResult.SUCCESS

    def shutdown(self):
        return None


def configure_tracing(run_name: str | None = None) -> None:
    """
    Wire OTel -> MongoDB. Call once at process startup.
    Auto-instruments all LangChain + LangGraph calls - no per-node code needed.
    No-ops silently if TRACING_ENABLED != "true".
    """
    if os.environ.get("TRACING_ENABLED", "").lower() != "true":
        return

    if _OTEL_IMPORT_ERROR is not None:  # pragma: no cover - depends on runtime deps
        raise RuntimeError("Tracing dependencies are not installed.") from _OTEL_IMPORT_ERROR

    from openinference.instrumentation.langchain import LangChainInstrumentor
    from opentelemetry import trace
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from pymongo import MongoClient

    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    col: Any = MongoClient(mongo_uri)["atlas_fabric"]["traces"]

    col.create_index("trace_id")
    col.create_index("start_time")
    col.create_index([("attributes.year", 1), ("attributes.region", 1)])

    resource = Resource({"service.name": "atlas-fabric", "run.name": run_name or ""})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(MongoSpanExporter(col)))
    trace.set_tracer_provider(provider)

    LangChainInstrumentor().instrument()
