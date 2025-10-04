"""
Integration tests for LiteLLM proxy server health checks and model availability.

These tests make actual HTTP requests to the LiteLLM proxy server running on localhost:4000.
Requires the LiteLLM server to be running before executing tests.

Usage:
    # Start LiteLLM server first:
    docker-compose up -d

    # Then run these tests:
    python tests/test_litellm_health.py
"""

import sys
import requests
import openai
from typing import List

# Constants
LITELLM_BASE_URL = "http://localhost:4000"
LITELLM_API_KEY = "sk-1234"


class TestLiteLLMHealth:
    """Integration tests for LiteLLM proxy server health and model availability."""

    def __init__(self):
        """Initialize test client."""
        self.base_url = LITELLM_BASE_URL
        self.api_key = LITELLM_API_KEY
        self.headers = {
            "accept": "application/json",
            "x-litellm-api-key": self.api_key
        }
        self.openai_client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def get_models(self) -> List[str]:
        """
        Retrieve list of available models from LiteLLM.

        Returns:
            List of model IDs (e.g., ['gpt-5-nano', 'qwen-max', ...])
        """
        url = f"{self.base_url}/models"
        params = {
            "return_wildcard_routes": False,
            "include_model_access_groups": False,
            "only_model_access_groups": False,
            "include_metadata": False
        }

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()

        data = response.json()
        model_ids = [model["id"] for model in data.get("data", [])]

        print(f"Found {len(model_ids)} models: {', '.join(model_ids)}")
        return model_ids

    def test_liveness_check(self):
        """Test liveness endpoint returns 'I'm alive!'"""
        print("\n=== Testing Liveness Check ===")

        url = f"{self.base_url}/health/liveness"
        response = requests.get(url, headers={"accept": "application/json"})

        assert response.status_code == 200, f"Expected status 200, got {response.status_code}"

        # Response should be a simple string
        response_text = response.text.strip('"')
        assert response_text == "I'm alive!", f"Expected 'I'm alive!', got '{response_text}'"

        print(f"✓ Liveness check passed: {response_text}")

    def test_readiness_check(self):
        """Test readiness endpoint returns proper status and verifies PanwPrismaAirsHandler."""
        print("\n=== Testing Readiness Check ===")

        url = f"{self.base_url}/health/readiness"
        response = requests.get(url, headers=self.headers)

        assert response.status_code == 200, f"Expected status 200, got {response.status_code}"

        data = response.json()

        # Verify status is connected
        assert data.get("status") == "connected", f"Expected status 'connected', got '{data.get('status')}'"
        print(f"✓ Status: {data.get('status')}")

        # Verify db is connected
        assert data.get("db") == "connected", f"Expected db 'connected', got '{data.get('db')}'"
        print(f"✓ Database: {data.get('db')}")

        # Verify success_callbacks contains at least 2 instances of PanwPrismaAirsHandler
        success_callbacks = data.get("success_callbacks", [])
        panw_handler_count = success_callbacks.count("PanwPrismaAirsHandler")

        assert panw_handler_count >= 2, \
            f"Expected at least 2 PanwPrismaAirsHandler instances, found {panw_handler_count}"
        print(f"✓ Found {panw_handler_count} PanwPrismaAirsHandler instances in success_callbacks")

        # Print additional info
        if "litellm_version" in data:
            print(f"✓ LiteLLM version: {data['litellm_version']}")

    def test_model_health_checks(self):
        """Test health check for each configured model."""
        print("\n=== Testing Model Health Checks ===")

        # Get dynamic list of models
        model_ids = self.get_models()
        assert len(model_ids) > 0, "No models found in LiteLLM configuration"

        failed_models = []

        for model_id in model_ids:
            print(f"\nChecking health for model: {model_id}")

            url = f"{self.base_url}/health"
            params = {"model": model_id}

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()

                healthy_count = data.get("healthy_count", 0)
                unhealthy_count = data.get("unhealthy_count", 0)

                # Verify healthy_count >= 1
                if healthy_count < 1:
                    failed_models.append(f"{model_id}: healthy_count={healthy_count}")
                    print(f"  ✗ healthy_count: {healthy_count} (expected >= 1)")
                else:
                    print(f"  ✓ healthy_count: {healthy_count}")

                # Verify unhealthy_count == 0
                if unhealthy_count != 0:
                    failed_models.append(f"{model_id}: unhealthy_count={unhealthy_count}")
                    print(f"  ✗ unhealthy_count: {unhealthy_count} (expected 0)")
                else:
                    print(f"  ✓ unhealthy_count: {unhealthy_count}")

            except Exception as e:
                failed_models.append(f"{model_id}: {str(e)}")
                print(f"  ✗ Error checking health: {e}")

        if failed_models:
            raise AssertionError(f"Health checks failed for models:\n" + "\n".join(failed_models))

        print(f"\n✓ All {len(model_ids)} models passed health checks")

    def test_real_llm_calls(self):
        """Test making real LLM call to gpt-5-nano model if available."""
        print("\n=== Testing Real LLM Calls ===")

        # Get dynamic list of models
        model_ids = self.get_models()
        assert len(model_ids) > 0, "No models found in LiteLLM configuration"

        # Check if gpt-5-nano is in the model list
        test_model = "gpt-5-nano"
        if test_model not in model_ids:
            print(f"⚠ Model '{test_model}' not found in model list. Skipping real LLM call test.")
            print(f"  Available models: {', '.join(model_ids)}")
            return

        test_message = "帮我写一首五言绝句的唐诗"

        print(f"\nTesting real call to model: {test_model}")

        try:
            response = self.openai_client.chat.completions.create(
                model=test_model,
                messages=[
                    {
                        "role": "user",
                        "content": test_message
                    }
                ]
            )

            # Verify response structure
            assert response.id is not None, "Response missing id"
            assert len(response.choices) > 0, "Response has no choices"
            assert response.choices[0].message is not None, "Response missing message"
            assert response.choices[0].message.content is not None, "Response missing content"

            content = response.choices[0].message.content
            assert len(content) > 0, "Response content is empty"

            print(f"  ✓ Model: {response.model}")
            print(f"  ✓ Response length: {len(content)} chars")
            print(f"  ✓ Completion tokens: {response.usage.completion_tokens if response.usage else 'N/A'}")
            print(f"  ✓ Content preview: {content[:80]}...")
            print(f"\n✓ Real LLM call to {test_model} completed successfully")

        except Exception as e:
            raise AssertionError(f"Real LLM call failed for {test_model}: {str(e)}")

    def run_all_tests(self):
        """Run all integration tests."""
        print("=" * 60)
        print("LITELLM HEALTH CHECK INTEGRATION TESTS")
        print("=" * 60)

        # Verify LiteLLM server is running
        try:
            response = requests.get(f"{self.base_url}/health/liveness", timeout=5)
            if response.status_code != 200:
                raise Exception("LiteLLM server not responding correctly")
            print("✓ LiteLLM server is running and accessible")
        except Exception as e:
            print(f"❌ LiteLLM server is not running on {self.base_url}")
            print(f"   Error: {e}")
            print(f"   Please start it first with: litellm --config litellm/litellm_config.yaml --port 4000")
            return False

        # Run all test methods
        test_methods = [
            self.test_liveness_check,
            self.test_readiness_check,
            self.test_model_health_checks,
            self.test_real_llm_calls,
        ]

        passed_tests = 0
        total_tests = len(test_methods)

        for test_method in test_methods:
            try:
                test_method()
                passed_tests += 1
                print(f"\n✅ {test_method.__name__} - PASSED")
            except Exception as e:
                print(f"\n❌ {test_method.__name__} - FAILED: {e}")

        print("\n" + "=" * 60)
        print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
        print("=" * 60)

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! LiteLLM is working correctly.")
            return True
        else:
            print(f"⚠️ {total_tests - passed_tests} tests failed. Please check the output above.")
            return False


if __name__ == "__main__":
    """Run integration tests when script is executed directly."""
    test_runner = TestLiteLLMHealth()
    success = test_runner.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
