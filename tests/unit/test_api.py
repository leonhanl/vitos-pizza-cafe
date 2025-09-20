"""Integration tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from backend.api import app


class TestVitosAPI:
    """Integration tests for Vito's Pizza Cafe API."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Welcome to Vito's Pizza Cafe API" in data["message"]

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "running" in data["message"]

    @patch('backend.api.get_or_create_chat_service')
    def test_chat_endpoint_success(self, mock_get_service):
        """Test successful chat request."""
        # Mock chat service
        mock_service = Mock()
        mock_service.process_query.return_value = "Hello! I'm here to help."
        mock_get_service.return_value = mock_service

        # Send chat request
        response = self.client.post("/api/v1/chat", json={
            "message": "Hello",
            "conversation_id": "test_conversation"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Hello! I'm here to help."
        assert data["conversation_id"] == "test_conversation"

        # Verify service was called correctly
        mock_get_service.assert_called_once_with("test_conversation")
        mock_service.process_query.assert_called_once_with("Hello")

    @patch('backend.api.get_or_create_chat_service')
    def test_chat_endpoint_default_conversation(self, mock_get_service):
        """Test chat request with default conversation ID."""
        mock_service = Mock()
        mock_service.process_query.return_value = "Response"
        mock_get_service.return_value = mock_service

        response = self.client.post("/api/v1/chat", json={
            "message": "Test message"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == "default"
        mock_get_service.assert_called_once_with("default")

    def test_chat_endpoint_missing_message(self):
        """Test chat request with missing message."""
        response = self.client.post("/api/v1/chat", json={
            "conversation_id": "test"
        })

        assert response.status_code == 422  # Validation error

    @patch('backend.api.get_or_create_chat_service')
    def test_chat_endpoint_service_error(self, mock_get_service):
        """Test chat endpoint when service throws error."""
        mock_service = Mock()
        mock_service.process_query.side_effect = Exception("Service error")
        mock_get_service.return_value = mock_service

        response = self.client.post("/api/v1/chat", json={
            "message": "Test message",
            "conversation_id": "test"
        })

        assert response.status_code == 500

    @patch('backend.api.list_conversations')
    def test_get_conversations(self, mock_list_conversations):
        """Test getting conversations list."""
        mock_list_conversations.return_value = ["conv1", "conv2", "conv3"]

        response = self.client.get("/api/v1/conversations")

        assert response.status_code == 200
        data = response.json()
        assert data == ["conv1", "conv2", "conv3"]

    @patch('backend.api.get_or_create_chat_service')
    def test_get_conversation_history(self, mock_get_service):
        """Test getting conversation history."""
        mock_service = Mock()
        mock_service.get_conversation_history.return_value = [
            {"user": "Hello", "assistant": "Hi there!"}
        ]
        mock_get_service.return_value = mock_service

        response = self.client.get("/api/v1/conversations/test_conv/history")

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == "test_conv"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["user"] == "Hello"

    @patch('backend.api.delete_conversation')
    def test_delete_conversation_success(self, mock_delete):
        """Test successful conversation deletion."""
        mock_delete.return_value = True

        response = self.client.delete("/api/v1/conversations/test_conv")

        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]
        mock_delete.assert_called_once_with("test_conv")

    @patch('backend.api.delete_conversation')
    def test_delete_conversation_not_found(self, mock_delete):
        """Test deleting non-existent conversation."""
        mock_delete.return_value = False

        response = self.client.delete("/api/v1/conversations/nonexistent")

        assert response.status_code == 404

    @patch('backend.api.get_or_create_chat_service')
    def test_clear_conversation_history(self, mock_get_service):
        """Test clearing conversation history."""
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        response = self.client.post("/api/v1/conversations/test_conv/clear")

        assert response.status_code == 200
        data = response.json()
        assert "history cleared successfully" in data["message"]
        mock_service.clear_history.assert_called_once()

    def test_invalid_endpoint(self):
        """Test accessing invalid endpoint."""
        response = self.client.get("/api/v1/invalid")
        assert response.status_code == 404

    def test_chat_endpoint_large_message(self):
        """Test chat endpoint with large message."""
        large_message = "A" * 10000  # 10KB message

        with patch('backend.api.get_or_create_chat_service') as mock_get_service:
            mock_service = Mock()
            mock_service.process_query.return_value = "Processed large message"
            mock_get_service.return_value = mock_service

            response = self.client.post("/api/v1/chat", json={
                "message": large_message,
                "conversation_id": "test"
            })

            assert response.status_code == 200


class TestAPIErrorHandling:
    """Test API error handling scenarios."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_malformed_json(self):
        """Test handling of malformed JSON."""
        response = self.client.post(
            "/api/v1/chat",
            content=b"invalid json",
            headers={"content-type": "application/json"}
        )
        assert response.status_code == 422

    def test_empty_request_body(self):
        """Test handling of empty request body."""
        response = self.client.post("/api/v1/chat")
        assert response.status_code == 422