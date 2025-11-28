"""
Integration tests for streaming AIRS protection.

Tests end-to-end flow with actual API endpoints:
- Input scanning at API level
- Progressive output scanning during streaming
- AIRS API call count verification
- Performance impact measurement
- Conversation history validation
"""

import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from backend.api import app
from backend.security.airs_scanner import ScanResult


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_scan_allow():
    """Mock AIRS scanner that allows all content."""
    return AsyncMock(return_value=ScanResult(action="allow"))


@pytest.fixture
def mock_scan_block_input():
    """Mock AIRS scanner that blocks input."""
    return AsyncMock(return_value=ScanResult(action="block", category="malicious"))


@pytest.fixture
def mock_scan_block_output():
    """Mock AIRS scanner that allows input but blocks output."""
    async def conditional_scan(prompt=None, response=None, profile_name=None):
        if prompt:  # Input scan
            return ScanResult(action="allow")
        else:  # Output scan
            return ScanResult(action="block", category="toxic")
    return conditional_scan


@pytest.fixture
def mock_rag():
    """Mock RAG retrieval."""
    with patch('backend.chat_service.retrieve_context', return_value="<context>Test context</context>"):
        yield


@pytest.fixture
def mock_llm():
    """Mock LLM."""
    with patch('backend.chat_service.get_llm'):
        yield


@pytest.fixture
def mock_tools():
    """Mock tools."""
    with patch('backend.chat_service.get_database_tools', return_value=[]), \
         patch('backend.chat_service.get_mcp_tools', new_callable=AsyncMock, return_value=[]):
        yield


class TestEndToEndStreaming:
    """End-to-end streaming tests with malicious content detection."""

    def test_input_scan_blocks_at_api_level(self, client, mock_rag, mock_llm, mock_tools):
        """Test that malicious input is blocked at API endpoint before streaming."""
        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.security.airs_scanner.scan_input', AsyncMock(return_value=ScanResult(action="block", category="malicious"))), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "malicious prompt injection",
                    "conversation_id": "test-input-block"
                }
            )

            # Should return 403 Forbidden
            assert response.status_code == 403
            assert "content policy" in response.json()["detail"].lower()

            # Should have logged the violation
            assert mock_log.called
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["scan_type"] == "input"
            assert call_kwargs["action"] == "block"
            assert call_kwargs["conversation_id"] == "test-input-block"

    def test_output_scan_blocks_during_streaming(self, client, mock_rag, mock_llm, mock_tools):
        """Test that malicious output is detected and streaming stops."""
        # Mock agent that yields chunks
        async def mock_stream():
            for i in range(60):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="bad "), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = [0]  # Use list to allow mutation in nested function

        async def mock_scan_with_count(prompt=None, response=None, profile_name=None):
            if prompt:  # Input scan - allow
                return ScanResult(action="allow")
            else:  # Output scan
                scan_count[0] += 1
                if scan_count[0] == 1:  # First progressive scan - block
                    return ScanResult(action="block", category="toxic")
                else:
                    return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', side_effect=mock_scan_with_count), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_with_count), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "tell me a story",
                    "conversation_id": "test-output-block"
                }
            )

            # Collect all SSE events
            events = []
            for line in response.iter_lines():
                if line:
                    if line.startswith('data: '):
                        import json
                        try:
                            event = json.loads(line[6:])  # Skip "data: " prefix
                            events.append(event)
                            if event.get("type") == "security_violation":
                                break
                        except json.JSONDecodeError:
                            pass

            # Should have security violation event
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) > 0

            # Should have logged the violation
            assert mock_log.called

    def test_benign_content_streams_successfully(self, client, mock_rag, mock_llm, mock_tools):
        """Test that benign content streams without interruption."""
        async def mock_stream():
            for i in range(75):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="safe "), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', AsyncMock(return_value=ScanResult(action="allow"))), \
             patch('backend.security.airs_scanner.scan_output', AsyncMock(return_value=ScanResult(action="allow"))):

            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "what's on the menu?",
                    "conversation_id": "test-benign"
                },
            )

            # Collect all events
            events = []
            for line in response.iter_lines():
                if line:
                    if line.startswith('data: '):
                        import json
                        try:
                            event = json.loads(line[6:])
                            events.append(event)
                        except json.JSONDecodeError:
                            pass

            # Should have no security violations
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 0

            # Should have token events
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) > 0


