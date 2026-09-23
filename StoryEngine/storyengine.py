"""Interactive command-line entry point for StoryEngine."""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import sys
import unicodedata
from pathlib import Path

from story_memory import (
    MAX_USER_ANSWER_CHARS,
    MEMORY_PATH,
    ConfigurationError,
    StoryAlreadyEndedError,
    StoryMemory,
    StoryMemoryError,
    contains_fantastical_action,
    generate_story,
    load_memory,
)


# Keep the interaction and story limits visible to new contributors.
MAX_STORY_DECISIONS = 9
STARTING_STORY_PATH = Path(__file__).resolve().with_name("opening.txt")
DECISION_PROMPT = (
    "What will you do next, and what will you photograph?\n> "
)
BASE64_CANDIDATE_PATTERN = re.compile(r"[A-Za-z0-9_+/=-]{16,}")

# Correct documented typoglycemia variants before scanning for direct attacks.
TYPOGLYCEMIA_CORRECTIONS = {
    "ignroe": "ignore",
    "prevoius": "previous",
    "systme": "system",
    "revael": "reveal",
    "bpyass": "bypass",
    "measueres": "measures",
    "ovverride": "override",
    "securty": "security",
    "immediatley": "immediately",
}


# Describe an invalid user answer that should be corrected without ending the session.
class UserAnswerError(ValueError):
    """Raised for blank or oversized story answers."""


# Stop clearly malicious requests before any network call is made.
class MaliciousPromptError(ValueError):
    """Raised when input attempts to override instructions or extract prompts."""


# Explain that fantastical actions are outside this story's realistic world.
class UnrealisticDecisionError(UserAnswerError):
    """Raised when a story decision asks for an impossible or supernatural action."""


# Convert Unicode and spacing variants into comparable plain text.
def normalize_security_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    words = [TYPOGLYCEMIA_CORRECTIONS.get(word, word) for word in normalized.split()]
    return " ".join(words)


# Detect direct prompt overrides, instruction extraction, and common obfuscations.
def is_malicious_prompt(value: str) -> bool:
    normalized = normalize_security_text(value)
    compact = normalized.replace(" ", "")
    patterns = (
        r"\bignore\s+(?:all\s+)?(?:previous|prior|system|developer)\s+instructions?\b",
        r"\b(?:reveal|show|print|repeat|quote|output|dump|tell)\b"
        r".{0,50}\b(?:system|developer|hidden|internal|your)\b"
        r".{0,30}\b(?:prompt|instructions?)\b",
        r"\bdeveloper\s+mode\b",
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:safety|security)\s+"
        r"(?:rules|measures|restrictions|guardrails|settings)\b",
        r"\bbypass\b.{0,30}\b(?:all\s+)?(?:safety|security)\b"
        r".{0,20}\b(?:measures|checks|rules|restrictions|safeguards|guardrails|settings)\b",
        r"\bbypass\s+(?:all\s+)?(?:guardrails|restrictions|rules)\b",
        r"\b(?:not\s+bound|ignore\s+the)\b.{0,40}\b(?:restrictions|safeguards|safety)\b",
        r"\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b"
        r".{0,40}\b(?:system|developer|unrestricted|unfiltered)\b",
    )
    if any(re.search(pattern, normalized) for pattern in patterns):
        return True

    compact_markers = (
        "ignoreallpreviousinstructions",
        "ignoreallpriorinstructions",
        "revealyoursystemprompt",
        "showyoursystemprompt",
        "developerinstructions",
        "bypassallsafetymeasures",
        "overrideyoursecuritysettings",
    )
    if any(marker in compact for marker in compact_markers):
        return True

    for candidate in BASE64_CANDIDATE_PATTERN.findall(value):
        try:
            padded = candidate + ("=" * (-len(candidate) % 4))
            decoded = base64.b64decode(padded, altchars=b"-_", validate=True)
            decoded_text = decoded.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        decoded_normalized = normalize_security_text(decoded_text)
        if any(re.search(pattern, decoded_normalized) for pattern in patterns):
            return True

    return False


