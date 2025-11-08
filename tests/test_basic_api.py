"""
Simple API test for Vito's Pizza Cafe.
Tests basic health check and chat functionality.

Usage:
    python tests/test_basic_api.py
    python tests/test_basic_api.py --url http://localhost:8000
    python tests/test_basic_api.py --url https://localhost:443
"""

import sys
import argparse
import uuid
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.api_client import VitosApiClient


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Simple API test for Vito's Pizza Cafe")
    parser.add_argument('--url', default='http://localhost:8000',
                        help='API base URL (default: http://localhost:8000)')
    return parser.parse_args()


def test_health_check(client):
    """Test that the API health endpoint is working."""
    print("\n=== Testing Health Check ===")

    result = client.health_check()

    if result:
        print("✓ Health check passed")
        return True
    else:
        print("✗ Health check failed - backend server may not be running")
        return False


def test_basic_chat(client, conversation_id):
    """Test basic chat functionality with specific test messages."""
    print("\n=== Testing Basic Chat Functionality ===")

    test_messages = [
        "What's on the menu?",
        "Do you deliver?",
        "Do you deliver to this address: 力宝广场, 上海市淮海中路222号"
    ]

    all_passed = True

    for i, message in enumerate(test_messages, 1):
        print(f"\n[{i}/{len(test_messages)}] Testing: '{message}'")

        try:
            response = client.chat(message, conversation_id)

            # Verify response is valid
            if response is None:
                print(f"✗ Response is None")
                all_passed = False
                continue

            if len(response.strip()) == 0:
                print(f"✗ Response is empty")
                all_passed = False
                continue

            print(f"✓ Got response ({len(response)} chars): \n{response}")

        except Exception as e:
            print(f"✗ Exception occurred: {e}")
            all_passed = False

    return all_passed


def cleanup_conversation(client, conversation_id):
    """Clean up test conversation."""
    print("\n=== Cleaning Up ===")

    try:
        if client.delete_conversation(conversation_id):
            print(f"✓ Cleaned up conversation: {conversation_id}")
            return True
        else:
            print(f"⚠ Failed to clean up conversation: {conversation_id}")
            return False
    except Exception as e:
        print(f"⚠ Error during cleanup: {e}")
        return False


def main():
    """Main test execution."""
    # Parse arguments
    args = parse_arguments()
    base_url = args.url

    print("=" * 60)
    print("VITO'S PIZZA CAFE - SIMPLE API TEST")
    print("=" * 60)
    print(f"Testing API at: {base_url}")

    # Generate unique conversation ID
    conversation_id = f"test_basic_{uuid.uuid4().hex[:8]}"

    # Initialize client
    client = VitosApiClient(base_url)

    tests_passed = 0
    tests_failed = 0

    try:
        # Test 1: Health Check
        print("\n[Test 1/2] Health Check")
        if test_health_check(client):
            tests_passed += 1
            print("✅ test_health_check - PASSED")
        else:
            tests_failed += 1
            print("❌ test_health_check - FAILED")
            print("\n" + "=" * 60)
            print("❌ TESTS FAILED: Backend server is not accessible")
            print(f"Please ensure the server is running at {base_url}")
            print("=" * 60)
            return 1

        # Test 2: Basic Chat
        print("\n[Test 2/2] Basic Chat")
        if test_basic_chat(client, conversation_id):
            tests_passed += 1
            print("✅ test_basic_chat - PASSED")
        else:
            tests_failed += 1
            print("❌ test_basic_chat - FAILED")

        # Cleanup
        cleanup_conversation(client, conversation_id)

        # Summary
        print("\n" + "=" * 60)
        print(f"TEST SUMMARY: {tests_passed}/{tests_passed + tests_failed} tests passed")
        print("=" * 60)

        if tests_failed == 0:
            print("✅ ALL TESTS PASSED")
            print("=" * 60)
            return 0
        else:
            print(f"❌ {tests_failed} test(s) failed")
            print("=" * 60)
            return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
