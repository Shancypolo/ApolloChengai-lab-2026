import os
import certifi
import httpx2
from openai import OpenAI

api_key = os.environ.get("OPENAI_API_KEY")
http_client = httpx2.Client(verify=certifi.where())
client = OpenAI(api_key=api_key, http_client=http_client)

try:
    response = client.responses.create(
        model="gpt-5.6-luna",
        input="what is the current time?",
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
    print(response.output_text)
except Exception as error:
    print("The API request failed:")
    print(error)
