import os
from unittest.mock import MagicMock, patch

import pytest


def test_missing_env_var_raises():
    from agents.model_factory import get_model
    env = {k: v for k, v in os.environ.items() if k != "GENERATOR_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="GENERATOR_MODEL"):
            get_model("generator")


def test_invalid_format_raises():
    from agents.model_factory import _build_model
    with pytest.raises(ValueError, match="provider/model_name"):
        _build_model("claude-opus-4-5", 0.0)


def test_unsupported_provider_raises():
    from agents.model_factory import _build_model
    with pytest.raises(ValueError, match="Unsupported provider"):
        _build_model("cohere/command-r", 0.0)


def test_correct_provider_selected_anthropic():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_anthropic", return_value=mock_model) as m:
        result = _build_model("anthropic/claude-opus-4-5", 0.2)
        m.assert_called_once_with("claude-opus-4-5", 0.2)
        assert result is mock_model


def test_correct_provider_selected_openai():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_openai", return_value=mock_model) as m:
        result = _build_model("openai/gpt-4o", 0.0)
        m.assert_called_once_with("gpt-4o", 0.0)
        assert result is mock_model


def test_correct_provider_selected_google():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_google", return_value=mock_model) as m:
        _build_model("google/gemini-pro", 0.0)
        m.assert_called_once_with("gemini-pro", 0.0)


def test_correct_provider_selected_groq():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_groq", return_value=mock_model) as m:
        _build_model("groq/llama3-70b-8192", 0.0)
        m.assert_called_once_with("llama3-70b-8192", 0.0)


def test_correct_provider_selected_mistral():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_mistral", return_value=mock_model) as m:
        _build_model("mistral/mistral-large-latest", 0.0)
        m.assert_called_once_with("mistral-large-latest", 0.0)


def test_correct_provider_selected_ollama():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_ollama", return_value=mock_model) as m:
        _build_model("ollama/llama3", 0.0)
        m.assert_called_once_with("llama3", 0.0)


def test_temperature_passed_correctly():
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_anthropic", return_value=mock_model) as m:
        _build_model("anthropic/claude-haiku-4-5", 0.7)
        assert m.call_args[0][1] == 0.7


def test_get_model_reads_generator_env():
    from agents.model_factory import get_model
    mock_model = MagicMock()
    env = {"GENERATOR_MODEL": "anthropic/claude-opus-4-5", "GENERATOR_TEMPERATURE": "0.2"}
    with patch.dict(os.environ, env):
        with patch("agents.model_factory._load_anthropic", return_value=mock_model):
            result = get_model("generator")
            assert result is mock_model


def test_get_model_reads_reviewer_env():
    from agents.model_factory import get_model
    mock_model = MagicMock()
    env = {"REVIEWER_MODEL": "openai/gpt-4o", "REVIEWER_TEMPERATURE": "0.0"}
    with patch.dict(os.environ, env):
        with patch("agents.model_factory._load_openai", return_value=mock_model):
            result = get_model("reviewer")
            assert result is mock_model


def test_default_temperature_is_zero():
    from agents.model_factory import get_model
    mock_model = MagicMock()
    env = {"GENERATOR_MODEL": "anthropic/claude-opus-4-5"}
    with patch.dict(os.environ, env):
        with patch("agents.model_factory._load_anthropic", return_value=mock_model) as m:
            get_model("generator")
            assert m.call_args[0][1] == 0.0


def test_all_providers_registered():
    from agents.model_factory import _PROVIDER_MAP
    expected = {"anthropic", "openai", "google", "ollama", "groq", "mistral"}
    assert set(_PROVIDER_MAP.keys()) == expected


def test_model_name_with_slash_preserved():
    # Some model names contain slashes — only split on first /
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_openai", return_value=mock_model) as m:
        _build_model("openai/org/gpt-4o", 0.0)
        m.assert_called_once_with("org/gpt-4o", 0.0)
