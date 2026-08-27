"""
gui_demo.py
-----------
A local web app demonstrating common UI elements students might use
in their own projects. Run this file and it opens automatically in your browser.
Press Ctrl+C in the terminal to stop it.

UI elements demonstrated:
    - Text input (single line)
    - Textarea (multi-line)
    - Dropdown / select box
    - Checkboxes
    - Radio buttons
    - Tabs
    - Buttons (submit and clear)
    - Displaying AI responses
    - Token usage display
"""

from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import os
import threading
import webbrowser

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Demo — UI Elements</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: system-ui, -apple-system, sans-serif;
    background: #1a1a1a;
    color: #e0e0e0;
    padding: 32px 20px;
  }

  h1 { font-size: 1.3rem; color: #7eb8f7; margin-bottom: 24px; }
  h2 { font-size: 0.95rem; color: #aaa; text-transform: uppercase;
       letter-spacing: 0.06em; margin-bottom: 12px; }

  .container { max-width: 720px; margin: 0 auto; }

  /* ── tabs ── */
  .tab-bar {
    display: flex; gap: 4px; margin-bottom: 24px;
    border-bottom: 1px solid #333;
  }
  .tab-btn {
    background: none; border: none; color: #888;
    font-size: 0.9rem; padding: 8px 16px; cursor: pointer;
    border-bottom: 2px solid transparent; margin-bottom: -1px;
    transition: color 0.15s;
  }
  .tab-btn.active { color: #7eb8f7; border-bottom-color: #7eb8f7; }
  .tab-btn:hover:not(.active) { color: #ccc; }

  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* ── form elements ── */
  .field { margin-bottom: 20px; }
  label { display: block; font-size: 0.85rem; color: #aaa; margin-bottom: 6px; }

  input[type="text"],
  textarea,
  select {
    width: 100%;
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 0.9rem;
    padding: 8px 12px;
    font-family: inherit;
    transition: border-color 0.15s;
  }
  input[type="text"]:focus,
  textarea:focus,
  select:focus {
    outline: none; border-color: #7eb8f7;
  }
  textarea { height: 100px; resize: vertical; }
  select option { background: #2a2a2a; }

  /* checkboxes and radios */
  .options-group { display: flex; flex-direction: column; gap: 8px; }
  .option-row {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.9rem; cursor: pointer;
  }
  input[type="checkbox"],
  input[type="radio"] {
    width: 16px; height: 16px;
    accent-color: #7eb8f7; cursor: pointer;
  }

  /* ── buttons ── */
  .btn-row { display: flex; gap: 10px; margin-top: 8px; }
  button.primary {
    background: #7eb8f7; color: #111; border: none;
    padding: 9px 22px; border-radius: 6px; font-size: 0.9rem;
    font-weight: 600; cursor: pointer; transition: background 0.15s;
  }
  button.primary:hover { background: #a8d0ff; }
  button.primary:disabled { background: #444; color: #777; cursor: default; }

  button.secondary {
    background: none; color: #aaa; border: 1px solid #444;
    padding: 9px 22px; border-radius: 6px; font-size: 0.9rem;
    cursor: pointer; transition: all 0.15s;
  }
  button.secondary:hover { border-color: #777; color: #e0e0e0; }

  /* ── output ── */
  #output {
    background: #2a2a2a; border-radius: 8px;
    padding: 16px; min-height: 80px;
    font-size: 0.9rem; line-height: 1.7;
    white-space: pre-wrap; color: #e0e0e0;
    margin-top: 20px;
  }
  #output.empty { color: #555; font-style: italic; }

  .token-bar {
    display: flex; gap: 16px; margin-top: 10px;
    font-size: 0.78rem; color: #666;
  }
  .token-bar span { color: #888; }

  /* ── slider ── */
  input[type="range"] {
    width: 100%; accent-color: #7eb8f7; cursor: pointer;
  }
  .range-row {
    display: flex; justify-content: space-between;
    font-size: 0.8rem; color: #666; margin-top: 4px;
  }
</style>
</head>
<body>
<div class="container">
  <h1>AI Demo — UI Elements</h1>

  <!-- ── TABS ── -->
  <div class="tab-bar">
    <button class="tab-btn active" onclick="switchTab('basic')">Basic</button>
    <button class="tab-btn"        onclick="switchTab('options')">Options</button>
    <button class="tab-btn"        onclick="switchTab('advanced')">Advanced</button>
  </div>

  <!-- ── TAB 1: BASIC ── -->
  <div id="tab-basic" class="tab-panel active">
    <h2>Text inputs</h2>

    <div class="field">
      <label for="topic">Topic (single-line input)</label>
      <input type="text" id="topic" placeholder="e.g. photosynthesis">
    </div>

    <div class="field">
      <label for="context">Extra context (multi-line textarea)</label>
      <textarea id="context" placeholder="Add any background information here..."></textarea>
    </div>

    <div class="field">
      <label for="style">Response style (dropdown)</label>
      <select id="style">
        <option value="concise">Concise — 2 to 3 sentences</option>
        <option value="detailed">Detailed — a full paragraph</option>
        <option value="eli5">Simple — explain like I'm 12</option>
        <option value="bullet">Bullet points</option>
      </select>
    </div>

    <div class="btn-row">
      <button class="primary" id="submit-basic" onclick="submitBasic()">Ask AI</button>
      <button class="secondary" onclick="clearAll()">Clear</button>
    </div>
  </div>

  <!-- ── TAB 2: OPTIONS ── -->
  <div id="tab-options" class="tab-panel">
    <h2>Checkboxes — what to include</h2>

    <div class="field">
      <div class="options-group">
        <label class="option-row">
          <input type="checkbox" id="chk-examples" checked>
          Include a real-world example
        </label>
        <label class="option-row">
          <input type="checkbox" id="chk-analogy">
          Include an analogy
        </label>
        <label class="option-row">
          <input type="checkbox" id="chk-quiz">
          End with a quiz question
        </label>
      </div>
    </div>

    <h2 style="margin-top: 24px;">Radio buttons — audience</h2>

    <div class="field">
      <div class="options-group">
        <label class="option-row">
          <input type="radio" name="audience" value="student" checked>
          High school student
        </label>
        <label class="option-row">
          <input type="radio" name="audience" value="expert">
          Domain expert
        </label>
        <label class="option-row">
          <input type="radio" name="audience" value="child">
          Young child
        </label>
      </div>
    </div>

    <div class="field" style="margin-top: 24px;">
      <label for="topic2">Topic</label>
      <input type="text" id="topic2" placeholder="e.g. how vaccines work">
    </div>

    <div class="btn-row">
      <button class="primary" id="submit-options" onclick="submitOptions()">Ask AI</button>
      <button class="secondary" onclick="clearAll()">Clear</button>
    </div>
  </div>

  <!-- ── TAB 3: ADVANCED ── -->
  <div id="tab-advanced" class="tab-panel">
    <h2>Slider — response length</h2>

    <div class="field">
      <label>Max response length: <strong id="words-out">100</strong> words</label>
      <input type="range" id="words" min="30" max="300" value="100" step="10"
             oninput="document.getElementById('words-out').textContent = this.value">
      <div class="range-row"><span>30</span><span>300</span></div>
    </div>

    <div class="field">
      <label for="topic3">Topic</label>
      <input type="text" id="topic3" placeholder="e.g. black holes">
    </div>

    <div class="field">
      <label for="persona">AI persona (text input used in system prompt)</label>
      <input type="text" id="persona" placeholder="e.g. a patient tutor, a Socratic teacher">
    </div>

    <div class="btn-row">
      <button class="primary" id="submit-advanced" onclick="submitAdvanced()">Ask AI</button>
      <button class="secondary" onclick="clearAll()">Clear</button>
    </div>
  </div>

  <!-- ── OUTPUT (shared across all tabs) ── -->
  <div id="output" class="empty">Your response will appear here...</div>
  <div class="token-bar">
    <div>Input tokens: <span id="tok-in">—</span></div>
    <div>Output tokens: <span id="tok-out">—</span></div>
    <div>Total: <span id="tok-total">—</span></div>
    <div>Est. cost: <span id="tok-cost">—</span></div>
  </div>
</div>

<script>
  function switchTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
  }

  function setLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    btn.disabled = loading;
    btn.textContent = loading ? 'Thinking...' : 'Ask AI';
  }

  function showResponse(data) {
    const out = document.getElementById('output');
    out.classList.remove('empty');
    out.textContent = data.reply;
    document.getElementById('tok-in').textContent    = data.input_tokens;
    document.getElementById('tok-out').textContent   = data.output_tokens;
    document.getElementById('tok-total').textContent = data.total_tokens;
    document.getElementById('tok-cost').textContent  = '$' + data.cost;
  }

  function clearAll() {
    const out = document.getElementById('output');
    out.classList.add('empty');
    out.textContent = 'Your response will appear here...';
    ['tok-in','tok-out','tok-total','tok-cost'].forEach(id => {
      document.getElementById(id).textContent = '—';
    });
  }

  async function post(payload, btnId) {
    setLoading(btnId, true);
    const res  = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    showResponse(data);
    setLoading(btnId, false);
  }

  function submitBasic() {
    post({
      mode:    'basic',
      topic:   document.getElementById('topic').value,
      context: document.getElementById('context').value,
      style:   document.getElementById('style').value
    }, 'submit-basic');
  }

  function submitOptions() {
    post({
      mode:      'options',
      topic:     document.getElementById('topic2').value,
      examples:  document.getElementById('chk-examples').checked,
      analogy:   document.getElementById('chk-analogy').checked,
      quiz:      document.getElementById('chk-quiz').checked,
      audience:  document.querySelector('input[name="audience"]:checked').value
    }, 'submit-options');
  }

  function submitAdvanced() {
    post({
      mode:    'advanced',
      topic:   document.getElementById('topic3').value,
      persona: document.getElementById('persona').value,
      words:   document.getElementById('words').value
    }, 'submit-advanced');
  }
</script>
</body>
</html>
"""

# ── Luna pricing (per million tokens) ─────────────────────────────────────
INPUT_PRICE  = 0.20
OUTPUT_PRICE = 1.20

def calc_cost(input_tokens, output_tokens):
    cost = (input_tokens / 1_000_000 * INPUT_PRICE) + \
           (output_tokens / 1_000_000 * OUTPUT_PRICE)
    return f"{cost:.4f}"

# ── routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    mode = data.get("mode")

    # ── basic tab ──
    if mode == "basic":
        topic   = data.get("topic", "").strip()
        context = data.get("context", "").strip()
        style   = data.get("style", "concise")

        style_map = {
            "concise":  "Respond in 2 to 3 sentences.",
            "detailed": "Respond in one full detailed paragraph.",
            "eli5":     "Explain as if to a 12-year-old, using simple language.",
            "bullet":   "Respond as a short bullet-point list.",
        }

        system = f"You are a helpful assistant. {style_map.get(style, '')}"
        user   = f"Explain: {topic}"
        if context:
            user += f"\n\nExtra context: {context}"

    # ── options tab ──
    elif mode == "options":
        topic    = data.get("topic", "").strip()
        audience = data.get("audience", "student")
        examples = data.get("examples", False)
        analogy  = data.get("analogy",  False)
        quiz     = data.get("quiz",     False)

        audience_map = {
            "student": "a high school student",
            "expert":  "a domain expert",
            "child":   "a young child around age 8",
        }

        extras = []
        if examples: extras.append("include a real-world example")
        if analogy:  extras.append("include an analogy")
        if quiz:     extras.append("end with one quiz question")

        system = f"You are a helpful tutor explaining things to {audience_map.get(audience, 'a student')}."
        user   = f"Explain: {topic}"
        if extras:
            user += f"\n\nPlease also: {', '.join(extras)}."

    # ── advanced tab ──
    elif mode == "advanced":
        topic   = data.get("topic",   "").strip()
        persona = data.get("persona", "a helpful assistant").strip()
        words   = data.get("words",   100)

        system = f"You are {persona or 'a helpful assistant'}. Keep your response under {words} words."
        user   = f"Explain: {topic}"

    else:
        return jsonify({"reply": "Unknown mode.", "input_tokens": 0,
                        "output_tokens": 0, "total_tokens": 0, "cost": "0.0000"})

    if not user.strip() or "Explain: " == user.strip():
        return jsonify({"reply": "Please enter a topic first.",
                        "input_tokens": 0, "output_tokens": 0,
                        "total_tokens": 0, "cost": "0.0000"})

    response = client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]
    )

    reply         = response.choices[0].message.content
    input_tokens  = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    total_tokens  = response.usage.total_tokens
    cost          = calc_cost(input_tokens, output_tokens)

    print(f"[{mode}] tokens: {input_tokens} in / {output_tokens} out | cost: ${cost}")

    return jsonify({
        "reply":         reply,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "total_tokens":  total_tokens,
        "cost":          cost,
    })

# ── run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Starting — opening in your browser...")
    print("Press Ctrl+C to stop")
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False)
