"""Unit tests for session memory and the single generation request."""

from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from storyengine import (
    ENDING_KEY,
    INITIAL_PHOTO_COUNT,
    MAX_MEMORY_CHARS,
    MAX_MEMORY_OPERATIONS,
    MAX_NEW_EVENTS,
    MAX_STORY_DECISIONS,
    PHOTO_COUNT_KEY,
    PROMPT_CACHE_KEY,
    MODEL,
    REASONING_SETTINGS,
    TEXT_SETTINGS,
    GenerationResult,
    MemoryDelta,
    MemorySet,
    StoryMemory,
    TokenUsage,
    apply_delta,
    build_instructions,
    format_memory,
    generate_story,
    load_memory,
    remaining_photo_count,
)


# Construct one structured model result for generation tests.
def make_result(
    story_text: str,
    *,
    memory: MemoryDelta | None = None,
    ending: str = "none",
    photo_taken: bool = False,
    end_request_detected: bool = False,
) -> GenerationResult:
    """Build a valid typed response with focused test defaults."""
    return GenerationResult(
        end_request_detected=end_request_detected,
        story_text=story_text,
        memory=memory or MemoryDelta(),
        ending=ending,
        photo_taken=photo_taken,
    )


# Read-only seed loading and fixed memory operations.
class MemoryTests(unittest.TestCase):
    """Check seed loading, canonical validation, and all-or-nothing updates."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.memory_path = Path(self.temporary_directory.name) / "story_memory.json"

    def test_load_missing_and_valid_seed(self) -> None:
        self.assertEqual(load_memory(self.memory_path), StoryMemory())
        seed = StoryMemory(
            step=3,
            facts={"world.place": "A small island."},
            events=["The bridge was inspected."],
        )
        self.memory_path.write_text(seed.model_dump_json(), encoding="utf-8")
        self.assertEqual(load_memory(self.memory_path), seed)

    def test_reject_malformed_seed_and_oversized_key(self) -> None:
        self.memory_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_memory(self.memory_path)

        self.memory_path.write_text(
            json.dumps({"version": 1, "step": 0, "rules": {"k" * 121: "Rule."}}),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            load_memory(self.memory_path)

    def test_seed_file_stays_read_only(self) -> None:
        seed = StoryMemory(facts={"world.setting": "The valley is on an island."})
        self.memory_path.write_text(seed.model_dump_json(), encoding="utf-8")
        original_bytes = self.memory_path.read_bytes()
        current_session = load_memory(self.memory_path)
        updated = apply_delta(current_session, MemoryDelta(events=["He reached town."]))
        self.assertEqual(self.memory_path.read_bytes(), original_bytes)
        self.assertEqual(load_memory(self.memory_path), seed)
        self.assertEqual(updated.step, 1)

    def test_apply_delta_and_skip_normalized_duplicate_events(self) -> None:
        memory = StoryMemory(
            events=["The bridge was inspected."],
            threads={"dam.gates": "Gates close tomorrow."},
        )
        delta = MemoryDelta(
            set=[MemorySet(section="thread", key="photo.choice", value="Not chosen.")],
            events=[" the BRIDGE was inspected. ", "He photographed the church."],
            resolve_threads=["dam.gates"],
        )
        updated = apply_delta(memory, delta)
        self.assertEqual(updated.events, ["The bridge was inspected.", "He photographed the church."])
        self.assertIn("photo.choice", updated.threads)
        self.assertNotIn("dam.gates", updated.threads)
        self.assertEqual(updated.step, 1)

    def test_reject_fact_changes_and_preserve_original_memory(self) -> None:
        memory = StoryMemory(facts={"world.setting": "An island."})
        original = memory.model_dump()
        delta = MemoryDelta(
            set=[MemorySet(section="fact", key="world.setting", value="A peninsula.")]
        )
        with self.assertRaises(ValueError):
            apply_delta(memory, delta)
        self.assertEqual(memory.model_dump(), original)

    def test_reject_invalid_and_conflicting_mutations(self) -> None:
        memory = StoryMemory(threads={"thread.open": "Still unresolved."})
        with self.assertRaises(ValidationError):
            MemorySet(section="state", key="", value="Present.")

        invalid_updates = (
            MemoryDelta(
                set=[MemorySet(section="state", key="x", value="y" * 1_001)]
            ),
            MemoryDelta(
                set=[
                    MemorySet(section="state", key="same.key", value="One."),
                    MemorySet(section="state", key="same.key", value="Two."),
                ]
            ),
            MemoryDelta(resolve_threads=["thread.unknown"]),
            MemoryDelta(
                set=[MemorySet(section="thread", key="thread.open", value="Changed.")],
                resolve_threads=["thread.open"],
            ),
        )
        for delta in invalid_updates:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                apply_delta(memory, delta)

    def test_reject_operation_limits_and_application_owned_state(self) -> None:
        too_many_sets = [
            MemorySet(section="state", key=f"state.item{index}", value="Present.")
            for index in range(MAX_MEMORY_OPERATIONS + 1)
        ]
        with self.assertRaises(ValueError):
            apply_delta(StoryMemory(), MemoryDelta(set=too_many_sets))
        with self.assertRaises(ValueError):
            apply_delta(
                StoryMemory(),
                MemoryDelta(events=[f"Event {index}." for index in range(MAX_NEW_EVENTS + 1)]),
            )
        with self.assertRaises(ValueError):
            apply_delta(
                StoryMemory(),
                MemoryDelta(
                    set=[MemorySet(section="state", key=PHOTO_COUNT_KEY, value="4")]
                ),
            )

    def test_format_and_photo_count(self) -> None:
        formatted = format_memory(StoryMemory(facts={"world.place": "A valley."}))
        self.assertLess(len(formatted), MAX_MEMORY_CHARS)
        self.assertEqual(remaining_photo_count(StoryMemory()), INITIAL_PHOTO_COUNT)
        self.assertEqual(
            remaining_photo_count(StoryMemory(state={PHOTO_COUNT_KEY: "4"})), 4
        )
        with self.assertRaises(ValueError):
            remaining_photo_count(StoryMemory(state={PHOTO_COUNT_KEY: "6"}))


# Structured generation updates one temporary session without writing the seed.
class GenerationTests(unittest.TestCase):
    """Check one-call generation, turn endings, and application-owned state."""

    def setUp(self) -> None:
        self.chapter = (
            "He chose the bridge. The river moved softly below the worn boards. "
            "A fisherman watched from the far bank. Then the church bell rang, "
            "and something answered beneath the bridge."
        )
        self.client = Mock()

    def use_result(self, result: GenerationResult) -> None:
        usage = SimpleNamespace(
            input_tokens=1_000,
            input_tokens_details=SimpleNamespace(
                cached_tokens=200,
                cache_write_tokens=100,
            ),
            output_tokens=400,
            output_tokens_details=SimpleNamespace(reasoning_tokens=250),
            total_tokens=1_400,
        )
        self.client.responses.parse.return_value = SimpleNamespace(
            output_parsed=result,
            usage=usage,
        )

    def run_generation(
        self,
        user_answer: str,
        session_memory: StoryMemory,
        *,
        decision_limit_reached: bool = False,
    ) -> tuple[str, StoryMemory, TokenUsage]:
        """Keep every generation test on the mocked API client."""
        with patch("storyengine.OpenAI", return_value=self.client):
            return generate_story(
                user_answer,
                session_memory,
                decision_limit_reached=decision_limit_reached,
            )

    def test_instruction_contract(self) -> None:
        ongoing = build_instructions(
            decision_number=1,
            decision_limit_reached=False,
        ).casefold()
        at_limit = build_instructions(
            decision_number=MAX_STORY_DECISIONS,
            decision_limit_reached=True,
        ).casefold()
        self.assertIn("4–9 sentences", ongoing)
        self.assertIn("unresolved cliffhanger", ongoing)
        self.assertIn("at least", ongoing)
        self.assertIn("this response must be final", at_limit)

    def test_one_api_call_and_session_update(self) -> None:
        self.use_result(
            make_result(
                self.chapter,
                memory=MemoryDelta(events=["He reached the old bridge."]),
            )
        )
        with patch("storyengine.OpenAI", return_value=self.client) as client_factory:
            text, updated, usage = generate_story("He walks to the bridge.", StoryMemory())

        client_factory.assert_called_once_with()
        self.client.responses.parse.assert_called_once()
        request = self.client.responses.parse.call_args.kwargs
        self.assertEqual(request["model"], MODEL)
        self.assertEqual(request["reasoning"], REASONING_SETTINGS)
        self.assertEqual(request["text"], TEXT_SETTINGS)
        self.assertEqual(request["prompt_cache_key"], PROMPT_CACHE_KEY)
        self.assertFalse(request["store"])
        self.assertNotIn("tools", request)
        self.assertEqual(json.loads(request["input"])["user_decision"], "He walks to the bridge.")
        self.assertEqual(text, self.chapter)
        self.assertEqual(updated.step, 1)
        self.assertEqual(updated.events, ["He reached the old bridge."])
        self.assertEqual(usage.total_tokens, 1_400)
        self.assertEqual(usage.reasoning_tokens, 250)
        self.assertEqual(usage.estimated_cost_usd, Decimal("0.000649"))

    def test_final_chapter_and_decision_limit(self) -> None:
        self.use_result(
            make_result(
                "He walked to the ridge. The river moved below him. "
                "He carried the camera toward the coast. The valley faded behind him. "
                "At sunset, he had left the valley for good.",
                ending="leave_valley",
                end_request_detected=True,
            )
        )
        _, updated, _ = self.run_generation("Please finish this story now.", StoryMemory())
        self.assertEqual(updated.state[ENDING_KEY], "leave_valley")
        self.assertEqual(updated.step, 1)

        self.use_result(
            make_result(self.chapter, ending="leave_valley")
        )
        _, final_memory, _ = self.run_generation(
            "He walks toward the truck.",
            StoryMemory(step=MAX_STORY_DECISIONS - 1),
            decision_limit_reached=True,
        )
        self.assertEqual(final_memory.state[ENDING_KEY], "leave_valley")
        self.assertEqual(final_memory.step, MAX_STORY_DECISIONS)

    def test_photo_decrements_counter_and_rejects_spent_film(self) -> None:
        self.use_result(make_result(self.chapter, photo_taken=True))
        _, updated, _ = self.run_generation(
            "He photographs the bridge.",
            StoryMemory(state={PHOTO_COUNT_KEY: "5"}),
        )
        self.assertEqual(remaining_photo_count(updated), 4)

        with self.assertRaises(ValueError):
            self.run_generation(
                "He photographs the church.",
                StoryMemory(state={PHOTO_COUNT_KEY: "0"}),
            )

    def test_rejected_response_keeps_session_memory_unchanged(self) -> None:
        memory = StoryMemory(step=2)
        original = memory.model_dump()
        self.use_result(
            make_result(
                self.chapter,
                memory=MemoryDelta(events=["He reached the bridge."]),
                ending="leave_valley",
            )
        )
        with self.assertRaises(ValueError):
            self.run_generation("He walks to the bridge.", memory)
        self.assertEqual(memory.model_dump(), original)

    def test_completed_story_and_oversized_memory_stop_before_api(self) -> None:
        with patch("storyengine.OpenAI") as client:
            with self.assertRaises(ValueError):
                generate_story(
                    "Continue.", StoryMemory(state={ENDING_KEY: "leave_valley"})
                )
            oversized = StoryMemory(events=["x" * 999 for _ in range(100)])
            with self.assertRaises(ValueError):
                generate_story("Continue.", oversized)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
