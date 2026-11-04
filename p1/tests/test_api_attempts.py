"""Offline checks that each AI action sends one request and records usage once."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from ai_summaries import create_response, decode_response, SummaryError


USAGE = {
    "input_tokens": 10,
    "output_tokens": 2,
    "total_tokens": 12,
    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
    "output_tokens_details": {"reasoning_tokens": 1},
}


class FakeResponses:
    """Return one configured result while counting API requests."""

    def __init__(self, result):
        """Store the result and initialize the request count."""
        self.result = result
        self.calls = 0

    def create(self, **_request_data):
        """Count one request, then return or raise its configured result."""
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class ApiAttemptTests(unittest.TestCase):
    """Keep one-request and usage behavior deterministic and offline."""

    def client(self, result):
        """Build a fake API client and return it with its request counter."""
        endpoint = FakeResponses(result)
        return SimpleNamespace(responses=endpoint), endpoint

    def test_success_uses_one_request_and_records_usage_once(self):
        """A successful response yields one request and one usage record."""
        response = SimpleNamespace(output_text='{"summary":"Done."}', usage=USAGE)
        client, endpoint = self.client(response)
        recorded = []

        result = create_response(client, recorded.append, model="fake")

        self.assertIs(result, response)
        self.assertEqual(endpoint.calls, 1)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["input_tokens"], 10)
        self.assertEqual(recorded[0]["output_tokens"], 2)

    def test_connection_rate_limit_server_and_auth_fail_once(self):
        """Transient and authentication failures each log and record once."""
        class RateLimitError(Exception):
            """Represent a provider rate limit."""

        class ServerError(Exception):
            """Represent a provider server failure."""

            status_code = 503

        class AuthenticationError(Exception):
            """Represent invalid provider credentials."""

            status_code = 401

        errors = [
            ConnectionError("private connection detail"),
            RateLimitError("private quota detail"),
            ServerError("private server detail"),
            AuthenticationError("private credential detail"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                client, endpoint = self.client(error)
                recorded = []
                with self.assertLogs("pageone", level="ERROR") as logs:
                    with self.assertRaises(type(error)):
                        create_response(client, recorded.append, model="fake")

                self.assertEqual(endpoint.calls, 1)
                self.assertEqual(recorded, [None])
                self.assertEqual(len(logs.records), 1)
                self.assertIn(type(error).__name__, logs.output[0])
                self.assertNotIn(str(error), logs.output[0])

    def test_malformed_response_is_not_retried(self):
        """Malformed model output fails after its single successful request."""
        response = SimpleNamespace(output_text="not JSON", usage=USAGE)
        client, endpoint = self.client(response)
        recorded = []

        result = create_response(client, recorded.append, model="fake")
        with self.assertRaises(SummaryError):
            decode_response(result)

        self.assertEqual(endpoint.calls, 1)
        self.assertEqual(len(recorded), 1)
        self.assertIsNotNone(recorded[0])


if __name__ == "__main__":
    unittest.main()
