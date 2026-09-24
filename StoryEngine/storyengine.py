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
    ENDING_KEY,
    MAX_STORY_DECISIONS,
    MAX_USER_ANSWER_CHARS,
    MEMORY_PATH,
    ConfigurationError,
    UnrealisticDecisionError,
    StoryAlreadyEndedError,
    StoryMemory,
    StoryMemoryError,
    ERROR_EMPTY_ANSWER,
    ERROR_OVERSIZED_ANSWER,
    generate_story,
    load_memory,
    validate_openai_sdk_version,
    verify_tls_imports,
)


# CLI constants: parser, prompt, security checks, terminal output.
CLI_PROGRAM_NAME = "storyengine"
CLI_DESCRIPTION = "Continue the valley story with open-ended decisions."
CLI_EPILOG_TEMPLATE = (
    "Run with OPENAI_API_KEY set. Enter a free-text decision of up to {character_limit} characters."
)
CLI_ERROR_TEMPLATE = "Error: {message}"
CLI_GENERATING_STATUS = "Generating next chapter…"
CLI_COMPLETE_STATUS = "Story complete."
CLI_ENDING_EXISTS = "This story has already ended."
CLI_OPENING_READ_ERROR = "The starting story file could not be read."
CLI_INTERRUPT_MESSAGE = "\nStory session interrupted; in-memory story state will be discarded."
CLI_MALICIOUS_INPUT_ERROR = (
    "StoryEngine stopped because input attempted to override safety rules or reveal hidden instructions."
)
CLI_NEWLINE = "\n"
CLI_UTF8_ENCODING = "utf-8"
CLI_REPLACE_ERRORS = "replace"
CLI_ENCODING_SETTING = "encoding"
CLI_ERRORS_SETTING = "errors"
CLI_RECONFIGURE_METHOD = "reconfigure"
CLI_FORMAT_CONTROL_CATEGORY = "Cf"
CLI_SECURITY_NORMALIZATION = "NFKC"
CLI_SPACE = " "
CLI_EMPTY_TEXT = ""
CLI_SECURITY_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130
STARTING_STORY_PATH = Path(__file__).resolve().with_name("opening.txt")
DECISION_PROMPT = (
    "What will you do next, and what will you photograph?\n> "
)
BASE64_CANDIDATE_PATTERN = re.compile(r"[A-Za-z0-9_+/=-]{16,}")
BASE64_PADDING_CHARACTER = "="
BASE64_ALTERNATE_CHARACTERS = b"-_"

