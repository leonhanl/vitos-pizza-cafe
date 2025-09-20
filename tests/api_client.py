"""API client for communicating with the backend API."""

import httpx
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class VitosApiClient:
    """HTTP client for Vito's Pizza Cafe backend API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API client with base URL."""
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
        logger.info(f"VitosApiClient initialized with base_url: {self.base_url}")

    def chat(self, message: str, conversation_id: str = "default") -> str:
        """Send a chat message and get response."""
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/chat",
                json={
                    "message": message,
                    "conversation_id": conversation_id
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["response"]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during chat: {e.response.status_code} - {e.response.text}")
            return f"Sorry, I encountered an error: {e.response.status_code}. Please try again."
        except httpx.RequestError as e:
            logger.error(f"Request error during chat: {e}")
            return "Sorry, I couldn't connect to the service. Please check if the backend is running."
        except Exception as e:
            logger.error(f"Unexpected error during chat: {e}")
            return "Sorry, I encountered an unexpected error. Please try again."

    def get_conversations(self) -> List[str]:
        """Get list of active conversation IDs."""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/conversations")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting conversations: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error getting conversations: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting conversations: {e}")
            return []

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a specific conversation."""
        try:
            response = self.client.get(
                f"{self.base_url}/api/v1/conversations/{conversation_id}/history"
            )
            response.raise_for_status()
            data = response.json()
            return data["messages"]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting history: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error getting history: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting history: {e}")
            return []

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        try:
            response = self.client.delete(
                f"{self.base_url}/api/v1/conversations/{conversation_id}"
            )
            response.raise_for_status()
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting conversation: {e.response.status_code}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Request error deleting conversation: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting conversation: {e}")
            return False

    def clear_conversation_history(self, conversation_id: str) -> bool:
        """Clear conversation history."""
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/conversations/{conversation_id}/clear"
            )
            response.raise_for_status()
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error clearing history: {e.response.status_code}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Request error clearing history: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error clearing history: {e}")
            return False

    def health_check(self) -> bool:
        """Check if the backend API is healthy."""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/health")
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()