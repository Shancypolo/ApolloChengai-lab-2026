"""Run one clearly labeled live YouTube and OpenAI diagnostic request."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


APP_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIRECTORY))

from summary_service import MODEL_NAME, REASONING_EFFORT, label_video_titles, summarize_video
from usage_accounting import cost_units
from youtube_source import SourceError, fetch_english_transcript, fetch_source


PLAYLIST_ID = "PLVANSOs5ny50"
VIDEO_ID = "GmBG-26_Izw"
SYNTHETIC_TRANSCRIPT = (
    "A lecturer argues that strong research separates measured evidence from "
    "conjecture. The speaker says small samples limit broad conclusions."
)


def main() -> int:
    """Check source access or send one synthetic GPT contract request."""
    parser = argparse.ArgumentParser(description="Run a quota-bearing PageOne live diagnostic.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--ai-only", action="store_true", help="Send one synthetic summary request without YouTube access.")
    modes.add_argument("--topics-only", action="store_true", help="Send synthetic titles only for one topic-label request.")
    modes.add_argument("--source-only", action="store_true", help="List the sample playlist without captions or OpenAI calls.")
    arguments = parser.parse_args()
    try:
        if arguments.source_only:
            playlist = fetch_source("playlist", PLAYLIST_ID)
            print(f"YouTube source check: {len(playlist['videos'])} valid titles; {playlist['omitted_video_entries']} unavailable entries skipped.")
            return 0
        if not os.environ.get("OPENAI_API_KEY", "").strip():
            print("Skipped: OPENAI_API_KEY is not set; no live requests were made.")
            return 2
        if arguments.topics_only:
            titles = ["The role of evidence in modern research", "Video 2"]
            recorded_usage = []
            topics = label_video_titles(titles, usage_callback=recorded_usage.append)
            usage = recorded_usage[0] if recorded_usage else None
            cost = f"known_cost_usd={cost_units(usage) / 100_000_000:.8f}" if usage and usage.get("cached_detail_complete") else "known_cost_usd=unavailable"
            print(f"OpenAI topic check: success; model={MODEL_NAME}; reasoning={REASONING_EFFORT}; labels={len(topics)}; placeholder_is_other={topics[1] == 'Other'}; {cost}; tokens={usage['total_tokens'] if usage else 'unknown'}.")
            return 0
        if arguments.ai_only:
            title = "Synthetic PageOne API contract check"
            transcript = SYNTHETIC_TRANSCRIPT
            print("OpenAI live check: synthetic transcript only; one API request will be sent.")
        else:
            playlist = fetch_source("playlist", PLAYLIST_ID)
            print(f"YouTube playlist: {len(playlist['videos'])} valid video titles; {playlist['omitted_video_entries']} unavailable entries skipped.")
            transcript = fetch_english_transcript(VIDEO_ID)
            title = f"Sample video {VIDEO_ID}"
            print(f"English captions: available, {len(transcript)} characters; transcript not printed or saved.")
        recorded_usage = []
        result = summarize_video(
            title,
            transcript,
            "Write a concise academic summary. Explain the main claim and evidence.",
            usage_callback=recorded_usage.append,
        )
        usage = recorded_usage[0] if recorded_usage else None
        if usage and usage.get("cached_detail_complete"):
            cost = f"known_cost_usd={cost_units(usage) / 100_000_000:.8f}"
        else:
            cost = "known_cost_usd=unavailable"
        print(
            f"OpenAI Responses: success; model={MODEL_NAME}; reasoning={REASONING_EFFORT}; "
            f"summary_characters={len(result['summary'])}; {cost}; "
            f"input_tokens={usage['input_tokens'] if usage else 'unknown'}; "
            f"cached_tokens={usage['cached_tokens'] if usage else 'unknown'}; "
            f"output_tokens={usage['output_tokens'] if usage else 'unknown'}; "
            f"reasoning_tokens={usage['reasoning_tokens'] if usage else 'unknown'}."
        )
        return 0
    except SourceError as error:
        print(f"Live source diagnostic failed: {error}")
        return 1
    except Exception as error:
        print(f"Live API diagnostic failed: {type(error).__name__}; response details were not printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
