"""Entry point for running the backend API server."""

from .api import run_server
from .config import get_logger

if __name__ == "__main__":
    # Initialize logger
    get_logger()
    # Run the server
    run_server(reload=True)