"""Database management for Vito's Pizza Cafe application."""

import sqlite3
import logging
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit

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

_db_engine = None

def get_database_tools(llm):
    """Get database tools, initializing once and reusing the engine.

    Args:
        llm: Language model instance to use for database operations

    Returns:
        list: Database tools for SQL operations
    """
    global _db_engine

    # Initialize database engine once (singleton pattern)
    if _db_engine is None:
        _db_engine = get_engine_for_customer_db(Config.DATABASE_PATH)
        logger.info(f"Database engine initialized from {Config.DATABASE_PATH}")

    # Create database connection
    db = SQLDatabase(_db_engine)

    # Create SQL toolkit with the provided LLM
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()

    logger.info(f"Database tools initialized: {len(tools)} tools available")
    return tools