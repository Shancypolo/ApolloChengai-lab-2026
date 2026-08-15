"""
gui_demo_tkinter.py
-------------------
A minimal desktop GUI for chatting with an AI using CustomTkinter.
Run this file and a window opens on your desktop.

Install dependencies first:
    uv pip install customtkinter openai

Note: the window will freeze briefly while waiting for the AI response.
That is expected for now.
"""

import customtkinter as ctk
from openai import OpenAI
import os

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are a helpful assistant.
Keep your responses concise — two or three sentences unless the user asks for more."""

def get_response(user_message):
    """Call the OpenAI API and return the reply text."""
    response = client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ]
    )
    tokens = response.usage.total_tokens
    print(f"[tokens used: {tokens}]")
    return response.choices[0].message.content

def on_submit():
    """Called when the user clicks Submit or presses Ctrl+Enter."""
    user_text = input_field.get("1.0", "end").strip()
    if not user_text:
        return

    # show the user's message and clear the input
    output_area.configure(state="normal")
    output_area.insert("end", f"You\n{user_text}\n\n")
    output_area.see("end")
    input_field.delete("1.0", "end")
    submit_button.configure(state="disabled", text="Thinking...")
    app.update()  # force the window to redraw before the API call freezes it

    # call the API and replace the placeholder with the real response
    reply = get_response(user_text)
    output_area.insert("end", f"AI\n{reply}\n\n")
    output_area.configure(state="disabled")
    output_area.see("end")
    submit_button.configure(state="normal", text="Submit")

# ── build the window ───────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("AI Demo")
app.geometry("640x520")
app.resizable(True, True)

# output area — read only, scrollable
output_area = ctk.CTkTextbox(app, width=600, height=320, state="disabled",
                              font=("System", 13), wrap="word")
output_area.pack(padx=20, pady=(20, 10))

# input field
input_field = ctk.CTkTextbox(app, width=600, height=80, font=("System", 13))
input_field.pack(padx=20, pady=(0, 10))

# Ctrl+Enter or Cmd+Enter to submit
app.bind("<Control-Return>", lambda e: on_submit())
app.bind("<Command-Return>",  lambda e: on_submit())

# submit button
submit_button = ctk.CTkButton(app, text="Submit", command=on_submit, width=120)
submit_button.pack(pady=(0, 20))

app.mainloop()