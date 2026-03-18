import os

from agents.runtime_env import get_env_path, load_environment


def test_get_env_path_prefers_custom_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / "custom.env"
    monkeypatch.setenv("ATLAS_FABRIC_ENV_FILE", str(env_file))

    assert get_env_path() == env_file


def test_load_environment_uses_dotenv_as_main_source(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("API_SECRET_KEY=from-dotenv\nGENERATOR_MODEL=openai/test-model\n")
    monkeypatch.setenv("ATLAS_FABRIC_ENV_FILE", str(env_file))
    monkeypatch.setenv("API_SECRET_KEY", "from-shell")
    monkeypatch.delenv("GENERATOR_MODEL", raising=False)

    loaded = load_environment()

    assert loaded is True
    assert os.environ["API_SECRET_KEY"] == "from-dotenv"
    assert os.environ["GENERATOR_MODEL"] == "openai/test-model"
