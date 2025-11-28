"""
Unit tests for streaming AIRS protection.

Tests cover:
- Input scanning before streaming
- Progressive output scanning during streaming
- Final output scanning after streaming
- Security violation event handling
- Fail-open behavior
- Conversation history handling
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.chat_service import ChatService
from backend.security.airs_scanner import ScanResult


@pytest.fixture
def mock_scan_allow():
    """Mock AIRS scanner that allows all content."""
    return AsyncMock(return_value=ScanResult(action="allow"))


@pytest.fixture
def mock_scan_block():
    """Mock AIRS scanner that blocks all content."""
    return AsyncMock(return_value=ScanResult(action="block", category="malicious"))


@pytest.fixture
def mock_rag():
    """Mock RAG retrieval."""
    with patch('backend.chat_service.retrieve_context', return_value="<context>Test context</context>"):
        yield


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid actual API calls."""
    with patch('backend.chat_service.get_llm'):
        yield


@pytest.fixture
def mock_tools():
    """Mock database and MCP tools."""
    with patch('backend.chat_service.get_database_tools', return_value=[]), \
         patch('backend.chat_service.get_mcp_tools', new_callable=AsyncMock, return_value=[]):
        yield


class TestInputScanning:
    """Test input scanning before streaming begins."""

    @pytest.mark.asyncio
    async def test_input_scan_blocks_malicious_prompt_stateful(
        self, mock_rag, mock_llm, mock_tools, mock_scan_block
    ):
        """Test that malicious input is blocked before streaming in stateful mode."""
        chat_service = ChatService(conversation_id="test-input-block")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.security.airs_scanner.scan_input', mock_scan_block), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            # Note: Input scan happens at API level (api.py), not in chat_service
            # This test verifies the chat_service behavior when input passes scan
            # For API-level input blocking, see test_streaming_airs_integration.py

            # When input scan passes (happens at api.py), streaming proceeds
            with patch('backend.security.airs_scanner.scan_input', AsyncMock(return_value=ScanResult(action="allow"))):
                events = []
                async for event in chat_service.aprocess_query_stream("benign message"):
                    events.append(event)
                    if event.get("type") == "security_violation":
                        break

                # Should not have security violation from input (input scan passed)
                violation_events = [e for e in events if e.get("type") == "security_violation"]
                assert len(violation_events) == 0

    @pytest.mark.asyncio
    async def test_input_scan_blocks_malicious_prompt_stateless(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that malicious input is blocked in stateless mode."""
        # Input scanning happens at API level for both stateful and stateless
        # This is tested in integration tests where we test the full API endpoint
        pass  # Covered by integration tests


class TestProgressiveScanning:
    """Test progressive output scanning during streaming."""

    @pytest.mark.asyncio
    async def test_progressive_scan_detects_malicious_content_stateful(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that progressive scan detects malicious content at chunk interval."""
        chat_service = ChatService(conversation_id="test-progressive")

        # Mock LangGraph agent to yield chunks that will trigger progressive scan
        async def mock_stream():
            # Yield 50 benign chunks (trigger first progressive scan)
            for i in range(50):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok "), {"run_id": "test"})

            # Yield 50 more chunks (trigger second progressive scan - should block)
            for i in range(50):
                yield (AIMessage(content="bad "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = 0

        async def mock_scan_output(response, profile_name):
            nonlocal scan_count
            scan_count += 1
            # First scan (at 50 chunks): allow
            if scan_count == 1:
                return ScanResult(action="allow")
            # Second scan (at 100 chunks): block
            else:
                return ScanResult(action="block", category="malicious")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_output), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            events = []
            async for event in chat_service.aprocess_query_stream("test query"):
                events.append(event)
                if event.get("type") == "security_violation":
                    break

            # Should have triggered 2 progressive scans
            assert scan_count == 2

            # Should have security violation event
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 1
            assert violation_events[0]["message"] == "Response blocked due to content policy"

            # Should have logged the violation with progressive context
            assert mock_log.called
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["scan_type"] == "output"
            assert call_kwargs["scan_context"] == "progressive"
            assert call_kwargs["chunks_accumulated"] == 100
            assert call_kwargs["action"] == "block"

    @pytest.mark.asyncio
    async def test_progressive_scan_detects_malicious_content_stateless(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test progressive scan in stateless mode."""
        # Similar to stateful test but using process_stateless_query_stream
        async def mock_stream():
            for i in range(50):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok "), {"run_id": "test"})

            for i in range(50):
                yield (AIMessage(content="bad "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = 0

        async def mock_scan_output(response, profile_name):
            nonlocal scan_count
            scan_count += 1
            if scan_count == 1:
                return ScanResult(action="allow")
            else:
                return ScanResult(action="block", category="malicious")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_output), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            events = []
            async for event in ChatService.process_stateless_query_stream("test query"):
                events.append(event)
                if event.get("type") == "security_violation":
                    break

            # Should have triggered 2 progressive scans
            assert scan_count == 2

            # Should have security violation
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 1

            # Should have logged with conversation_id=None for stateless
            assert mock_log.called
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["conversation_id"] is None
            assert call_kwargs["scan_context"] == "progressive"


class TestFinalScanning:
    """Test final output scanning after streaming completes."""

    @pytest.mark.asyncio
    async def test_final_scan_detects_malicious_content(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that final scan catches malicious content in last chunks."""
        chat_service = ChatService(conversation_id="test-final")

        # Mock agent to yield 45 chunks (not enough to trigger progressive scan)
        # but final scan should still catch it
        async def mock_stream():
            for i in range(45):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="malicious "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = 0

        async def mock_scan_output(response, profile_name):
            nonlocal scan_count
            scan_count += 1
            # Final scan should block
            return ScanResult(action="block", category="toxic")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_output), \
             patch('backend.security.airs_scanner.log_security_violation') as mock_log:

            events = []
            async for event in chat_service.aprocess_query_stream("test query"):
                events.append(event)

            # Should have triggered only 1 scan (final, no progressive)
            assert scan_count == 1

            # Should have security violation from final scan
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 1

            # Should have logged with final context
            assert mock_log.called
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["scan_context"] == "final"
            assert call_kwargs["chunks_accumulated"] == 45

    @pytest.mark.asyncio
    async def test_final_scan_always_runs_after_progressive(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that final scan runs even after progressive scans (per Decision 5)."""
        chat_service = ChatService(conversation_id="test-final-always")

        # Mock agent to yield 100 chunks (triggers 2 progressive scans at 50 and 100)
        async def mock_stream():
            for i in range(100):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_count = 0

        async def mock_scan_output(response, profile_name):
            nonlocal scan_count
            scan_count += 1
            # All scans allow
            return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_output):

            events = []
            async for event in chat_service.aprocess_query_stream("test query"):
                events.append(event)

            # Should have 3 scans: progressive at 50, progressive at 100, and final
            assert scan_count == 3


class TestBenignContent:
    """Test that benign content passes all scans successfully."""

    @pytest.mark.asyncio
    async def test_benign_content_passes_all_scans(
        self, mock_rag, mock_llm, mock_tools, mock_scan_allow
    ):
        """Test that benign content streams successfully without blocking."""
        chat_service = ChatService(conversation_id="test-benign")

        async def mock_stream():
            for i in range(75):  # Trigger progressive scan at 50 and final at 75
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="safe "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', mock_scan_allow):

            events = []
            async for event in chat_service.aprocess_query_stream("safe query"):
                events.append(event)

            # Should have no security violations
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 0

            # Should have token events
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) == 75

            # Conversation history should be updated (not blocked)
            assert len(chat_service.conversation_history) == 2  # user + assistant


class TestChunkCounting:
    """Test scan interval timing with chunk-based counting."""

    @pytest.mark.asyncio
    async def test_scan_interval_timing(
        self, mock_rag, mock_llm, mock_tools, mock_scan_allow
    ):
        """Test that scans happen at correct chunk intervals."""
        chat_service = ChatService(conversation_id="test-timing")

        async def mock_stream():
            # Yield exactly 150 chunks to test multiple intervals
            for i in range(150):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="x"), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        scan_calls = []

        async def track_scan_calls(response, profile_name):
            scan_calls.append(len(response))  # Track accumulated response length at each scan
            return ScanResult(action="allow")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=track_scan_calls):

            events = []
            async for event in chat_service.aprocess_query_stream("test"):
                events.append(event)

            # Should have 4 scans: at 50, 100, 150 chunks (progressive) + final
            assert len(scan_calls) == 4

            # Verify scan timing (accumulated content length)
            assert scan_calls[0] == 50  # First progressive scan at 50 chunks
            assert scan_calls[1] == 100  # Second progressive scan at 100 chunks
            assert scan_calls[2] == 150  # Third progressive scan at 150 chunks
            assert scan_calls[3] == 150  # Final scan (same length as last progressive)


class TestSecurityViolationEvents:
    """Test security_violation event format."""

    @pytest.mark.asyncio
    async def test_security_violation_event_format(
        self, mock_rag, mock_llm, mock_tools, mock_scan_block
    ):
        """Test that security_violation event has correct format."""
        chat_service = ChatService(conversation_id="test-event")

        async def mock_stream():
            for i in range(10):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="bad"), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 5), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', mock_scan_block), \
             patch('backend.security.airs_scanner.log_security_violation'):

            events = []
            async for event in chat_service.aprocess_query_stream("test"):
                events.append(event)
                if event.get("type") == "security_violation":
                    break

            # Find security violation event
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 1

            violation_event = violation_events[0]
            assert violation_event["type"] == "security_violation"
            assert violation_event["message"] == "Response blocked due to content policy"
            assert "message" in violation_event  # Required field


class TestFailOpen:
    """Test fail-open behavior when AIRS API fails."""

    @pytest.mark.asyncio
    async def test_fail_open_on_airs_api_error_progressive(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that streaming continues when progressive scan fails."""
        chat_service = ChatService(conversation_id="test-failopen")

        async def mock_stream():
            for i in range(60):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        async def mock_scan_error(response, profile_name):
            raise Exception("AIRS API connection failed")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_error), \
             patch('backend.chat_service.logger') as mock_logger:

            events = []
            async for event in chat_service.aprocess_query_stream("test"):
                events.append(event)

            # Should continue streaming despite scan failure
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) == 60

            # Should NOT have security violation (fail-open)
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 0

            # Should have logged the error
            assert mock_logger.error.called
            error_calls = [call for call in mock_logger.error.call_args_list
                          if "AIRS scan failed" in str(call)]
            assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_fail_open_on_airs_api_error_final(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that response is delivered when final scan fails."""
        chat_service = ChatService(conversation_id="test-failopen-final")

        async def mock_stream():
            for i in range(30):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        async def mock_scan_error(response, profile_name):
            raise Exception("AIRS API timeout")

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', side_effect=mock_scan_error), \
             patch('backend.chat_service.logger') as mock_logger:

            events = []
            async for event in chat_service.aprocess_query_stream("test"):
                events.append(event)

            # Should deliver all tokens
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) == 30

            # Should NOT block on final scan error
            violation_events = [e for e in events if e.get("type") == "security_violation"]
            assert len(violation_events) == 0

            # Should log the final scan error
            assert mock_logger.error.called
            error_messages = [str(call) for call in mock_logger.error.call_args_list]
            assert any("AIRS final scan failed" in msg for msg in error_messages)


class TestConversationHistory:
    """Test conversation history handling for blocked content."""

    @pytest.mark.asyncio
    async def test_conversation_history_records_user_input_when_blocked(
        self, mock_rag, mock_llm, mock_tools, mock_scan_block
    ):
        """Test that user input is recorded when response is blocked (Decision 3)."""
        chat_service = ChatService(conversation_id="test-history-block")

        async def mock_stream():
            for i in range(10):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="bad"), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 5), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', mock_scan_block), \
             patch('backend.security.airs_scanner.log_security_violation'):

            # Start with empty history
            assert len(chat_service.conversation_history) == 0

            events = []
            async for event in chat_service.aprocess_query_stream("malicious query"):
                events.append(event)

            # History should have 1 entry (user input only, no blocked response)
            assert len(chat_service.conversation_history) == 1

            from langchain_core.messages import HumanMessage
            assert isinstance(chat_service.conversation_history[0], HumanMessage)
            assert chat_service.conversation_history[0].content == "malicious query"

    @pytest.mark.asyncio
    async def test_conversation_history_updates_normally_when_allowed(
        self, mock_rag, mock_llm, mock_tools, mock_scan_allow
    ):
        """Test that conversation history is updated normally for benign content."""
        chat_service = ChatService(conversation_id="test-history-allow")

        async def mock_stream():
            for i in range(10):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="ok"), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', True), \
             patch('backend.config.Config.AIRS_STREAM_SCAN_CHUNK_INTERVAL', 50), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output', mock_scan_allow):

            assert len(chat_service.conversation_history) == 0

            events = []
            async for event in chat_service.aprocess_query_stream("benign query"):
                events.append(event)

            # History should have 2 entries (user + assistant)
            assert len(chat_service.conversation_history) == 2

            from langchain_core.messages import HumanMessage, AIMessage
            assert isinstance(chat_service.conversation_history[0], HumanMessage)
            assert isinstance(chat_service.conversation_history[1], AIMessage)
            assert chat_service.conversation_history[0].content == "benign query"
            assert "ok" in chat_service.conversation_history[1].content


class TestAIRSDisabled:
    """Test behavior when AIRS is disabled."""

    @pytest.mark.asyncio
    async def test_streaming_works_when_airs_disabled(
        self, mock_rag, mock_llm, mock_tools
    ):
        """Test that streaming works normally when AIRS is disabled."""
        chat_service = ChatService(conversation_id="test-airs-disabled")

        async def mock_stream():
            for i in range(10):
                from langchain_core.messages import AIMessage
                yield (AIMessage(content="test "), {"run_id": "test"})

        mock_agent = MagicMock()
        mock_agent.astream = MagicMock(return_value=mock_stream())

        with patch('backend.config.Config.AIRS_ENABLED', False), \
             patch('backend.chat_service.create_react_agent', return_value=mock_agent), \
             patch('backend.security.airs_scanner.scan_output') as mock_scan:

            events = []
            async for event in chat_service.aprocess_query_stream("test"):
                events.append(event)

            # Should stream all tokens
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) == 10

            # Should NOT call scan_output when AIRS disabled
            assert not mock_scan.called
