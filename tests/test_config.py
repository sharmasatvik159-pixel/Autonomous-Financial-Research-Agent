"""Unit tests for configuration management."""

import os
from config.settings import Settings, get_settings

def test_settings_defaults():
    """Verify default configurations adhere to system specifications."""
    settings = get_settings()

    assert settings.DEFAULT_LLM_MODEL == "gpt-4o-mini"
    assert settings.REASONING_LLM_MODEL == "gpt-4o"
    assert settings.EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.EMBEDDING_DIMENSION == 1536
    assert settings.VECTOR_DB_TYPE == "chroma"
    assert settings.MAX_TOOL_CALLS_PER_TASK == 20
    assert "QuantumEdgeResearch" in settings.SEC_EDGAR_USER_AGENT

def test_settings_api_configuration_checks():
    """Verify API availability checker logic."""
    test_settings = Settings(
        OPENAI_API_KEY="sk-proj-test1234567890abcdef",
        ANTHROPIC_API_KEY="your_anthropic_api_key_here"
    )

    assert test_settings.is_openai_configured() is True
    assert test_settings.is_anthropic_configured() is False
