"""
gui_demo_tkinter_full.py
------------------------
A desktop GUI demonstrating common UI elements students might use
in their own projects. Uses CustomTkinter for a modern look.

Install dependencies first:
    uv pip install customtkinter openai

UI elements demonstrated:
    - Text input (single line)
    - Textbox (multi-line)
    - Dropdown / option menu
    - Checkboxes
    - Radio buttons
    - Slider with live label
    - Tabs (CTkTabview)
    - Buttons
    - Read-only scrollable output area
    - Token usage display
"""

import customtkinter as ctk
from openai import OpenAI
import os

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ── Luna pricing (per million tokens) ─────────────────────────────────────
INPUT_PRICE  = 0.20
OUTPUT_PRICE = 1.20

def calc_cost(input_tokens, output_tokens):
    cost = (input_tokens / 1_000_000 * INPUT_PRICE) + \
           (output_tokens / 1_000_000 * OUTPUT_PRICE)
    return f"${cost:.4f}"

def call_api(system_prompt, user_prompt):
    """Call the OpenAI API and return (reply, input_tokens, output_tokens)."""
    response = client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
    )
    reply         = response.choices[0].message.content
    input_tokens  = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    return reply, input_tokens, output_tokens

def show_thinking():
    """Gray out submit, show Thinking in output, force redraw."""
    submit_button.configure(state="disabled", text="Thinking...")
    output_area.configure(state="normal")
    output_area.insert("end", "Thinking...\n\n")
    output_area.see("end")
    app.update()

def show_response(reply, input_tokens, output_tokens):
    """Replace Thinking placeholder with real response and update token bar."""
    output_area.delete("end-3l", "end")  # remove "Thinking...\n\n"
    output_area.insert("end", f"{reply}\n\n")
    output_area.configure(state="disabled")
    output_area.see("end")
    submit_button.configure(state="normal", text="Submit")

    cost = calc_cost(input_tokens, output_tokens)
    token_label.configure(
        text=f"Input: {input_tokens}  |  Output: {output_tokens}  |  "
             f"Total: {input_tokens + output_tokens}  |  Cost: {cost}"
    )

# ── submit handlers — one per tab ─────────────────────────────────────────

def submit_basic():
    topic   = basic_topic.get().strip()
    context = basic_context.get("1.0", "end").strip()
    style   = basic_style.get()

    if not topic:
        return

    style_map = {
        "Concise (2-3 sentences)": "Respond in 2 to 3 sentences.",
        "Detailed (full paragraph)": "Respond in one full detailed paragraph.",
        "Simple (explain like I'm 12)": "Explain as if to a 12-year-old.",
        "Bullet points": "Respond as a short bullet-point list.",
    }
    system = f"You are a helpful assistant. {style_map.get(style, '')}"
    user   = f"Explain: {topic}"
    if context:
        user += f"\n\nExtra context: {context}"

    show_thinking()
    reply, i, o = call_api(system, user)
    show_response(reply, i, o)

def submit_options():
    topic    = options_topic.get().strip()
    audience = audience_var.get()

    if not topic:
        return

    audience_map = {
        "High school student": "a high school student",
        "Domain expert":       "a domain expert",
        "Young child":         "a young child around age 8",
    }
    extras = []
    if chk_examples.get(): extras.append("include a real-world example")
    if chk_analogy.get():  extras.append("include an analogy")
    if chk_quiz.get():     extras.append("end with one quiz question")

    system = f"You are a helpful tutor explaining things to {audience_map.get(audience, 'a student')}."
    user   = f"Explain: {topic}"
    if extras:
        user += f"\n\nPlease also: {', '.join(extras)}."

    show_thinking()
    reply, i, o = call_api(system, user)
    show_response(reply, i, o)

def submit_advanced():
    topic   = adv_topic.get().strip()
    persona = adv_persona.get().strip()
    words   = int(slider_var.get())

    if not topic:
        return

    system = f"You are {persona or 'a helpful assistant'}. Keep your response under {words} words."
    user   = f"Explain: {topic}"

    show_thinking()
    reply, i, o = call_api(system, user)
    show_response(reply, i, o)

def update_slider_label(value):
    slider_label.configure(text=f"Max words: {int(float(value))}")

# ── build the window ───────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("AI Demo — UI Elements")
app.geometry("700x720")
app.resizable(True, True)

PAD = {"padx": 20, "pady": (0, 10)}

# ── tabs ───────────────────────────────────────────────────────────────────
tabs = ctk.CTkTabview(app, width=660, height=320)
tabs.pack(padx=20, pady=(20, 10))
tabs.add("Basic")
tabs.add("Options")
tabs.add("Advanced")