# Recognize common plain-language requests to end the story next turn.
def is_end_request(value: str) -> bool:
    normalized = normalize_security_text(value)
    for contraction, expanded in (
        ("don t", "dont"),
        ("doesn t", "doesnt"),
        ("didn t", "didnt"),
        ("can t", "cant"),
        ("won t", "wont"),
        ("wouldn t", "wouldnt"),
        ("shouldn t", "shouldnt"),
        ("i m ", "im "),
    ):
        normalized = normalized.replace(contraction, expanded)
    matches = list(
        re.finditer(
            r"\b(?:end|finish|conclude|wrap up)\s+(?:(?:the|this|our)\s+)?story\b"
            r"|\bend\s+of\s+(?:the\s+)?story\b",
            normalized,
        )
    )
    for match in matches:
        preceding_words = normalized[: match.start()].split()[-3:]
        if any(
            word in {"not", "never", "dont", "doesnt", "didnt", "cant", "wont", "wouldnt", "shouldnt"}
            for word in preceding_words
        ):
            continue
        return True

    additional_end_patterns = (
        r"\b(?:i am done|im done|i want to stop|please stop|quit)\b.{0,30}\bstory\b",
        r"\b(?:story|ending)\b.{0,20}\b(?:is over|is finished|is done)\b",
    )
    return any(re.search(pattern, normalized) for pattern in additional_end_patterns)


# Reject unsafe and oversized answers, while allowing empty lines to be re-entered.
def validate_user_answer(value: str) -> str:
    if is_malicious_prompt(value):
        raise MaliciousPromptError(
            "StoryEngine stopped because input attempted to override safety rules or reveal hidden instructions."
        )
    if not value.strip():
        raise UserAnswerError("Enter a story decision before continuing.")
    if len(value) > MAX_USER_ANSWER_CHARS:
        raise UserAnswerError(
            f"Story answers must be {MAX_USER_ANSWER_CHARS} characters or fewer."
        )
    if contains_fantastical_action(value, allow_reported_belief=True):
        raise UnrealisticDecisionError(
            "Keep actions physically possible; characters may discuss folklore, but fantasy events are filtered out."
        )
    return value.strip()


# Read one open-ended story decision, reprompting for blank or oversized answers.
def read_user_answer() -> str | None:
    while True:
        try:
            answer = input(DECISION_PROMPT)
        except EOFError:
            return None

        try:
            return validate_user_answer(answer)
        except UserAnswerError as error:
            print(f"Error: {error}", file=sys.stderr)


# Decide whether this answer should produce the final chapter immediately.
def should_end_story(answer: str, memory: StoryMemory) -> bool:
    return is_end_request(answer) or memory.step + 1 >= MAX_STORY_DECISIONS


# Read and print the supplied opening verbatim at the start of every session.
def print_opening() -> None:
    try:
        opening = STARTING_STORY_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise StoryMemoryError("The starting story file could not be read.") from error
    sys.stdout.write(opening)
    if not opening.endswith("\n"):
        sys.stdout.write("\n")


# Use UTF-8 on Windows and macOS while leaving test streams untouched.
def configure_terminal_encoding() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


# Run the interactive story until completion, EOF, or a safe failure.
def run_story() -> int:
    memory = load_memory(MEMORY_PATH)
    if memory.state.get("story.ending"):
        print("This story has already ended.", file=sys.stderr)
        return 0

    print_opening()

    while True:
        answer = read_user_answer()
        if answer is None:
            return 0
        final_generation = should_end_story(answer, memory)
        print("Generating next chapter…", file=sys.stderr, flush=True)
        story_text, memory = generate_story(
            answer,
            memory,
            final_generation=final_generation,
        )
        print(story_text, file=sys.stdout, flush=True)
        if final_generation:
            print("Story complete.", file=sys.stderr)
            return 0


# Provide standard help and concise errors with conventional process exit codes.
def main(arguments: list[str] | None = None) -> int:
    configure_terminal_encoding()
    parser = argparse.ArgumentParser(
        prog="storyengine",
        description="Continue the valley story with open-ended decisions.",
        epilog="Run with OPENAI_API_KEY set. Enter a free-text decision of up to 400 characters.",
    )
    parser.parse_args(arguments)

    try:
        return run_story()
    except MaliciousPromptError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except ConfigurationError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except StoryAlreadyEndedError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except StoryMemoryError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStory session interrupted; in-memory story state will be discarded.", file=sys.stderr)
        return 130


# Execute the CLI only when this module is launched as a program.
if __name__ == "__main__":
    raise SystemExit(main())
