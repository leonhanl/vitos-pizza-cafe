"""Unit tests for chat service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from backend.chat_service import ChatService, get_or_create_chat_service, delete_conversation


class TestChatService:
    """Test cases for ChatService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.conversation_id = "test_conversation"
        self.chat_service = ChatService(self.conversation_id)

    def test_init(self):
        """Test ChatService initialization."""
        assert self.chat_service.conversation_id == self.conversation_id
        assert self.chat_service.conversation_history == []

    @patch('backend.chat_service.retrieve_context')
    @patch('backend.chat_service.get_database_tools')
    @patch('backend.chat_service.create_react_agent')
    def test_process_query_success(self, mock_create_agent, mock_get_tools, mock_retrieve_context):
        """Test successful query processing."""
        # Mock dependencies
        mock_retrieve_context.return_value = "<context>Test context</context>"
        mock_tools = [Mock()]
        mock_llm = Mock()
        mock_get_tools.return_value = (mock_tools, mock_llm)

        # Mock React agent
        mock_agent = Mock()
        mock_result = {
            "messages": [
                Mock(content="Test response")
            ]
        }
        mock_agent.invoke.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        # Test query processing
        user_input = "What's on the menu?"
        result = self.chat_service.process_query(user_input)

        # Assertions
        assert result == "Test response"
        mock_retrieve_context.assert_called_once_with(user_input)
        mock_get_tools.assert_called_once()
        mock_create_agent.assert_called_once_with(model=mock_llm, tools=mock_tools)

        # Check conversation history was updated
        assert len(self.chat_service.conversation_history) == 2
        assert isinstance(self.chat_service.conversation_history[0], HumanMessage)
        assert isinstance(self.chat_service.conversation_history[1], AIMessage)

    @patch('backend.chat_service.retrieve_context')
    def test_process_query_error_handling(self, mock_retrieve_context):
        """Test error handling in query processing."""
        # Mock exception
        mock_retrieve_context.side_effect = Exception("Test error")

        user_input = "Test query"
        result = self.chat_service.process_query(user_input)

        assert "I apologize, but I encountered an error" in result

    def test_get_conversation_history_empty(self):
        """Test getting empty conversation history."""
        history = self.chat_service.get_conversation_history()
        assert history == []

    def test_get_conversation_history_with_messages(self):
        """Test getting conversation history with messages."""
        # Add test messages
        self.chat_service.conversation_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm doing well!")
        ]

        history = self.chat_service.get_conversation_history()

        expected = [
            {"user": "Hello", "assistant": "Hi there!"},
            {"user": "How are you?", "assistant": "I'm doing well!"}
        ]
        assert history == expected

    def test_clear_history(self):
        """Test clearing conversation history."""
        # Add some messages
        self.chat_service.conversation_history = [
            HumanMessage(content="Test"),
            AIMessage(content="Response")
        ]

        # Clear history
        self.chat_service.clear_history()

        assert self.chat_service.conversation_history == []


class TestChatServiceGlobalFunctions:
    """Test global functions for chat service management."""

    def setup_method(self):
        """Clean up conversations before each test."""
        from backend.chat_service import _conversations
        _conversations.clear()

    def test_get_or_create_chat_service_new(self):
        """Test creating new chat service."""
        conversation_id = "new_conversation"
        service = get_or_create_chat_service(conversation_id)

        assert isinstance(service, ChatService)
        assert service.conversation_id == conversation_id

    def test_get_or_create_chat_service_existing(self):
        """Test getting existing chat service."""
        conversation_id = "existing_conversation"

        # Create first service
        service1 = get_or_create_chat_service(conversation_id)
        # Get same service again
        service2 = get_or_create_chat_service(conversation_id)

        assert service1 is service2

    def test_delete_conversation_existing(self):
        """Test deleting existing conversation."""
        conversation_id = "to_delete"

        # Create conversation
        get_or_create_chat_service(conversation_id)

        # Delete it
        result = delete_conversation(conversation_id)
        assert result is True

        # Verify it's deleted (new service should be created)
        new_service = get_or_create_chat_service(conversation_id)
        assert new_service.conversation_history == []

    def test_delete_conversation_nonexistent(self):
        """Test deleting non-existent conversation."""
        result = delete_conversation("nonexistent")
        assert result is False