import pytest

from agents import tracing


def test_configure_tracing_noops_when_disabled(monkeypatch):
    monkeypatch.delenv("TRACING_ENABLED", raising=False)
    tracing.configure_tracing("unit-test")


def test_configure_tracing_requires_dependencies_when_enabled(monkeypatch):
    monkeypatch.setenv("TRACING_ENABLED", "true")
    monkeypatch.setattr(tracing, "_OTEL_IMPORT_ERROR", ImportError("missing"))

    with pytest.raises(RuntimeError, match="Tracing dependencies are not installed"):
        tracing.configure_tracing("unit-test")
