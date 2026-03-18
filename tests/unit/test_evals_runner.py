from evals import runner


def test_get_prerequisite_errors_reports_missing_models_and_data(monkeypatch):
    monkeypatch.delenv("GENERATOR_MODEL", raising=False)
    monkeypatch.delenv("REVIEWER_MODEL", raising=False)
    monkeypatch.setenv("NATURAL_EARTH_DATA_PATH", "/tmp/atlas-fabric-missing.geojson")

    errors = runner.get_prerequisite_errors()

    assert any("GENERATOR_MODEL is not set" in error for error in errors)
    assert any("REVIEWER_MODEL is not set" in error for error in errors)
    assert any("Natural Earth data not found" in error for error in errors)


def test_main_exits_cleanly_when_prerequisites_are_missing(monkeypatch):
    monkeypatch.delenv("GENERATOR_MODEL", raising=False)
    monkeypatch.delenv("REVIEWER_MODEL", raising=False)
    monkeypatch.setenv("NATURAL_EARTH_DATA_PATH", "/tmp/atlas-fabric-missing.geojson")

    try:
        runner.main(load_env=False)
    except SystemExit as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive check
        raise AssertionError("Expected runner.main() to exit when prerequisites are missing")

    assert "Cannot run evals:" in message
    assert "GENERATOR_MODEL is not set" in message
    assert "REVIEWER_MODEL is not set" in message
