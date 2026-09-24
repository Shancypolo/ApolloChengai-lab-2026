"""Check OpenAI Responses API connectivity for StoryEngine."""
from __future__ import annotations

import argparse
import os
import sys

import story_memory

# Prompt, status messages, and exit codes used by this diagnostic.
TEST_PROMPT = "Reply with OK. This is an API connection test."
TEST_SUCCESS_MESSAGE = "TLS imports verified; OpenAI Responses API connection succeeded. Request ID:"
TEST_ERROR_TEMPLATE = "Error: {message}"
TEST_REQUEST_ERROR_TEMPLATE = "OpenAI API check failed ({error_type})."
TEST_REASONING_SETTINGS = {story_memory.REASONING_PARAMETER_KEY: story_memory.REASONING_EFFORT}
TEST_TEXT_SETTINGS = {story_memory.TEXT_VERBOSITY_PARAMETER_KEY: story_memory.VERBOSITY}
TEST_EXIT_SUCCESS, TEST_EXIT_FAILURE, TEST_EXIT_CONFIGURATION = 0, 1, 2

# Verify runtime setup and make one small Responses API request.
def main(command_arguments: list[str] | None = None) -> int:
    argparse.ArgumentParser().parse_args(command_arguments)
    openai_api_key = os.environ.get(story_memory.OPENAI_API_KEY_ENV, "").strip()
    if not openai_api_key:
        print(f"Error: {story_memory.ERROR_API_KEY_MISSING}", file=sys.stderr)
        return TEST_EXIT_CONFIGURATION
    try:
        story_memory.verify_tls_imports()
        story_memory.validate_openai_sdk_version()
        openai_client = story_memory.create_openai_client(openai_api_key)
        api_response = openai_client.responses.create(
            model=story_memory.MODEL,
            reasoning=TEST_REASONING_SETTINGS,
            text=TEST_TEXT_SETTINGS,
            instructions=TEST_PROMPT,
            input=TEST_PROMPT,
            store=False,
        )
    except story_memory.ConfigurationError as configuration_error:
        print(TEST_ERROR_TEMPLATE.format(message=configuration_error), file=sys.stderr)
        return TEST_EXIT_CONFIGURATION
    except Exception as api_error:
        api_error_message = TEST_REQUEST_ERROR_TEMPLATE.format(error_type=type(api_error).__name__)
        print(TEST_ERROR_TEMPLATE.format(message=api_error_message), file=sys.stderr)
        return TEST_EXIT_FAILURE
    print(TEST_SUCCESS_MESSAGE, getattr(api_response, "_request_id", ""))
    return TEST_EXIT_SUCCESS

if __name__ == "__main__":
    raise SystemExit(main())
