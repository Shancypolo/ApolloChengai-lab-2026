"""Unit tests for the interactive story loop."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import storyengine
from storyengine import ENDING_KEY, MAX_STORY_DECISIONS, StoryMemory, TokenUsage


# Free-text input stays inside the user-facing loop.
class UserInputTests(unittest.TestCase):
    """Check answer bounds, correction output, EOF, and the prompt text."""

    def test_read_user_answer_reprompts_for_invalid_input(self) -> None:
        errors = io.StringIO()
        with patch(
            "builtins.input",
            side_effect=["", "x" * 401, "x" * 400],
        ), contextlib.redirect_stderr(errors):
            answer = storyengine.read_user_answer()

        self.assertEqual(answer, "x" * 400)
        self.assertEqual(errors.getvalue(), "an error occurred\nan error occurred\n")

    def test_read_user_answer_returns_none_on_eof(self) -> None:
        with patch("builtins.input", side_effect=EOFError):
            self.assertIsNone(storyengine.read_user_answer())

    def test_prompt_asks_for_next_action_and_photo(self) -> None:
        self.assertEqual(
            storyengine.DECISION_PROMPT,
            "What will you do next, and what will you photograph?\n> ",
        )


# Opening, decisions, and chapters share one temporary session.
class StoryLoopTests(unittest.TestCase):
    """Check chapter flow, decision limits, and generic error output."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.opening_path = Path(self.temporary_directory.name) / "opening.txt"
        self.opening_path.write_text("The saved beginning.\n", encoding="utf-8")

    def test_opening_prints_and_eof_exits(self) -> None:
        output = io.StringIO()
        with patch.object(storyengine, "STARTING_STORY_PATH", self.opening_path), patch.object(
            storyengine, "load_memory", return_value=StoryMemory()
        ), patch.object(storyengine, "read_user_answer", return_value=None), contextlib.redirect_stdout(
            output
        ):
            status = storyengine.run_story()

        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), "The saved beginning.\n")

    def test_final_chapter_stops_loop(self) -> None:
        output = io.StringIO()
        final_memory = StoryMemory(state={ENDING_KEY: "drowning"}, step=1)
        usage = TokenUsage(
            requests=1,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=Decimal("0.000080"),
        )
        with patch.object(storyengine, "STARTING_STORY_PATH", self.opening_path), patch.object(
            storyengine, "load_memory", return_value=StoryMemory()
        ), patch.object(storyengine, "read_user_answer", return_value="end story"), patch.object(
            storyengine,
            "generate_story",
            return_value=("The final chapter.", final_memory, usage),
        ) as generator, contextlib.redirect_stdout(output):
            status = storyengine.run_story()

        self.assertEqual(status, 0)
        self.assertFalse(generator.call_args.kwargs["decision_limit_reached"])
        self.assertIn("The final chapter.", output.getvalue())
        self.assertIn("Output tokens: 50.", output.getvalue())
        self.assertIn("Estimated GPT-5.6 Luna (high) cost: $0.000080 USD", output.getvalue())
        self.assertNotIn("input 100", output.getvalue())
        self.assertNotIn("150 total", output.getvalue())

    def test_ninth_decision_is_final(self) -> None:
        output = io.StringIO()
        final_memory = StoryMemory(
            step=MAX_STORY_DECISIONS,
            state={ENDING_KEY: "leave_valley"},
        )
        usage = TokenUsage(requests=1, total_tokens=3)
        with patch.object(storyengine, "STARTING_STORY_PATH", self.opening_path), patch.object(
            storyengine,
            "load_memory",
            return_value=StoryMemory(step=MAX_STORY_DECISIONS - 1),
        ), patch.object(storyengine, "read_user_answer", return_value="He walks to the truck."), patch.object(
            storyengine,
            "generate_story",
            return_value=("The story ends.", final_memory, usage),
        ) as generator, contextlib.redirect_stdout(output):
            status = storyengine.run_story()

        self.assertEqual(status, 0)
        self.assertTrue(generator.call_args.kwargs["decision_limit_reached"])

    def test_main_shows_only_generic_error(self) -> None:
        errors = io.StringIO()
        with patch.object(
            storyengine, "run_story", side_effect=RuntimeError("sensitive error details")
        ), contextlib.redirect_stderr(errors):
            status = storyengine.main()

        self.assertEqual(status, 1)
        self.assertEqual(errors.getvalue(), "an error occurred\n")


if __name__ == "__main__":
    unittest.main()
