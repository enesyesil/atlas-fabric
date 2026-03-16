"""
model_factory.py — THE ONLY FILE THAT IMPORTS LLM PROVIDER CLASSES.

Agent code NEVER imports ChatAnthropic, ChatOpenAI, etc. directly.
Always call:
    from agents.model_factory import get_model
    llm = get_model(role="generator")
"""

import os
from typing import Literal

from langchain_core.language_models import BaseChatModel


Role = Literal["generator", "reviewer"]

_PROVIDER_MAP: dict[str, str] = {
    "anthropic": "_load_anthropic",
    "openai":    "_load_openai",
    "google":    "_load_google",
    "ollama":    "_load_ollama",
    "groq":      "_load_groq",
    "mistral":   "_load_mistral",
    "azure":     "_load_azure",
}


def get_model(role: Role) -> BaseChatModel:
    """
    Return a configured LLM for the given role.

    Reads from environment:
        GENERATOR_MODEL=anthropic/claude-opus-4-5
        REVIEWER_MODEL=openai/gpt-4o
        GENERATOR_TEMPERATURE=0.2
        REVIEWER_TEMPERATURE=0.0

    Format: {provider}/{model_name}
    Supported providers: anthropic, openai, google, ollama, groq, mistral, azure
    """
    env_key = f"{role.upper()}_MODEL"
    model_string = os.environ.get(env_key)
    if not model_string:
        raise ValueError(
            f"Environment variable {env_key} is not set. "
            f"Example: {env_key}=anthropic/claude-opus-4-5"
        )

    temp_key = f"{role.upper()}_TEMPERATURE"
    temperature = float(os.environ.get(temp_key, "0.0"))

    return _build_model(model_string, temperature)


def _build_model(model_string: str, temperature: float) -> BaseChatModel:
    if "/" not in model_string:
        raise ValueError(
            f"Invalid model string '{model_string}'. "
            "Expected format: provider/model_name (e.g. anthropic/claude-opus-4-5)"
        )

    provider, model_name = model_string.split("/", 1)

    if provider not in _PROVIDER_MAP:
        raise ValueError(
            f"Unsupported provider '{provider}'. "
            f"Supported: {list(_PROVIDER_MAP.keys())}"
        )

    loader = globals()[_PROVIDER_MAP[provider]]
    return loader(model_name, temperature)


# ── Provider loaders ────────────────────────────────────────────────────────
# These are the ONLY places provider-specific classes are imported.

def _load_anthropic(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=model_name, temperature=temperature)  # type: ignore[call-arg]


def _load_openai(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model_name, temperature=temperature)


def _load_google(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)


def _load_ollama(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model_name, temperature=temperature)


def _load_groq(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_groq import ChatGroq
    return ChatGroq(model=model_name, temperature=temperature)


def _load_mistral(model_name: str, temperature: float) -> BaseChatModel:
    from langchain_mistralai import ChatMistralAI
    return ChatMistralAI(model=model_name, temperature=temperature)


def _load_azure(model_name: str, temperature: float) -> BaseChatModel:
    # Azure AI Foundry — OpenAI-compatible serverless endpoint.
    # Required env vars:
    #   AZURE_API_BASE  = https://<your-endpoint>.inference.ai.azure.com
    #   AZURE_API_KEY   = <your-azure-ai-foundry-key>
    # Usage: GENERATOR_MODEL=azure/kimi-k2-5
    from langchain_openai import ChatOpenAI
    base_url = os.environ.get("AZURE_API_BASE")
    api_key = os.environ.get("AZURE_API_KEY")
    if not base_url:
        raise ValueError("AZURE_API_BASE is not set. Example: https://your-endpoint.inference.ai.azure.com")
    if not api_key:
        raise ValueError("AZURE_API_KEY is not set.")
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        api_key=api_key,  # type: ignore[arg-type]
    )