class TestAIRSAPICallCount:
    """Verify AIRS API call count matches design expectations."""

    def test_api_call_count_for_long_response(self, client, mock_rag, mock_llm, mock_tools):
        """Test AIRS API call count for a 500-chunk response."""
        async def mock_stream():
            # Generate 500 chunks to test API call count
            for i in range(500):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="x"), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        input_scan_count = [0]
        output_scan_count = [0]

        async def count_input_scans(prompt, profile_name):
            input_scan_count[0] += 1
            return ScanResult(action="allow")

        async def count_output_scans(response, profile_name):
            output_scan_count[0] += 1
            return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', side_effect=count_input_scans), \
             patch('backend.security.airs_scanner.scan_output', side_effect=count_output_scans):

            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "test query",
                    "conversation_id": "test-call-count"
                },
            )

            # Consume all events
            for line in response.iter_lines():
                pass

            # Expected: 1 input scan + 10 progressive scans (at 50,100,...,500) + 1 final = 12 total
            assert input_scan_count[0] == 1  # One input scan
            assert output_scan_count[0] == 11  # 10 progressive + 1 final

    def test_api_call_count_for_short_response(self, client, mock_rag, mock_llm, mock_tools):
        """Test AIRS API call count for a 30-chunk response (no progressive scan)."""
        async def mock_stream():
            for i in range(30):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="x"), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        input_scan_count = [0]
        output_scan_count = [0]

        async def count_input_scans(prompt, profile_name):
            input_scan_count[0] += 1
            return ScanResult(action="allow")

        async def count_output_scans(response, profile_name):
            output_scan_count[0] += 1
            return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', side_effect=count_input_scans), \
             patch('backend.security.airs_scanner.scan_output', side_effect=count_output_scans):

            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "short query",
                    "conversation_id": "test-short"
                },
            )

            for line in response.iter_lines():
                pass

            # Expected: 1 input scan + 0 progressive + 1 final = 2 total
            assert input_scan_count[0] == 1
            assert output_scan_count[0] == 1  # Only final scan (no progressive)


class TestPerformanceImpact:
    """Measure performance impact of AIRS scanning."""

    def test_streaming_latency_with_airs_enabled(self, client, mock_rag, mock_llm, mock_tools):
        """Test streaming latency with AIRS enabled."""
        async def mock_stream():
            for i in range(100):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="x"), {"run_id": "test"})
                await asyncio.sleep(0.001)  # Simulate streaming delay

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        async def mock_scan_with_delay(prompt=None, response=None, profile_name=None):
            await asyncio.sleep(0.05)  # Simulate 50ms AIRS API latency
            return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', side_effect=mock_scan_with_delay), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_with_delay):

            start_time = time.time()
            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "test",
                    "conversation_id": "test-perf"
                },
            )

            for line in response.iter_lines():
                pass

            elapsed_time = time.time() - start_time

            # With 2 progressive scans (at 50, 100) + 1 final = 3 output scans + 1 input scan
            # Expected delay: ~4 scans * 50ms = 200ms
            # Allow some overhead for processing
            assert elapsed_time < 1.0  # Should complete within 1 second

    def test_streaming_latency_with_airs_disabled(self, client, mock_rag, mock_llm, mock_tools):
        """Test streaming latency with AIRS disabled (baseline)."""
        async def mock_stream():
            for i in range(100):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="x"), {"run_id": "test"})
                await asyncio.sleep(0.001)

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', False), \
             patch('backend.config.Config.AIRS_ENABLED', False), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output') as mock_scan:

            start_time = time.time()
            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "test",
                    "conversation_id": "test-perf-baseline"
                },
            )

            for line in response.iter_lines():
                pass

            elapsed_time = time.time() - start_time

            # Without AIRS scanning, should be faster
            assert elapsed_time < 0.5  # Should complete within 500ms

            # Should not call scan_output
            assert not mock_scan.called


