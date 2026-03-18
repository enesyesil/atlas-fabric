import os
import sys
from types import ModuleType
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


def test_correct_provider_selected_azure():
    from agents.model_factory import _build_model

    mock_model = MagicMock()
    with patch("agents.model_factory._load_azure", return_value=mock_model) as m:
        result = _build_model("azure/Kimi-Prod", 0.1)
        m.assert_called_once_with("Kimi-Prod", 0.1)
        assert result is mock_model


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
    expected = {"anthropic", "openai", "google", "ollama", "groq", "mistral", "azure"}
    assert set(_PROVIDER_MAP.keys()) == expected


def test_model_name_with_slash_preserved():
    # Some model names contain slashes — only split on first /
    from agents.model_factory import _build_model
    mock_model = MagicMock()
    with patch("agents.model_factory._load_openai", return_value=mock_model) as m:
        _build_model("openai/org/gpt-4o", 0.0)
        m.assert_called_once_with("org/gpt-4o", 0.0)


def test_azure_requires_base_and_key():
    from agents.model_factory import _load_azure

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="AZURE_API_BASE"):
            _load_azure("kimi-k2-5", 0.0)

    with patch.dict(
        os.environ,
        {"AZURE_API_BASE": "https://resource.services.ai.azure.com/openai/v1"},
        clear=True,
    ):
        with pytest.raises(ValueError, match="AZURE_API_KEY"):
            _load_azure("kimi-k2-5", 0.0)


def test_azure_rejects_legacy_inference_url():
    from agents.model_factory import _load_azure

    env = {
        "AZURE_API_BASE": (
            "https://resource.services.ai.azure.com/models/chat/completions"
            "?api-version=2024-05-01-preview"
        ),
        "AZURE_API_KEY": "secret",
    }
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="/openai/v1"):
            _load_azure("kimi-prod", 0.0)


def test_azure_loader_uses_official_foundry_chat_model():
    from agents.model_factory import _load_azure

    fake_cls = MagicMock(name="AzureAIChatCompletionsModel")
    fake_chat_models = ModuleType("langchain_azure_ai.chat_models")
    fake_chat_models.AzureAIChatCompletionsModel = fake_cls
    fake_package = ModuleType("langchain_azure_ai")
    fake_package.chat_models = fake_chat_models

    env = {
        "AZURE_API_BASE": "https://resource.services.ai.azure.com/openai/v1/",
        "AZURE_API_KEY": "secret",
    }
    with patch.dict(
        sys.modules,
        {
            "langchain_azure_ai": fake_package,
            "langchain_azure_ai.chat_models": fake_chat_models,
        },
    ):
        with patch.dict(os.environ, env, clear=True):
            _load_azure("Kimi-Prod", 0.2)

    fake_cls.assert_called_once_with(
        endpoint="https://resource.services.ai.azure.com/openai/v1",
        credential="secret",
        model="Kimi-Prod",
        temperature=0.2,
    )
