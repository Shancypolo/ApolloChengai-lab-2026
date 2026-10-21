
import os, json, tempfile, certifi
from pathlib import Path
os.environ["SSL_CERT_FILE"] = certifi.where()
from yt_dlp import YoutubeDL
from openai import OpenAI

video_id = input("Video ID: ").strip()
with tempfile.TemporaryDirectory() as folder:
    with YoutubeDL({"quiet": True, "skip_download": True, "writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["en"], "subtitlesformat": "json3", "outtmpl": f"{folder}/%(id)s.%(ext)s"}) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    file = next(Path(folder).glob("*.json3"), None)
    if not file: raise SystemExit("No English captions available.")
    data = json.loads(file.read_text(encoding="utf-8"))
    transcript = " ".join(s["utf8"].strip() for e in data["events"] for s in e.get("segs", []) if s.get("utf8", "").strip())

response = OpenAI().responses.create(model="gpt-5.6-luna", reasoning={"effort": "high"}, tools=[], instructions="Write a concise academic summary in coherent paragraphs. Explain the central thesis, key arguments, evidence, and limitations. Do not invent facts.", input=transcript)
print(response.output_text)
