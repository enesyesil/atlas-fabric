"""
model_factory.py — THE ONLY FILE THAT IMPORTS LLM PROVIDER CLASSES.

Agent code NEVER imports ChatAnthropic, ChatOpenAI, etc. directly.
Always call:
    from agents.model_factory import get_model
    llm = get_model(role="generator")
"""

import os
from typing import Literal
from urllib.parse import urlparse

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
    return ChatMistralAI(model_name=model_name, temperature=temperature)


def _load_azure(model_name: str, temperature: float) -> BaseChatModel:
    # Azure AI Foundry — official LangChain Azure AI integration.
    # Required env vars:
    #   AZURE_API_BASE  = https://<resource>.services.ai.azure.com/openai/v1
    #   AZURE_API_KEY   = <your-azure-ai-foundry-key>
    # Usage: GENERATOR_MODEL=azure/<deployment-name>
    base_url = os.environ.get("AZURE_API_BASE")
    api_key = os.environ.get("AZURE_API_KEY")
    if not base_url:
        raise ValueError(
            "AZURE_API_BASE is not set. "
            "Example: https://<resource>.services.ai.azure.com/openai/v1"
        )
    if not api_key:
        raise ValueError("AZURE_API_KEY is not set.")

    endpoint = _validate_azure_endpoint(base_url)
    deployment_name = _validate_azure_deployment_name(model_name)

    try:
        from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
    except ImportError as exc:
        raise ImportError(
            "langchain-azure-ai is not installed. "
            "Install project dependencies again to use azure/<deployment-name> models."
        ) from exc

    return AzureAIChatCompletionsModel(
        endpoint=endpoint,
        credential=api_key,
        model=deployment_name,
        temperature=temperature,
    )


def _validate_azure_endpoint(base_url: str) -> str:
    endpoint = base_url.strip().rstrip("/")
    if not endpoint:
        raise ValueError(
            "AZURE_API_BASE must be set to a direct Foundry endpoint ending in /openai/v1."
        )

    legacy_markers = ("/models", "/chat/completions", "api-version=")
    if any(marker in endpoint.lower() for marker in legacy_markers):
        raise ValueError(
            "AZURE_API_BASE is using the deprecated Azure AI Inference request URL format. "
            "Use the direct Foundry OpenAI-compatible endpoint root ending in /openai/v1, "
            "for example https://<resource>.services.ai.azure.com/openai/v1. "
            "GENERATOR_MODEL and REVIEWER_MODEL must use the deployment name: "
            "azure/<deployment-name>."
        )

    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(
            "AZURE_API_BASE must be a valid https URL ending in /openai/v1."
        )
    if not parsed.path.endswith("/openai/v1"):
        raise ValueError(
            "AZURE_API_BASE must point to the direct Foundry OpenAI-compatible endpoint root "
            "ending in /openai/v1, for example "
            "https://<resource>.services.ai.azure.com/openai/v1."
        )
    return endpoint


def _validate_azure_deployment_name(model_name: str) -> str:
    deployment_name = model_name.strip()
    if not deployment_name:
        raise ValueError(
            "Azure model strings must use the deployment name. "
            "Example: GENERATOR_MODEL=azure/<deployment-name>"
        )
    return deployment_name
