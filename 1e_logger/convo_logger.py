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

from openai import OpenAI
import json
import os

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

LOG_FILE = "conversation_log.json"

SYSTEM_PROMPT = """You are a helpful assistant. Be concise — keep responses to 2-3 sentences unless the user specifically asks for more detail."""


def load_history():
    with open(LOG_FILE, "r") as f:
        data = json.load(f)
    return data["history"]


def save_history(history):
    with open(LOG_FILE, "w") as f:
        json.dump({"history": history}, f)


def get_ai_response(conversation):
    response = client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation
    )
    return response.choices[0].message.content


def display_previous_sessions(history):
    print(f"\nLoaded {len(history)} previous exchanges.")
    print("Last exchange:")
    last = history[-1]
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

        conversation.append({"role": "assistant", "content": ai_response})
        history.append({"user": user_input, "assistant": ai_response})

        print(f"AI: {ai_response}")

    save_history(history)


if __name__ == "__main__":
    main()
