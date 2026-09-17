import os
import sys

import certifi
import httpx2
from openai import OpenAI


def print_error(stage, error):
    """Print one useful error without exposing the API key."""
    print(
        f"ERROR during {stage}: {type(error).__name__}: {error}",
        file=sys.stderr,
    )


def main():
    """Run one diagnostic Responses API request and report every outcome."""
    print("test.py: starting")
    exit_code = 1

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: OPENAI_API_KEY is missing.", file=sys.stderr)
            return exit_code

        http_client = httpx2.Client(verify=certifi.where())
        client = OpenAI(
            api_key=api_key,
            http_client=http_client,
            timeout=60.0,
            max_retries=0,
        )
        print("test.py: client created")

        response = client.responses.create(
            model="gpt-5.6-luna",
            input="What is the current time? If a location is needed, ask for it.",
            tools=[
                {"type": "tool_search", "execution": "server"},
                {"type": "web_search_preview", "search_context_size": "low"},
                {
                    "type": "function",
                    "name": "get_current_time",
                    "description": "Get the current time for a location.",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                        "required": ["location"],
                        "additionalProperties": False,
                    },
                    "defer_loading": True,
                },
            ],
        )
        print(f"test.py: response status = {getattr(response, 'status', 'unknown')}")
        print(f"test.py: response id = {getattr(response, 'id', 'unknown')}")

        output_text = response.output_text or ""
        if output_text.strip():
            print("--- response text ---")
            print(output_text)
            exit_code = 0
        else:
            print("ERROR: API returned no response text.", file=sys.stderr)
            output_items = getattr(response, "output", []) or []
            if output_items:
                print("Output items returned:", file=sys.stderr)
                for item in output_items:
                    print(
                        f"- type={getattr(item, 'type', 'unknown')}; "
                        f"details={item!r}",
                        file=sys.stderr,
                    )
            else:
                print("ERROR: API returned no output items either.", file=sys.stderr)
    except KeyboardInterrupt:
        print("ERROR: interrupted by user.", file=sys.stderr)
    except Exception as error:
        print_error("API diagnostic request", error)
    finally:
        print(f"test.py: finished with exit code {exit_code}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
