
import os, certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
from pytubefix import YouTube
from openai import OpenAI

video_id = input("Video ID: ").strip()
captions = YouTube(f"https://www.youtube.com/watch?v={video_id}").captions
caption = captions.get("en") or captions.get("a.en")
if not caption: raise SystemExit("No English captions available.")
transcript = caption.generate_txt_captions()
response = OpenAI().responses.create(model="gpt-5.6-luna", reasoning={"effort": "high"}, tools=[], instructions="Write a concise academic summary in coherent paragraphs. Explain the central thesis, key arguments, evidence, and limitations. Do not invent facts.", input=transcript)
print(response.output_text)
