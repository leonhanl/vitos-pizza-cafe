"""Configuration management for Vito's Pizza Cafe application."""

import os
import logging
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API Default Base URL
# This is OpenAI's official endpoint. If OpenAI changes this, they'll maintain
# backward compatibility on v1 and update their SDK accordingly.
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"

class Config:
    """Application configuration settings."""

    # Required API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or OPENAI_DEFAULT_BASE_URL

    # AMAP Configuration
    AMAP_API_KEY = os.getenv("AMAP_API_KEY")
    AMAP_SSE_ENABLED = os.getenv("AMAP_SSE_ENABLED", "false").lower() == "true"
    AMAP_STDIO_ENABLED = os.getenv("AMAP_STDIO_ENABLED", "false").lower() == "true"

    # PAN MCP Relay Configuration
    PAN_MCP_RELAY_ENABLED = os.getenv("PAN_MCP_RELAY_ENABLED", "false").lower() == "true"
    PAN_MCP_RELAY_URL = os.getenv("PAN_MCP_RELAY_URL", "http://127.0.0.1:8800/mcp/")

    # Embedding API Configuration
    # Note: OPENAI_EMBEDDING_BASE_URL defaults to OpenAI's endpoint, NOT to OPENAI_BASE_URL
    # This prevents errors when LLM uses a provider that doesn't support OpenAI embeddings
    OPENAI_EMBEDDING_API_KEY = os.getenv("OPENAI_EMBEDDING_API_KEY") or OPENAI_API_KEY
    OPENAI_EMBEDDING_BASE_URL = os.getenv("OPENAI_EMBEDDING_BASE_URL") or OPENAI_DEFAULT_BASE_URL

    # Optional API Keys
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false")
    LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "vitos-pizza-cafe")

    # AIRS (AI Runtime Security) Configuration
    AIRS_ENABLED = os.getenv("AIRS_ENABLED", "false").lower() == "true"
    X_PAN_TOKEN = os.getenv("X_PAN_TOKEN")
    X_PAN_AI_MODEL = os.getenv("X_PAN_AI_MODEL", "gpt-5-mini")
    X_PAN_APP_NAME = os.getenv("X_PAN_APP_NAME", "Vitos Pizza Cafe")
    X_PAN_APP_USER = os.getenv("X_PAN_APP_USER", "Vitos-Admin")
    X_PAN_INPUT_CHECK_PROFILE_NAME = os.getenv("X_PAN_INPUT_CHECK_PROFILE_NAME", "Demo-Profile-for-Input")
    X_PAN_OUTPUT_CHECK_PROFILE_NAME = os.getenv("X_PAN_OUTPUT_CHECK_PROFILE_NAME", "Demo-Profile-for-Output")

    # AIRS Streaming Scan Configuration
    AIRS_STREAM_SCAN_CHUNK_INTERVAL = int(os.getenv("AIRS_STREAM_SCAN_CHUNK_INTERVAL", "50"))

    # Application Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "Vitos-Pizza-Cafe-KB")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "customer_db.sql")

    # Model Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5-mini")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

    # Embedding Configuration
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    RERANK_MODEL = os.getenv("RERANK_MODEL", "rerank-english-v3.0")

    # RAG Configuration
    SIMILARITY_SEARCH_K = int(os.getenv("SIMILARITY_SEARCH_K", "5"))
    RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "3"))
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

    # MCP Configuration
    # Format: {"server_name": {"url": "https://...", "transport": "sse", ...}}
    # Multiple transport types are supported: sse, stdio, streamable_http, websocket
    # Both SSE and STDIO transports share the same AMAP_API_KEY for simplicity in this demo.
    # Example:
    # MCP_SERVERS = {
    #     "amap-sse": {
    #         "url": "https://mcp.amap.com/sse?key=YOUR_API_KEY",
    #         "transport": "sse"
    #     },
    #     "amap-stdio": {
    #         "command": "uvx",
    #         "args": ["amap-mcp-server"],
    #         "transport": "stdio",
    #         "env": {"AMAP_MAPS_API_KEY": "YOUR_API_KEY"}
    #     }
    # }
    MCP_SERVERS = {}
    if AMAP_SSE_ENABLED and AMAP_API_KEY:
        MCP_SERVERS["amap-sse"] = {
            "url": f"https://mcp.amap.com/sse?key={AMAP_API_KEY}",
            "transport": "sse"
        }
    if AMAP_STDIO_ENABLED and AMAP_API_KEY:
        MCP_SERVERS["amap-stdio"] = {
            "command": "npx",
            "args": ["-y", "@amap/amap-maps-mcp-server"],
            "transport": "stdio",
            "env": {"AMAP_MAPS_API_KEY": AMAP_API_KEY}
        }
    if PAN_MCP_RELAY_ENABLED:
        MCP_SERVERS["pan-mcp-relay"] = {
            "url": PAN_MCP_RELAY_URL,
            "transport": "streamable_http"
        }

    @classmethod
    def validate_required_vars(cls):
        """Validate that all required environment variables are set."""
        required_vars = [
            "OPENAI_API_KEY"
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
        os.environ["OPENAI_API_KEY"] = cls.OPENAI_API_KEY
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