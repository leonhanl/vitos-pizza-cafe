"""Configuration management for Vito's Pizza Cafe application."""

import os
import logging
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration settings."""

    # Required API Keys
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

    # Optional API Keys
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false")
    LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "vitos-pizza-cafe")

    # Application Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "Vitos-Pizza-Cafe-KB")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "customer_db.sql")

    # Model Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

    # Embedding Configuration
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embed-english-v3.0")
    RERANK_MODEL = os.getenv("RERANK_MODEL", "rerank-english-v3.0")

    # RAG Configuration
    SIMILARITY_SEARCH_K = int(os.getenv("SIMILARITY_SEARCH_K", "5"))
    RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "3"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

    @classmethod
    def validate_required_vars(cls):
        """Validate that all required environment variables are set."""
        required_vars = [
            "COHERE_API_KEY",
            "DEEPSEEK_API_KEY"
        ]

        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please ensure you have created a .env file and configured all necessary API keys.\n"
                "You can refer to the .env.example file for configuration."
            )

    @classmethod
    def setup_environment(cls):
        """Set up environment variables for external libraries."""
        os.environ["DEEPSEEK_API_KEY"] = cls.DEEPSEEK_API_KEY
        os.environ["COHERE_API_KEY"] = cls.COHERE_API_KEY
        os.environ["LANGSMITH_TRACING"] = cls.LANGSMITH_TRACING
        if cls.LANGSMITH_API_KEY:
            os.environ["LANGSMITH_API_KEY"] = cls.LANGSMITH_API_KEY
        os.environ["LANGSMITH_ENDPOINT"] = cls.LANGSMITH_ENDPOINT
        os.environ["LANGSMITH_PROJECT"] = cls.LANGSMITH_PROJECT

    @classmethod
    @lru_cache(maxsize=1)
    def setup_logging(cls):
        """Configure logging for the application."""
        logging.basicConfig(level=getattr(logging, cls.LOG_LEVEL))

        # Set third-party library log levels to WARNING
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("faiss").setLevel(logging.WARNING)
        logging.getLogger("langchain").setLevel(logging.WARNING)
        logging.getLogger("langgraph").setLevel(logging.WARNING)

        return logging.getLogger(__name__)

@lru_cache(maxsize=1)
def initialize_config():
    """Initialize configuration with validation and environment setup."""
    Config.validate_required_vars()
    Config.setup_environment()
    return Config.setup_logging()

# Get logger through lazy initialization
def get_logger():
    """Get configured logger."""
    return initialize_config()

# For backward compatibility, initialize immediately
logger = get_logger()