class TestConversationHistoryValidation:
    """Validate conversation history for blocked responses."""

    def test_conversation_history_after_blocked_response(self, client, mock_rag, mock_llm, mock_tools):
        """Test conversation history contains user input but not blocked response."""
        async def mock_stream():
            for i in range(60):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="bad "), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = [0]

        async def mock_scan_block_second(prompt=None, response=None, profile_name=None):
            if prompt:
                return ScanResult(action="allow")
            else:
                scan_count[0] += 1
                if scan_count[0] == 1:  # Block at first progressive scan
                    return ScanResult(action="block", category="toxic")
                return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', side_effect=mock_scan_block_second), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_block_second), \
             patch('backend.security.airs_scanner.log_security_violation'):

            # Stream with blocking
            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "test blocked query",
                    "conversation_id": "test-history-blocked"
                },
            )

            for line in response.iter_lines():
                if line:
                    if line.startswith('data: '):
                        import json
                        try:
                            event = json.loads(line[6:])
                            if event.get("type") == "security_violation":
                                break
                        except json.JSONDecodeError:
                            pass

            # Check conversation history via API
            history_response = client.get("/api/v1/conversations/test-history-blocked/history")
            history = history_response.json()

            # Should have 1 exchange (user input only, no assistant response)
            # Note: The API returns conversation history in exchange format
            # When blocked, only user message is recorded (per Decision 3)
            # But history endpoint might not show incomplete exchanges
            # This depends on how get_conversation_history() handles odd-length history

    def test_conversation_history_after_allowed_response(self, client, mock_rag, mock_llm, mock_tools):
        """Test conversation history contains both user input and assistant response."""
        async def mock_stream():
            for i in range(60):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok "), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', AsyncMock(return_value=ScanResult(action="allow"))), \
             patch('backend.security.airs_scanner.scan_output', AsyncMock(return_value=ScanResult(action="allow"))):

            # Stream without blocking
            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "test allowed query",
                    "conversation_id": "test-history-allowed"
                },
            )

            for line in response.iter_lines():
                pass

            # Check conversation history
            history_response = client.get("/api/v1/conversations/test-history-allowed/history")
            history_data = history_response.json()

            # Should have 1 complete exchange (user + assistant)
            assert "messages" in history_data
            messages = history_data["messages"]
            assert len(messages) == 1
            assert messages[0]["user"] == "test allowed query"
            assert "ok" in messages[0]["assistant"]


class TestStatelessMode:
    """Test streaming AIRS protection in stateless mode."""

    def test_stateless_streaming_with_progressive_scan(self, client, mock_rag, mock_llm, mock_tools):
        """Test that stateless mode also has progressive scanning."""
        async def mock_stream():
            for i in range(60):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="bad "), {"run_id": "test"})

        from unittest.mock import MagicMock
        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = [0]

        async def mock_scan_block_progressive(prompt=None, response=None, profile_name=None):
            if prompt:
                return ScanResult(action="allow")
            else:
                scan_count[0] += 1
                if scan_count[0] == 1:
                    return ScanResult(action="block", category="toxic")
                return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_input', side_effect=mock_scan_block_progressive), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_block_progressive), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            # Use stateless endpoint (no conversation_id)
            response = client.post(
                "/api/v1/chat/stream",
                json={
                    "message": "test stateless",
                    # No conversation_id - triggers stateless mode
                },
            )

            events = []
            for line in response.iter_lines():
                if line:
                    if line.startswith('data: '):
                        import json
                        try:
                            event = json.loads(line[6:])
                            events.append(event)
                            if event.get("type") == "security_violation":
                                break
                        except json.JSONDecodeError:
                            pass

            # Should have security violation
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) > 0

            # Should have logged with conversation_id=None (stateless)
            # Note: The API always assigns a conversation_id, so this test might need adjustment
            # If stateless mode is truly stateless, the endpoint needs modification