# Prompt-injection patterns: reject direct overrides before API access.
MALICIOUS_PROMPT_PATTERNS = (
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
COMPACT_MALICIOUS_MARKERS = (
    "ignoreallpreviousinstructions",
    "ignoreallpriorinstructions",
    "revealyoursystemprompt",
    "showyoursystemprompt",
    "developerinstructions",
    "bypassallsafetymeasures",
    "overrideyoursecuritysettings",
)
# Typo corrections: normalize common prompt-injection variants.
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


# User input error: blank or oversized answer; prompt again.
class UserAnswerError(ValueError):
    """Raised for blank or oversized story answers."""


# Prompt-injection error: stop before network access.
class MaliciousPromptError(ValueError):
    """Raised when input attempts to override instructions or extract prompts."""


# Security normalization: Unicode, format controls, separators, known typos.
def normalize_security_text(user_text: str) -> str:
    """Normalize Unicode, separators, and known typos for injection screening."""
    normalized_text = unicodedata.normalize(
        CLI_SECURITY_NORMALIZATION,
        user_text,
    ).casefold()
    normalized_text = "".join(
        unicode_character
        for unicode_character in normalized_text
        if unicodedata.category(unicode_character) != CLI_FORMAT_CONTROL_CATEGORY
    )
    normalized_text = CLI_SECURITY_SEPARATOR_PATTERN.sub(CLI_SPACE, normalized_text)
    normalized_words = [
        TYPOGLYCEMIA_CORRECTIONS.get(security_word, security_word)
        for security_word in normalized_text.split()
    ]
    return CLI_SPACE.join(normalized_words)


# Prompt-injection gate: direct, compact, encoded, and typo variants.
def is_malicious_prompt(user_answer: str) -> bool:
    """Detect direct prompt overrides and simple encoded variants before API use."""
    normalized_answer = normalize_security_text(user_answer)
    compact_answer = normalized_answer.replace(CLI_SPACE, CLI_EMPTY_TEXT)
    if any(
        re.search(injection_pattern, normalized_answer)
        for injection_pattern in MALICIOUS_PROMPT_PATTERNS
    ):
        return True

    if any(
        injection_marker in compact_answer
        for injection_marker in COMPACT_MALICIOUS_MARKERS
    ):
        return True

    for encoded_candidate in BASE64_CANDIDATE_PATTERN.findall(user_answer):
        try:
            padding_text = BASE64_PADDING_CHARACTER * (-len(encoded_candidate) % 4)
            padded_candidate = encoded_candidate + padding_text
            decoded_bytes = base64.b64decode(
                padded_candidate,
                altchars=BASE64_ALTERNATE_CHARACTERS,
                validate=True,
            )
            decoded_text = decoded_bytes.decode(CLI_UTF8_ENCODING)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        normalized_decoded_text = normalize_security_text(decoded_text)
        if any(
            re.search(injection_pattern, normalized_decoded_text)
            for injection_pattern in MALICIOUS_PROMPT_PATTERNS
        ):
            return True

    return False


# Answer validation: reject malicious, blank, or oversized input before API use.
def validate_user_answer(user_answer: str) -> str:
    """Reject malicious, blank, or over-limit input and return trimmed user text."""
    if is_malicious_prompt(user_answer):
        raise MaliciousPromptError(CLI_MALICIOUS_INPUT_ERROR)
    if not user_answer.strip():
        raise UserAnswerError(ERROR_EMPTY_ANSWER)
    if len(user_answer) > MAX_USER_ANSWER_CHARS:
        raise UserAnswerError(ERROR_OVERSIZED_ANSWER)
    return user_answer.strip()


# Input loop: one open response; reprompt blank or oversized answers.
def read_user_answer() -> str | None:
    """Read one free-text decision and photo subject.

    Reprompt blank or oversized answers. Return None on EOF for clean loop exit.
    """
    while True:
        try:
            user_answer = input(DECISION_PROMPT)
        except EOFError:
            return None

        try:
            return validate_user_answer(user_answer)
        except UserAnswerError as answer_error:
            print(CLI_ERROR_TEMPLATE.format(message=answer_error), file=sys.stderr)


# Opening: print supplied text verbatim at session start.
def print_opening() -> None:
    """Write the supplied opening unchanged to stdout for each new session."""
    try:
        opening_text = STARTING_STORY_PATH.read_text(encoding=CLI_UTF8_ENCODING)
    except OSError as file_error:
        raise StoryMemoryError(CLI_OPENING_READ_ERROR) from file_error
    sys.stdout.write(opening_text)
    if not opening_text.endswith(CLI_NEWLINE):
        sys.stdout.write(CLI_NEWLINE)


# Terminal encoding: request UTF-8 on Windows and macOS.
def configure_terminal_encoding() -> None:
    """Request UTF-8 streams where the current terminal supports reconfiguration."""
    for terminal_stream in (sys.stdin, sys.stdout, sys.stderr):
        configure_encoding = getattr(terminal_stream, CLI_RECONFIGURE_METHOD, None)
        if callable(configure_encoding):
            configure_encoding(
                **{
                    CLI_ENCODING_SETTING: CLI_UTF8_ENCODING,
                    CLI_ERRORS_SETTING: CLI_REPLACE_ERRORS,
                }
            )


# Story loop: continue until ending, EOF, or safe failure.
def run_story() -> int:
    """Run one story session from read-only canon.

    Print opening and accepted chapters; return conventional status on ending,
    EOF, or handled failure. Generated memory remains in process RAM.
    """
    session_memory = load_memory(MEMORY_PATH)
    if session_memory.state.get(ENDING_KEY):
        print(CLI_ENDING_EXISTS, file=sys.stderr)
        return EXIT_SUCCESS

    print_opening()

    while True:
        user_answer = read_user_answer()
        if user_answer is None:
            return EXIT_SUCCESS
        decision_limit_reached = session_memory.step + 1 >= MAX_STORY_DECISIONS
        print(CLI_GENERATING_STATUS, file=sys.stderr, flush=True)
        try:
            generated_chapter, session_memory = generate_story(
                user_answer,
                session_memory,
                decision_limit_reached=decision_limit_reached,
            )
        except UnrealisticDecisionError as decision_error:
            print(CLI_ERROR_TEMPLATE.format(message=decision_error), file=sys.stderr)
            continue

        print(generated_chapter, file=sys.stdout, flush=True)
        if session_memory.state.get(ENDING_KEY):
            print(CLI_COMPLETE_STATUS, file=sys.stderr)
            return EXIT_SUCCESS


# CLI entry point: help, runtime checks, conventional exit codes.
def main(command_arguments: list[str] | None = None) -> int:
    """Provide CLI entry point for direct use and module execution.

    Parse help, verify SDK/TLS setup, and map handled failures to exit codes.
    """
    configure_terminal_encoding()
    argument_parser = argparse.ArgumentParser(
        prog=CLI_PROGRAM_NAME,
        description=CLI_DESCRIPTION,
        epilog=CLI_EPILOG_TEMPLATE.format(
            character_limit=MAX_USER_ANSWER_CHARS
        ),
    )
    argument_parser.parse_args(command_arguments)

    try:
        verify_tls_imports()
        validate_openai_sdk_version()
        return run_story()
    except MaliciousPromptError as injection_error:
        print(CLI_ERROR_TEMPLATE.format(message=injection_error), file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR
    except ConfigurationError as configuration_error:
        print(CLI_ERROR_TEMPLATE.format(message=configuration_error), file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR
    except StoryAlreadyEndedError as ended_story_error:
        print(CLI_ERROR_TEMPLATE.format(message=ended_story_error), file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR
    except StoryMemoryError as story_error:
        print(CLI_ERROR_TEMPLATE.format(message=story_error), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except KeyboardInterrupt:
        print(CLI_INTERRUPT_MESSAGE, file=sys.stderr)
        return EXIT_INTERRUPTED


# Module entry point: run CLI only when launched as a program.
if __name__ == "__main__":
    raise SystemExit(main())
