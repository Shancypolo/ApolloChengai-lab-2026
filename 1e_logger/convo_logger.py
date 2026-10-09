"""
Conversation Logger
-------------------
This program is supposed to:
- Let the user have a conversation with an AI assistant
- Save every exchange to a log file so you can review previous sessions
- Load previous conversation history when you start a new session
- Let the user type 'quit' to exit

It was written by someone who assumed everything would always work perfectly.
It has problems. Find them, understand them, and fix them.
"""

from openai import OpenAI, OpenAIError
import json
import os

try:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
except KeyError as error:
    print(f"Error: Environment variable {error.args[0]} was not found.")
    print("Explanation: The OpenAI client needs an API key to start.")
    print("Solution: Set the OPENAI_API_KEY environment variable and run the program again.")
    raise SystemExit(1)
LOG_FILE = "conversation_log.json"

SYSTEM_PROMPT = """You are a helpful assistant. Be concise — keep responses to 2-3 sentences unless the user specifically asks for more detail."""


def load_history():
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
        return data["history"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as error:
        print(f"Error: {error}")
        if isinstance(error, FileNotFoundError):
            print("Explanation: The conversation log file does not exist yet.")
            print("Solution: Creating a new log with an empty history.")
        elif isinstance(error, json.JSONDecodeError):
            print("Explanation: The conversation log is empty or contains invalid JSON.")
            print("Solution: Replacing it with a valid empty history log.")
        else:
            print('Explanation: The conversation log does not contain a "history" key.')
            print('Solution: Replacing it with a valid empty history log.')

        data = {"history": [{"user": "", "assistant": ""}]}
        with open(LOG_FILE, "w") as f:
            json.dump(data, f)
        return data["history"]


def save_history(history):
    with open(LOG_FILE, "w") as f:
        json.dump({"history": history}, f)


def get_ai_response(conversation):
    try:
        response = client.chat.completions.create(
            model="gpt-5.6-luna",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation
        )
    except OpenAIError as error:
        print(f"Error: {error}")
        print("Explanation: The OpenAI API request failed.")
        print("Solution: Check the API key, model name, network connection, and account limits.")
        return None

    return response.choices[0].message.content


def display_previous_sessions(history):
    print(f"\nLoaded {len(history)} previous exchanges.")
    print("Last exchange:")
    try:
        last = history[-1]
    except IndexError as error:
        print(f"Error: {error}")
        print("Explanation: The history list is empty, so it has no last exchange.")
        print("Solution: Start a conversation to add the first user/assistant exchange.")
        return

    print(f"  You: {last['user']}")
    print(f"  AI: {last['assistant']}")


def main():
    print("Conversation Logger")
    print("Type 'quit' to exit\n")

    history = load_history()
    display_previous_sessions(history)

    conversation = []
    for exchange in history:
        conversation.append({"role": "user", "content": exchange["user"]})
        conversation.append({"role": "assistant", "content": exchange["assistant"]})

    while True:
        user_input = input("\nYou: ")

        if user_input == "quit":
            save_history(history)
            print("Conversation saved.")
            break

        conversation.append({"role": "user", "content": user_input})

        print("Thinking...")
        ai_response = get_ai_response(conversation)
        if ai_response is None:
            conversation.pop()
            continue

        conversation.append({"role": "assistant", "content": ai_response})
        history.append({"user": user_input, "assistant": ai_response})

        print(f"AI: {ai_response}")

    save_history(history)


if __name__ == "__main__":
    main()