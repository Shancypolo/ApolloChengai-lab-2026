"""Offline checks for transient API retry and per-attempt usage tracking."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from ai_summaries import MAX_API_ATTEMPTS, create_response, decode_response, SummaryError


USAGE = {
    "input_tokens": 10,
    "output_tokens": 2,
    "total_tokens": 12,
    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
    "output_tokens_details": {"reasoning_tokens": 1},
}


class FakeResponses:
    """Return or raise queued results while counting requests."""

    def __init__(self, results):
        """Keep the next fake outcomes in request order."""
        self.results = list(results)
        self.calls = 0

    def create(self, **_request_data):
        """Consume one queued result and count the API attempt."""
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class ApiRetryTests(unittest.TestCase):
    """Keep retry policy and usage accounting deterministic and offline."""

    def client(self, results):
        """Build a fake client for the selected response sequence."""
        endpoint = FakeResponses(results)
        return SimpleNamespace(responses=endpoint), endpoint

    def test_retries_connection_timeout_rate_limit_and_server_errors(self):
        """Each transient failure is recorded before a later success."""
        class RateLimitError(Exception):
            """Stand in for a transient provider rate limit."""
            pass

        response = SimpleNamespace(output_text='{"summary":"Done."}', usage=USAGE)
        client, endpoint = self.client([
            ConnectionError("offline"), TimeoutError("slow"), RateLimitError(), response,
        ])
        recorded = []

        with patch("ai_summaries.time.sleep") as sleep:
            result = create_response(client, recorded.append, model="fake")

        self.assertIs(result, response)
        self.assertEqual(endpoint.calls, 4)
        self.assertEqual(recorded, [None, None, None, {
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
            "cached_tokens": 0,
            "cache_write_tokens": 0,
            "cache_write_30m_tokens": 0,
            "cache_write_12h_tokens": 0,
            "reasoning_tokens": 1,
            "cached_detail_complete": True,
            "cache_write_detail_complete": True,
            "details_complete": True,
        }])
        self.assertEqual(sleep.call_count, 3)

    def test_retries_server_status_and_stops_after_max_attempts(self):
        """Count every failed server attempt, including the final one."""
        class ServerError(Exception):
            """Stand in for a transient provider server failure."""
            status_code = 500

        client, endpoint = self.client([ServerError("busy") for _ in range(MAX_API_ATTEMPTS)])
        recorded = []

        with patch("ai_summaries.time.sleep") as sleep:
            with self.assertRaises(ServerError):
                create_response(client, recorded.append, model="fake")

        self.assertEqual(endpoint.calls, MAX_API_ATTEMPTS)
        self.assertEqual(recorded, [None] * MAX_API_ATTEMPTS)
        self.assertEqual(sleep.call_count, MAX_API_ATTEMPTS - 1)

    def test_does_not_retry_auth_or_client_errors(self):
        """Invalid credentials and ordinary 4xx errors fail immediately."""
        class AuthenticationError(Exception):
            """Stand in for invalid API credentials."""
            status_code = 401

        class BadRequestError(Exception):
            """Stand in for an invalid provider request."""
            status_code = 400

        for error in (AuthenticationError("unauthorized"), BadRequestError("bad request")):
            with self.subTest(error=type(error).__name__):
                client, endpoint = self.client([error])
                recorded = []
                with patch("ai_summaries.time.sleep") as sleep:
                    with self.assertRaises(type(error)):
                        create_response(client, recorded.append, model="fake")
                self.assertEqual(endpoint.calls, 1)
                self.assertEqual(recorded, [None])
                sleep.assert_not_called()

    def test_malformed_response_is_not_retried(self):
        """A returned malformed body is parsed once and its usage is retained."""
        response = SimpleNamespace(output_text="not JSON", usage=USAGE)
        client, endpoint = self.client([response])
        recorded = []

        with patch("ai_summaries.time.sleep") as sleep:
            result = create_response(client, recorded.append, model="fake")
            with self.assertRaises(SummaryError):
                decode_response(result)

        self.assertEqual(endpoint.calls, 1)
        self.assertEqual(len(recorded), 1)
        self.assertIsNotNone(recorded[0])
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