# ── TAB 1: BASIC ───────────────────────────────────────────────────────────
t1 = tabs.tab("Basic")

ctk.CTkLabel(t1, text="Topic (single-line input)", anchor="w").pack(fill="x", padx=10, pady=(10,2))
basic_topic = ctk.CTkEntry(t1, placeholder_text="e.g. photosynthesis")
basic_topic.pack(fill="x", padx=10, pady=(0,8))

ctk.CTkLabel(t1, text="Extra context (multi-line textbox)", anchor="w").pack(fill="x", padx=10, pady=(0,2))
basic_context = ctk.CTkTextbox(t1, height=60)
basic_context.pack(fill="x", padx=10, pady=(0,8))

ctk.CTkLabel(t1, text="Response style (dropdown)", anchor="w").pack(fill="x", padx=10, pady=(0,2))
basic_style = ctk.CTkOptionMenu(t1, values=[
    "Concise (2-3 sentences)",
    "Detailed (full paragraph)",
    "Simple (explain like I'm 12)",
    "Bullet points",
])
basic_style.pack(fill="x", padx=10, pady=(0,10))

# ── TAB 2: OPTIONS ─────────────────────────────────────────────────────────
t2 = tabs.tab("Options")

ctk.CTkLabel(t2, text="Topic", anchor="w").pack(fill="x", padx=10, pady=(10,2))
options_topic = ctk.CTkEntry(t2, placeholder_text="e.g. how vaccines work")
options_topic.pack(fill="x", padx=10, pady=(0,10))

ctk.CTkLabel(t2, text="What to include (checkboxes)", anchor="w").pack(fill="x", padx=10, pady=(0,4))
chk_examples = ctk.CTkCheckBox(t2, text="Include a real-world example")
chk_examples.pack(anchor="w", padx=20, pady=2)
chk_examples.select()  # checked by default
chk_analogy = ctk.CTkCheckBox(t2, text="Include an analogy")
chk_analogy.pack(anchor="w", padx=20, pady=2)
chk_quiz = ctk.CTkCheckBox(t2, text="End with a quiz question")
chk_quiz.pack(anchor="w", padx=20, pady=(2,10))

ctk.CTkLabel(t2, text="Audience (radio buttons)", anchor="w").pack(fill="x", padx=10, pady=(0,4))
audience_var = ctk.StringVar(value="High school student")
for option in ["High school student", "Domain expert", "Young child"]:
    ctk.CTkRadioButton(t2, text=option, variable=audience_var, value=option).pack(
        anchor="w", padx=20, pady=2)

# ── TAB 3: ADVANCED ────────────────────────────────────────────────────────
t3 = tabs.tab("Advanced")

ctk.CTkLabel(t3, text="Topic", anchor="w").pack(fill="x", padx=10, pady=(10,2))
adv_topic = ctk.CTkEntry(t3, placeholder_text="e.g. black holes")
adv_topic.pack(fill="x", padx=10, pady=(0,10))

ctk.CTkLabel(t3, text="AI persona (used in system prompt)", anchor="w").pack(fill="x", padx=10, pady=(0,2))
adv_persona = ctk.CTkEntry(t3, placeholder_text="e.g. a patient tutor, a Socratic teacher")
adv_persona.pack(fill="x", padx=10, pady=(0,10))

slider_label = ctk.CTkLabel(t3, text="Max words: 100", anchor="w")
slider_label.pack(fill="x", padx=10, pady=(0,2))
slider_var = ctk.DoubleVar(value=100)
ctk.CTkSlider(t3, from_=30, to=300, variable=slider_var, command=update_slider_label).pack(
    fill="x", padx=10, pady=(0,10))

# ── SHARED SUBMIT BUTTON ───────────────────────────────────────────────────
submit_button = ctk.CTkButton(app, text="Submit", width=120, command=lambda: {
    "Basic":    submit_basic,
    "Options":  submit_options,
    "Advanced": submit_advanced,
}[tabs.get()]())
submit_button.pack(pady=(0, 10))

# ── OUTPUT AREA ────────────────────────────────────────────────────────────
output_area = ctk.CTkTextbox(app, width=660, height=180, state="disabled",
                              font=("System", 13), wrap="word")
output_area.pack(padx=20, pady=(0, 6))

# token usage bar
token_label = ctk.CTkLabel(app, text="Input: —  |  Output: —  |  Total: —  |  Cost: —",
                            font=("System", 11), text_color="gray")
token_label.pack(pady=(0, 16))

app.mainloop()