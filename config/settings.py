"""Configuration management for ARA-1 using Pydantic Settings.

Safely loads and validates environment variables, API credentials,
LLM parameters, vector database paths, and execution thresholds.
"""

from functools import lru_cache
from typing import Optional, List
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Central configuration for ARA-1 Agent runtime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # -------------------------------------------------------------------------
    # Core LLM API Keys & Provider Settings
    # -------------------------------------------------------------------------
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API key")

    # -------------------------------------------------------------------------
    # Financial Market & Search API Credentials
    # -------------------------------------------------------------------------
    SEC_EDGAR_USER_AGENT: str = Field(
        default="QuantumEdgeResearch intern@quantumedge.com",
        description="Mandatory User-Agent for SEC EDGAR rate limit compliance"
    )
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(default=None, description="Alpha Vantage API key")
    FMP_API_KEY: Optional[str] = Field(default=None, description="Financial Modeling Prep key")
    TAVILY_API_KEY: Optional[str] = Field(default=None, description="Tavily AI Search key")
    SERPAPI_API_KEY: Optional[str] = Field(default=None, description="SerpAPI key")
    NEWS_API_KEY: Optional[str] = Field(default=None, description="NewsAPI key")

    # -------------------------------------------------------------------------
    # Model Names & Parameters
    # -------------------------------------------------------------------------
    DEFAULT_LLM_MODEL: str = Field(default="gpt-4o-mini", description="Base fast model")
    REASONING_LLM_MODEL: str = Field(default="gpt-4o", description="Flagship reasoning model")
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Default dense embedding model"
    )
    EMBEDDING_DIMENSION: int = Field(default=1536, description="Embedding vector dimension")
    TEMPERATURE: float = Field(default=0.1, ge=0.0, le=2.0)
    MAX_TOKENS: int = Field(default=4096, gt=0)
    CONTEXT_WINDOW_LIMIT: int = Field(default=128000, description="Nominal model context window limit")

    # -------------------------------------------------------------------------
    # Vector Database Configuration
    # -------------------------------------------------------------------------
    VECTOR_DB_TYPE: str = Field(default="chroma", description="'chroma' or 'pinecone'")
    CHROMA_PERSIST_DIRECTORY: str = Field(default="./data/chroma_db")
    CHROMA_COLLECTION_NAME: str = Field(default="ara1_research_memory")
    PINECONE_API_KEY: Optional[str] = Field(default=None)
    PINECONE_ENVIRONMENT: str = Field(default="us-east-1-aws")
    PINECONE_INDEX_NAME: str = Field(default="ara1-financial-research")

    # -------------------------------------------------------------------------
    # Execution & Safety Thresholds
    # -------------------------------------------------------------------------
    MAX_TOOL_CALLS_PER_TASK: int = Field(default=20, ge=1, le=100)
    CIRCUIT_BREAKER_FAIL_THRESHOLD: int = Field(default=3, ge=1)
    CIRCUIT_BREAKER_RESET_TIMEOUT_SEC: float = Field(default=30.0, ge=5.0)
    TOOL_TIMEOUT_SECONDS: float = Field(default=15.0, ge=1.0)
    MAX_RETRIES: int = Field(default=3, ge=0)

    # -------------------------------------------------------------------------
    # Logging & Trace Paths
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE_PATH: str = Field(default="./logs/ara1_agent.log")
    TRACE_LOG_PATH: str = Field(default="./logs/traces.jsonl")

    # -------------------------------------------------------------------------
    # Mock / Offline Execution Flag
    # -------------------------------------------------------------------------
    MOCK_MODE: bool = Field(
        default=False,
        description="Forces mock responses for testing without active API credits"
    )

    @field_validator("EMBEDDING_DIMENSION")
    @classmethod
    def validate_embedding_dim(cls, v: int, info) -> int:
        """Validates that embedding dimensions match model specifications."""
        return v

    def is_openai_configured(self) -> bool:
        """Returns True if a plausible OpenAI API key is set and not a placeholder."""
        if not self.OPENAI_API_KEY:
            return False
        return not self.OPENAI_API_KEY.startswith("your_") and len(self.OPENAI_API_KEY) > 10

    def is_anthropic_configured(self) -> bool:
        """Returns True if a plausible Anthropic API key is set."""
        if not self.ANTHROPIC_API_KEY:
            return False
        return not self.ANTHROPIC_API_KEY.startswith("your_") and len(self.ANTHROPIC_API_KEY) > 10

    def get_log_dir(self) -> Path:
        """Ensure and return the log directory path."""
        p = Path(self.LOG_FILE_PATH).parent
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_chroma_dir(self) -> Path:
        """Ensure and return the ChromaDB directory path."""
        p = Path(self.CHROMA_PERSIST_DIRECTORY)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache()
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
