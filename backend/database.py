"""Database management for Vito's Pizza Cafe application."""

import sqlite3
import logging
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_deepseek import ChatDeepSeek

from .config import Config

logger = logging.getLogger(__name__)

def get_engine_for_customer_db(sql_file_path: str):
    """Read the local SQL file content, fill the memory database, and create the engine."""
    try:
        # Read the local SQL file content
        with open(sql_file_path, "r", encoding="utf-8") as file:
            sql_script = file.read()

        # Create a memory SQLite database connection
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.executescript(sql_script)

        # Create SQLAlchemy engine
        engine = create_engine(
            "sqlite://",
            creator=lambda: connection,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )

        logger.info(f"Database loaded successfully from {sql_file_path}")
        return engine

    except FileNotFoundError:
        logger.error(f"Database file not found: {sql_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        raise

@lru_cache(maxsize=1)
def setup_database_tools():
    """Set up database connection and tools."""
    # Initialize LLM for database operations
    llm = ChatDeepSeek(
        model=Config.LLM_MODEL,
        temperature=Config.LLM_TEMPERATURE,
        max_tokens=None,
        timeout=None,
        max_retries=Config.LLM_MAX_RETRIES,
    )

    # Create database engine and connection
    engine = get_engine_for_customer_db(Config.DATABASE_PATH)
    db = SQLDatabase(engine)

    # Create SQL toolkit
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    logger.info(f"Database tools initialized: {len(tools)} tools available")
    return tools, llm

def get_database_tools():
    """Get cached database tools and LLM."""
    return setup_database_tools()