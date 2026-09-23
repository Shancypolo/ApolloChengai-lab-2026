"""Check that StoryEngine can reach the OpenAI Responses API."""

from __future__ import annotations

import argparse
import os
import sys

from openai import APIConnectionError, APIStatusError, OpenAI

from story_memory import (
    API_MAX_RETRIES,
    API_TIMEOUT_SECONDS,
    MODEL,
    REASONING_EFFORT,
    VERBOSITY,
    ConfigurationError,
    validate_openai_sdk_version,
    verify_tls_imports,
)


# Keep this diagnostic request short and bounded while matching the story client.
TEST_PROMPT = "Reply with only OK. This is an API connection test."


# Convert API failures into useful messages without printing credentials or payloads.
def describe_api_error(error: Exception) -> str:
    if isinstance(error, APIConnectionError):
        return "Could not connect to OpenAI API. Check network, proxy, TLS, or firewall settings."

    if isinstance(error, APIStatusError):
        status_code = error.status_code
        if status_code == 401:
            detail = "OpenAI rejected the API key (HTTP 401). Check OPENAI_API_KEY."
        elif status_code == 403:
            detail = "OpenAI denied the request (HTTP 403). Check account and model access."
        elif status_code == 429:
            detail = "OpenAI usage or rate limit reached (HTTP 429). Check account usage and retry later."
        else:
            detail = f"OpenAI returned HTTP {status_code}. Check API and model settings."

        request_id = getattr(error, "request_id", None)
        if request_id:
            detail += f" Request ID: {request_id}."
        return detail

    return f"API check failed ({type(error).__name__}). Check API and SDK setup."


# Make one small Responses API request to check key, network, and model access.
def check_api_connection() -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Error: OPENAI_API_KEY is not set in this terminal.", file=sys.stderr)
        return 2

    try:
        certificate_bundle, httpx2_version = verify_tls_imports()
        validate_openai_sdk_version()
    except ConfigurationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if httpx2_version:
        transport_status = f"httpx2 import verified ({httpx2_version})"
    else:
        transport_status = "httpx2 not installed (not required by OpenAI SDK 2.x)"
    print(f"TLS imports verified: certifi bundle found; {transport_status}.")

    try:
        client = OpenAI(
            api_key=api_key,
            timeout=API_TIMEOUT_SECONDS,
            max_retries=API_MAX_RETRIES,
        )
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": REASONING_EFFORT},
            text={"verbosity": VERBOSITY},
            instructions="Return a brief confirmation that the API test completed.",
            input=TEST_PROMPT,
            store=False,
        )
    except Exception as error:
        print(f"Error: {describe_api_error(error)}", file=sys.stderr)
        return 1

    if not getattr(response, "id", None):
        print("Error: OpenAI returned no response ID; API check did not complete.", file=sys.stderr)
        return 1

    print("OpenAI Responses API connection succeeded.")
    request_id = getattr(response, "_request_id", None)
    if request_id:
        print(f"Request ID: {request_id}")
    return 0


# Provide standard help and process exit codes for the diagnostic command.
def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="testAPI.py",
        description="Send one short request to check OpenAI Responses API access.",
        epilog="Set OPENAI_API_KEY in this terminal before running the test.",
    )
    parser.parse_args(arguments)
    return check_api_connection()


# Run the connection check only when this file is launched as a command.
if __name__ == "__main__":
    raise SystemExit(main())
