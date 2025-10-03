"""
Real integration tests for Vito's Pizza Cafe API endpoints.

These tests make actual HTTP requests to the live backend server running on localhost:8000.
Requires the backend server to be running before executing tests.

Usage:
    # Start backend server first:
    python -m backend.api

    # Then run these tests:
    python tests/test_api_integration.py
"""

import sys
import time
import uuid
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api_client import VitosApiClient


class TestVitosAPIIntegration:
    """Integration tests for Vito's Pizza Cafe API using real HTTP requests."""

    def __init__(self):
        """Initialize test client and generate unique conversation ID."""
        self.client = VitosApiClient("http://localhost:8000")
        self.test_conversation_id = f"test_{uuid.uuid4().hex[:8]}"
        self.conversation_ids_to_cleanup = []

    def setUp(self):
        """Set up test environment."""
        print(f"Setting up integration tests with conversation ID: {self.test_conversation_id}")

        # Verify backend is running
        if not self.client.health_check():
            raise Exception("Backend server is not running on localhost:8000. Please start it first with: python -m backend.api")

        print("✓ Backend server is running and healthy")

    def tearDown(self):
        """Clean up test conversations."""
        print("\nCleaning up test conversations...")
        for conv_id in self.conversation_ids_to_cleanup:
            try:
                self.client.delete_conversation(conv_id)
                print(f"✓ Cleaned up conversation: {conv_id}")
            except Exception as e:
                print(f"⚠ Failed to clean up conversation {conv_id}: {e}")

        self.client.close()
        print("✓ Test cleanup completed")

    def test_health_check(self):
        """Test health endpoint returns success."""
        print("\n=== Testing Health Check ===")

        result = self.client.health_check()
        assert result is True, "Health check should return True"
        print("✓ Health check passed")

    def test_basic_chat_functionality(self):
        """Test basic chat with realistic pizza cafe questions."""
        print("\n=== Testing Basic Chat Functionality ===")

        test_messages = [
            "What's on the menu?",
            "Do you deliver?",
            "Do you deliver to this address: 力宝广场, 上海市淮海中路222号",
            "What are your hours?",
            "Tell me about your pizza sizes"
        ]

        for i, message in enumerate(test_messages, 1):
            print(f"\n[{i}/{len(test_messages)}] Testing message: '{message}'")

            response = self.client.chat(message, self.test_conversation_id)

            # Verify we got a meaningful response
            assert response is not None, f"Response should not be None for message: {message}"
            assert len(response.strip()) > 0, f"Response should not be empty for message: {message}"
            assert not response.startswith("Sorry, I encountered an error"), f"Response indicates an error: {response}"

            print(f"✓ Got response ({len(response)} chars): {response[:100]}...")

            # Brief pause between requests to be respectful to the server
            time.sleep(0.5)

        # Track this conversation for cleanup
        self.conversation_ids_to_cleanup.append(self.test_conversation_id)
        print(f"✓ All {len(test_messages)} chat messages processed successfully")

    def test_conversation_continuity(self):
        """Test that conversation maintains context across multiple messages."""
        print("\n=== Testing Conversation Continuity ===")

        conv_id = f"continuity_test_{uuid.uuid4().hex[:8]}"
        self.conversation_ids_to_cleanup.append(conv_id)

        # First message - establish context
        response1 = self.client.chat("I'd like to order a pizza", conv_id)
        assert response1 and len(response1) > 0, "First response should not be empty"
        print(f"✓ First message response: {response1[:100]}...")

        # Second message - should reference previous context
        response2 = self.client.chat("What sizes do you have?", conv_id)
        assert response2 and len(response2) > 0, "Second response should not be empty"
        print(f"✓ Second message response: {response2[:100]}...")

        # Third message - continue the conversation
        response3 = self.client.chat("I'll take a large one", conv_id)
        assert response3 and len(response3) > 0, "Third response should not be empty"
        print(f"✓ Third message response: {response3[:100]}...")

        print("✓ Conversation continuity test passed")

    def test_conversation_history_retrieval(self):
        """Test retrieving conversation history."""
        print("\n=== Testing Conversation History Retrieval ===")

        conv_id = f"history_test_{uuid.uuid4().hex[:8]}"
        self.conversation_ids_to_cleanup.append(conv_id)

        # Send a few messages to build history
        messages = ["Hello", "What's your best pizza?", "How much does it cost?"]

        for msg in messages:
            response = self.client.chat(msg, conv_id)
            assert response and len(response) > 0, f"Response should not be empty for: {msg}"
            time.sleep(0.3)

        # Retrieve conversation history
        history = self.client.get_conversation_history(conv_id)

        assert history is not None, "History should not be None"
        assert len(history) >= len(messages), f"History should contain at least {len(messages)} messages, got {len(history)}"

        print(f"✓ Retrieved conversation history with {len(history)} messages")

        # Verify history contains our messages
        history_text = str(history).lower()
        assert "hello" in history_text, "History should contain our first message"
        print("✓ History contains expected content")

    def test_conversation_management(self):
        """Test conversation listing, clearing, and deletion."""
        print("\n=== Testing Conversation Management ===")

        conv_id = f"mgmt_test_{uuid.uuid4().hex[:8]}"

        # Create a conversation by sending a message
        response = self.client.chat("Test message for management", conv_id)
        assert response and len(response) > 0, "Initial message should get response"

        # List conversations - should include our test conversation
        conversations = self.client.get_conversations()
        assert conversations is not None, "Conversations list should not be None"
        print(f"✓ Retrieved {len(conversations)} active conversations")

        # Clear conversation history
        clear_result = self.client.clear_conversation_history(conv_id)
        assert clear_result is True, "Clear history should succeed"
        print("✓ Conversation history cleared successfully")

        # Verify history is empty after clearing
        history_after_clear = self.client.get_conversation_history(conv_id)
        assert len(history_after_clear) == 0, "History should be empty after clearing"
        print("✓ Verified history is empty after clearing")

        # Delete the conversation
        delete_result = self.client.delete_conversation(conv_id)
        assert delete_result is True, "Delete conversation should succeed"
        print("✓ Conversation deleted successfully")

    def test_multiple_conversations(self):
        """Test handling multiple separate conversations."""
        print("\n=== Testing Multiple Conversations ===")

        conv_ids = [f"multi_test_{i}_{uuid.uuid4().hex[:6]}" for i in range(3)]
        self.conversation_ids_to_cleanup.extend(conv_ids)

        # Send different messages to different conversations
        conversations_data = [
            (conv_ids[0], "I want to order pizza"),
            (conv_ids[1], "What are your hours?"),
            (conv_ids[2], "Do you have vegetarian options?")
        ]

        responses = []
        for conv_id, message in conversations_data:
            response = self.client.chat(message, conv_id)
            assert response and len(response) > 0, f"Response should not be empty for conversation {conv_id}"
            responses.append(response)
            print(f"✓ Conversation {conv_id}: {response[:50]}...")
            time.sleep(0.3)

        # Verify each conversation maintains separate context
        for conv_id, _ in conversations_data:
            history = self.client.get_conversation_history(conv_id)
            assert len(history) >= 1, f"Conversation {conv_id} should have at least 1 message"

        print(f"✓ Successfully managed {len(conv_ids)} separate conversations")

    def test_error_scenarios(self):
        """Test handling of various error scenarios."""
        print("\n=== Testing Error Scenarios ===")

        # Test with very long message
        long_message = "A" * 5000  # 5KB message
        response = self.client.chat(long_message, f"long_msg_test_{uuid.uuid4().hex[:8]}")
        # Should handle gracefully - either process it or return appropriate error
        assert response is not None, "Should handle long messages gracefully"
        print("✓ Long message handled appropriately")

        # Test with empty message
        response = self.client.chat("", f"empty_msg_test_{uuid.uuid4().hex[:8]}")
        # Should handle gracefully
        assert response is not None, "Should handle empty messages gracefully"
        print("✓ Empty message handled appropriately")

        # Test getting history for non-existent conversation
        history = self.client.get_conversation_history("nonexistent_conversation")
        # Should return empty list or handle gracefully
        assert history is not None, "Should handle non-existent conversation gracefully"
        print("✓ Non-existent conversation handled appropriately")

    def run_all_tests(self):
        """Run all integration tests."""
        print("=" * 60)
        print("VITO'S PIZZA CAFE API INTEGRATION TESTS")
        print("=" * 60)

        try:
            self.setUp()

            # Run all test methods
            test_methods = [
                self.test_health_check,
                self.test_basic_chat_functionality,
                self.test_conversation_continuity,
                self.test_conversation_history_retrieval,
                self.test_conversation_management,
                self.test_multiple_conversations,
                # self.test_error_scenarios
            ]

            passed_tests = 0
            total_tests = len(test_methods)

            for test_method in test_methods:
                try:
                    test_method()
                    passed_tests += 1
                    print(f"✅ {test_method.__name__} - PASSED")
                except Exception as e:
                    print(f"❌ {test_method.__name__} - FAILED: {e}")

            print("\n" + "=" * 60)
            print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
            print("=" * 60)

            if passed_tests == total_tests:
                print("🎉 ALL TESTS PASSED! The API is working correctly.")
                return True
            else:
                print(f"⚠️ {total_tests - passed_tests} tests failed. Please check the output above.")
                return False

        except Exception as e:
            print(f"❌ Test setup failed: {e}")
            return False

        finally:
            self.tearDown()


if __name__ == "__main__":
    """Run integration tests when script is executed directly."""
    test_runner = TestVitosAPIIntegration()
    success = test_runner.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)