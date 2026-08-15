"""
gui_demo_simple.py
------------------
A minimal local web interface for chatting with an AI.
Run this file and it opens automatically in your browser.
Press Ctrl+C in the terminal to stop it.
"""

from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import CustomTkinter as ctk
import os
import threading
import webbrowser

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are a helpful assistant.
Keep your responses concise — two or three sentences unless the user asks for more."""

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Demo</title>
    <style>
        body {
            font-family: system-ui, sans-serif;
            max-width: 700px;
            margin: 40px auto;
            padding: 0 20px;
            background: #1a1a1a;
            color: #e0e0e0;
        }
        h1 { font-size: 1.4rem; color: #7eb8f7; margin-bottom: 20px; }

        #output {
            background: #2a2a2a;
            border-radius: 8px;
            padding: 16px;
            height: 360px;
            overflow-y: auto;
            margin-bottom: 16px;
            font-size: 0.95rem;
            line-height: 1.6;
        }
        .user-msg  { color: #a8d8a8; margin-bottom: 8px; }
        .ai-msg    { color: #e0e0e0; margin-bottom: 16px; }
        .label     { font-size: 0.75rem; color: #888; text-transform: uppercase;
                     letter-spacing: 0.05em; margin-bottom: 2px; }

        textarea {
            width: 100%;
            height: 80px;
            background: #2a2a2a;
            color: #e0e0e0;
            border: 1px solid #444;
            border-radius: 8px;
            padding: 10px;
            font-size: 0.95rem;
            resize: vertical;
            box-sizing: border-box;
        }
        button {
            margin-top: 10px;
            padding: 10px 24px;
            background: #7eb8f7;
            color: #1a1a1a;
            border: none;
            border-radius: 6px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
        }
        button:hover    { background: #a8d0ff; }
        button:disabled { background: #444; color: #888; cursor: default; }
    </style>
</head>
<body>
    <h1>AI Demo</h1>

    <div id="output"></div>

    <textarea id="input" placeholder="Type your message here..."></textarea>
    <br>
    <button id="btn" onclick="sendMessage()">Submit</button>

    <script>
        // Ctrl+Enter or Cmd+Enter to submit
        document.getElementById('input').addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') sendMessage();
        });

        async function sendMessage() {
            const input  = document.getElementById('input');
            const btn    = document.getElementById('btn');
            const output = document.getElementById('output');
            const text   = input.value.trim();
            if (!text) return;

            // show the user's message
            output.innerHTML += `<div class="label">You</div><div class="user-msg">${text}</div>`;
            input.value = '';
            btn.disabled = true;
            btn.textContent = 'Thinking...';
            output.scrollTop = output.scrollHeight;

            // send to Python server and get response
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();

            // show the AI response
            output.innerHTML += `<div class="label">AI</div><div class="ai-msg">${data.reply}</div>`;
            btn.disabled = false;
            btn.textContent = 'Submit';
            output.scrollTop = output.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "No message received."})

    response = client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ]
    )

    reply  = response.choices[0].message.content
    tokens = response.usage.total_tokens
    print(f"[tokens used: {tokens}]")

    return jsonify({"reply": reply})

# ── run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting — opening in your browser...")
    print("Press Ctrl+C to stop")
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False)
