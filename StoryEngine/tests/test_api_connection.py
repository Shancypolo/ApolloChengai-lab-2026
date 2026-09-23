"""Unit tests for the standalone OpenAI API connectivity command."""

from __future__ import annotations

import contextlib
import io
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai import APIConnectionError

import testAPI
from story_memory import ConfigurationError


# Verify success, missing setup, incompatible SDK, and sanitized API failures.
class ApiConnectionTests(unittest.TestCase):
    # Capture CLI output while keeping terminal streams isolated per test.
    def setUp(self) -> None:
        self.output = io.StringIO()
        self.errors = io.StringIO()

    # A valid response reports success and request ID without printing response text.
    def test_successful_response(self) -> None:
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            id="resp_connection_test",
            _request_id="req_connection_test",
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.object(
            testAPI, "verify_tls_imports", return_value=("cacert.pem", None)
        ) as tls_verification, patch.object(testAPI, "validate_openai_sdk_version", return_value="2.54.0"
        ), patch.object(testAPI, "OpenAI", return_value=client) as openai_constructor, contextlib.redirect_stdout(
            self.output
        ), contextlib.redirect_stderr(self.errors):
            status = testAPI.check_api_connection()

        self.assertEqual(status, 0)
        self.assertIn("connection succeeded", self.output.getvalue())
        self.assertIn("certifi bundle found", self.output.getvalue())
        self.assertIn("httpx2 not installed (not required", self.output.getvalue())
        self.assertIn("req_connection_test", self.output.getvalue())
        self.assertNotIn("test-key", self.output.getvalue())
        self.assertEqual(self.errors.getvalue(), "")
        call = client.responses.create.call_args.kwargs
        self.assertEqual(call["model"], "gpt-5.6-luna")
        self.assertFalse(call["store"])
        self.assertNotIn("tools", call)
        openai_constructor.assert_called_once()
        tls_verification.assert_called_once()

    # Missing credentials fail before constructing the network client.
    def test_missing_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(testAPI, "OpenAI") as client, contextlib.redirect_stderr(
            self.errors
        ):
            status = testAPI.check_api_connection()

        self.assertEqual(status, 2)
        self.assertIn("OPENAI_API_KEY is not set", self.errors.getvalue())
        client.assert_not_called()

    # Unsupported SDK setup fails before any network request.
    def test_unsupported_sdk_version(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.object(
            testAPI,
            "validate_openai_sdk_version",
            side_effect=ConfigurationError("OpenAI SDK 3.11.0 is unsupported."),
        ), patch.object(testAPI, "verify_tls_imports", return_value=("cacert.pem", "2.12.0")), patch.object(
            testAPI, "OpenAI"
        ) as client, contextlib.redirect_stderr(self.errors):
            status = testAPI.check_api_connection()

        self.assertEqual(status, 2)
        self.assertIn("SDK 3.11.0 is unsupported", self.errors.getvalue())
        client.assert_not_called()

    # Network errors show a concise diagnosis and never expose exception payloads.
    def test_connection_error_is_sanitized(self) -> None:
        client = Mock()
        client.responses.create.side_effect = APIConnectionError(
            message="Connection error containing sk-secret.",
            request=None,
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.object(
            testAPI, "validate_openai_sdk_version", return_value="2.54.0"
        ), patch.object(testAPI, "verify_tls_imports", return_value=("cacert.pem", None)), patch.object(
            testAPI, "OpenAI", return_value=client
        ), contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.errors):
            status = testAPI.check_api_connection()

        self.assertEqual(status, 1)
        self.assertIn("network, proxy, TLS, or firewall", self.errors.getvalue())
        self.assertNotIn("sk-secret", self.errors.getvalue())
        self.assertNotIn("test-key", self.errors.getvalue())

    # Standard help exits without requiring a key or making a request.
    def test_help(self) -> None:
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(self.output):
            with self.assertRaises(SystemExit) as raised:
                testAPI.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("OpenAI Responses API", self.output.getvalue())


# Allow this file to run as a focused test module.
if __name__ == "__main__":
    unittest.main()
