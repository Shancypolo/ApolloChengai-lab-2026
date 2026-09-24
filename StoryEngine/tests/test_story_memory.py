"""Unit tests for canonical memory and structured generation validation."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from openai import APIConnectionError

from story_memory import (
    API_MAX_RETRIES,
    API_TIMEOUT_SECONDS,
    MAX_STORY_DECISIONS,
    MIN_STORY_DECISIONS,
    MIN_STORY_SENTENCES,
    MAX_STORY_SENTENCES,
    MAX_MEMORY_CHARS,
    MAX_MEMORY_OPERATIONS,
    MAX_NEW_EVENTS,
    PROMPT_CACHE_KEY,
    MODEL,
    REASONING_EFFORT,
    ENDING_KEY,
    PHOTO_COUNT_KEY,
    ConfigurationError,
    GenerationError,
    GenerationResult,
    UnrealisticDecisionError,
    MemoryDelta,
    MemorySet,
    MemoryValidationError,
    StoryMemory,
    StoryMemoryError,
    StoryAlreadyEndedError,
    apply_delta,
    build_instructions,
    format_memory,
    generate_story,
    load_memory,
    remaining_photo_count,
    validate_memory_size,
    verify_tls_imports,
)


# Construct a minimal valid response for API seam tests.
def make_result(
    story_text: str,
    *,
    memory: MemoryDelta | None = None,
    ending: str = "none",
    photo_taken: bool = False,
    decision_is_realistic: bool = True,
    end_request_detected: bool = False,
    sentence_count: int = 5,
    story_contract_passed: bool = True,
) -> GenerationResult:
    return GenerationResult(
        decision_is_realistic=decision_is_realistic,
        end_request_detected=end_request_detected,
        sentence_count=sentence_count,
        story_contract_passed=story_contract_passed,
        story_text=story_text,
        memory=memory or MemoryDelta(),
        ending=ending,
        photo_taken=photo_taken,
    )


# Verify certifi's bundle and detect whether optional HTTPX2 imports correctly.
class RuntimeImportTests(unittest.TestCase):
    # The supported SDK works without HTTPX2, while an installed HTTPX2 must import.
    def test_tls_import_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle_path = Path(directory) / "cacert.pem"
            bundle_path.write_text("test CA bundle", encoding="utf-8")
            fake_certifi = SimpleNamespace(where=lambda: str(bundle_path))

            for httpx2_module, expected_version in (
                (None, None),
                (SimpleNamespace(__version__="test-version"), "test-version"),
            ):
                module_overrides = {"certifi": fake_certifi, "httpx2": httpx2_module}
                with patch.dict(sys.modules, module_overrides), self.subTest(
                    expected_version=expected_version
                ):
                    certificate_bundle, httpx2_version = verify_tls_imports()
                self.assertEqual(certificate_bundle, str(bundle_path))
                self.assertEqual(httpx2_version, expected_version)

    # A missing certificate bundle stops startup with setup guidance.
    def test_missing_certificate_bundle_is_rejected(self) -> None:
        fake_certifi = SimpleNamespace(where=lambda: "missing-cacert.pem")
        with patch.dict(sys.modules, {"certifi": fake_certifi, "httpx2": None}):
            with self.assertRaisesRegex(ConfigurationError, "certificate bundle is missing"):
                verify_tls_imports()


# Test that the seed file is read-only and each process receives a fresh canon copy.
class MemoryFileTests(unittest.TestCase):
    # Create a temporary memory path for each file operation test.
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.memory_path = Path(self.temporary_directory.name) / "story_memory.json"

    # A missing file creates the initial in-memory schema.
    def test_load_missing_file(self) -> None:
        memory = load_memory(self.memory_path)
        self.assertEqual(memory.version, 1)
        self.assertEqual(memory.step, 0)
        self.assertEqual(memory.rules, {})

    # A valid JSON file loads all categories with strict types.
    def test_load_valid_file(self) -> None:
        expected = StoryMemory(
            step=3,
            facts={"world.place": "A small island."},
            events=["The bridge was inspected."],
        )
        self.memory_path.write_text(expected.model_dump_json(), encoding="utf-8")
        self.assertEqual(load_memory(self.memory_path), expected)

    # Malformed JSON and invalid canonical keys fail without resetting memory.
    def test_reject_malformed_memory(self) -> None:
        self.memory_path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(MemoryValidationError):
            load_memory(self.memory_path)

    # Invalid persisted keys are rejected after schema parsing.
    def test_reject_invalid_key_in_file(self) -> None:
        self.memory_path.write_text(
            json.dumps({"version": 1, "step": 0, "rules": {"Bad Key": "rule"}}),
            encoding="utf-8",
        )
        with self.assertRaises(MemoryValidationError):
            load_memory(self.memory_path)

    # Changes to a loaded object remain in memory and never rewrite the seed file.
    def test_seed_file_is_read_only(self) -> None:
        seed = StoryMemory(facts={"world.setting": "The valley is on an island."})
        self.memory_path.write_text(seed.model_dump_json(), encoding="utf-8")
        original_bytes = self.memory_path.read_bytes()
        current_session = load_memory(self.memory_path)
        current_session.step = 3
        current_session.state["camera.exposures_remaining"] = "Four photographs remain."
        self.assertEqual(self.memory_path.read_bytes(), original_bytes)
        self.assertEqual(load_memory(self.memory_path), seed)


# Test fixed mutation operations, limits, and canon protection.
class MemoryDeltaTests(unittest.TestCase):
    # A combined delta updates state, creates a thread, resolves an old thread, and appends events.
    def test_apply_delta_operations_and_duplicate_events(self) -> None:
        memory = StoryMemory(
            state={"camera.remaining": "Five exposures."},
            events=["The bridge was inspected."],
            threads={"dam.gates": "Gates close tomorrow."},
        )
        delta = MemoryDelta(
            set=[
                MemorySet(section="state", key="camera.remaining", value="Four exposures."),
                MemorySet(section="thread", key="photo.choice", value="He has not chosen a subject."),
            ],
            events=[" the BRIDGE was inspected. ", "He photographed the church."],
            resolve_threads=["dam.gates"],
        )
        updated = apply_delta(memory, delta)
        self.assertEqual(updated.state["camera.remaining"], "Four exposures.")
        self.assertIn("photo.choice", updated.threads)
        self.assertNotIn("dam.gates", updated.threads)
        self.assertEqual(updated.events, ["The bridge was inspected.", "He photographed the church."])
        self.assertEqual(updated.step, 1)

    # New rules and facts are allowed, but existing canonical values need retcon permission.
    def test_rule_and_fact_retcon_protection(self) -> None:
        memory = StoryMemory(
            rules={"story.silence": "He never speaks."},
            facts={"world.setting": "The valley is on an island."},
        )
        with self.assertRaises(MemoryValidationError):
            apply_delta(
                memory,
                MemoryDelta(
                    set=[MemorySet(section="rule", key="story.silence", value="He speaks.")]
                ),
            )
        updated = apply_delta(
            memory,
            MemoryDelta(
                set=[
                    MemorySet(section="rule", key="story.silence", value="He speaks."),
                    MemorySet(section="fact", key="world.setting", value="The valley is on a peninsula."),
                ]
            ),
            allow_retcon=True,
        )
        self.assertEqual(updated.rules["story.silence"], "He speaks.")
        self.assertEqual(updated.facts["world.setting"], "The valley is on a peninsula.")

    # Invalid keys and values reject the whole delta.
    def test_reject_invalid_key_and_oversized_value(self) -> None:
        memory = StoryMemory()
        invalid_key = MemoryDelta(
            set=[MemorySet(section="state", key="Bad Key", value="No.")]
        )
        oversized_value = MemoryDelta(
            set=[MemorySet(section="state", key="valid.key", value="x" * 1_001)]
        )
        with self.assertRaises(MemoryValidationError):
            apply_delta(memory, invalid_key)
        with self.assertRaises(MemoryValidationError):
            apply_delta(memory, oversized_value)

    # Duplicate keys, unknown thread targets, and overlapping set/resolve operations fail.
    def test_reject_duplicate_or_conflicting_operations(self) -> None:
        memory = StoryMemory(threads={"thread.open": "Still unresolved."})
        duplicate_keys = MemoryDelta(
            set=[
                MemorySet(section="state", key="same.key", value="One."),
                MemorySet(section="state", key="same.key", value="Two."),
            ]
        )
        unknown_thread = MemoryDelta(resolve_threads=["thread.unknown"])
        conflicting_thread = MemoryDelta(
            set=[MemorySet(section="thread", key="thread.open", value="Still unresolved.")],
            resolve_threads=["thread.open"],
        )
        for delta in (duplicate_keys, unknown_thread, conflicting_thread):
            with self.subTest(delta=delta), self.assertRaises(MemoryValidationError):
                apply_delta(memory, delta)

    # Operation and event limits prevent pathological model updates.
    def test_reject_too_many_operations_and_events(self) -> None:
        too_many_sets = [
            MemorySet(section="state", key=f"state.item{index}", value="Present.")
            for index in range(MAX_MEMORY_OPERATIONS + 1)
        ]
        with self.assertRaises(MemoryValidationError):
            apply_delta(StoryMemory(), MemoryDelta(set=too_many_sets))
        with self.assertRaises(MemoryValidationError):
            apply_delta(
                StoryMemory(),
                MemoryDelta(events=[f"Event {index}." for index in range(MAX_NEW_EVENTS + 1)]),
            )

    # A rejected mutation leaves the original Pydantic model unchanged.
    def test_failed_mutation_preserves_original_object(self) -> None:
        memory = StoryMemory(facts={"world.setting": "An island."})
        before = memory.model_dump()
        delta = MemoryDelta(
            set=[
                MemorySet(section="state", key="camera.remaining", value="Four."),
                MemorySet(section="fact", key="world.setting", value="A moon."),
            ]
        )
        with self.assertRaises(MemoryValidationError):
            apply_delta(memory, delta)
        self.assertEqual(memory.model_dump(), before)

    # Compact serialization remains below the configured memory limit for seeded canon.
    def test_format_memory_is_compact(self) -> None:
        formatted = format_memory(StoryMemory(facts={"world.place": "A valley."}))
        self.assertLess(len(formatted), MAX_MEMORY_CHARS)

    # Parse supported exposure descriptions and reject counts outside the original five.
    def test_photo_count_validation(self) -> None:
        self.assertEqual(remaining_photo_count(StoryMemory()), 5)
        self.assertEqual(
            remaining_photo_count(StoryMemory(state={PHOTO_COUNT_KEY: "Four photographs remain."})),
            4,
        )
        self.assertEqual(
            remaining_photo_count(StoryMemory(state={PHOTO_COUNT_KEY: "Zero exposures remain."})),
            0,
        )
        with self.assertRaises(MemoryValidationError):
            remaining_photo_count(StoryMemory(state={PHOTO_COUNT_KEY: "Six photographs remain."}))

    # Reject memory that exceeds the supported full-context limit.
    def test_reject_memory_over_size_limit(self) -> None:
        oversized = StoryMemory(events=["x" * 999 for _ in range(100)])
        with self.assertRaises(MemoryValidationError):
            validate_memory_size(oversized)


# Test structured AI decisions, API settings, and session-only updates.
class GenerationTests(unittest.TestCase):
    # Prepare a five-sentence realistic chapter and isolate seed-file behavior.
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.seed_path = Path(self.temporary_directory.name) / "story_memory.json"
        self.sdk_version_patch = patch("story_memory.version", return_value="2.54.0")
        self.sdk_version_patch.start()
        self.addCleanup(self.sdk_version_patch.stop)
        self.chapter = (
            "He chose the bridge. The river moved softly below the worn boards. "
            "A fisherman watched from the far bank. Then the church bell rang, "
            "and something answered beneath the bridge."
        )

    # The prompt asks AI to assess realism, end intent, photography, and its own contract.
    def test_generation_instruction_contract(self) -> None:
        ongoing = build_instructions(
            allow_retcon=False,
            decision_number=1,
            decision_limit_reached=False,
        ).casefold()
        at_limit = build_instructions(
            allow_retcon=False,
            decision_number=MAX_STORY_DECISIONS,
            decision_limit_reached=True,
        ).casefold()
        self.assertIn("decision_is_realistic", ongoing)
        self.assertIn("detect whether user explicitly wants the story to end", ongoing)
        self.assertIn(f"before decision {MIN_STORY_DECISIONS}", ongoing)
        self.assertIn("photo_taken", ongoing)
        self.assertIn("sentence_count", ongoing)
        self.assertIn("story_contract_passed", ongoing)
        self.assertIn("4 to 9 english sentences", ongoing)
        self.assertIn("unresolved cliffhanger", ongoing)
        self.assertIn("final sentence", ongoing)
        self.assertIn("no fixed outcome", ongoing)
        self.assertIn("must be final", at_limit)
        self.assertNotIn("ray bradbury", ongoing)

    # A normal response uses high reasoning and returns updated in-memory canon.
    def test_generate_story_api_contract_and_session_memory(self) -> None:
        session_memory = StoryMemory()
        parsed_result = make_result(
            self.chapter,
            memory=MemoryDelta(
                set=[MemorySet(section="state", key="camera.remaining", value="Five exposures.")],
                events=["He reached the old bridge."],
            ),
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=parsed_result)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ) as openai_constructor:
            returned_text, next_session_memory = generate_story(
                "He walks to the bridge.", session_memory
            )

        self.assertEqual(returned_text, self.chapter)
        openai_constructor.assert_called_once_with(
            api_key="test-key",
            timeout=API_TIMEOUT_SECONDS,
            max_retries=API_MAX_RETRIES,
        )
        call = client.responses.parse.call_args.kwargs
        self.assertEqual(call["model"], MODEL)
        self.assertEqual(call["reasoning"], {"effort": REASONING_EFFORT})
        self.assertEqual(call["text"], {"verbosity": "low"})
        self.assertFalse(call["store"])
        self.assertEqual(call["prompt_cache_key"], PROMPT_CACHE_KEY)
        self.assertNotIn("tools", call)
        self.assertIn("decision_is_realistic", call["instructions"])
        self.assertEqual(json.loads(call["input"])["user_decision"], "He walks to the bridge.")
        self.assertEqual(session_memory.step, 0)
        self.assertEqual(next_session_memory.step, 1)
        self.assertIn("He reached the old bridge.", next_session_memory.events)

    # AI rejection reprompts without applying model-proposed story changes.
    def test_ai_rejects_unrealistic_decision_without_memory_change(self) -> None:
        session_memory = StoryMemory(step=2)
        original = session_memory.model_dump()
        rejected_result = make_result(
            "",
            memory=MemoryDelta(events=["He teleported to the coast."]),
            decision_is_realistic=False,
            sentence_count=0,
            story_contract_passed=False,
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(output_parsed=rejected_result)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaises(UnrealisticDecisionError):
                generate_story("He teleports to the coast.", session_memory)

        client.responses.parse.assert_called_once()
        self.assertEqual(session_memory.model_dump(), original)

    # AI-reported self-check failure rejects output before session memory changes.
    def test_story_contract_self_check_failure_preserves_memory(self) -> None:
        session_memory = StoryMemory(step=1)
        original = session_memory.model_dump()
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(self.chapter, story_contract_passed=False)
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaisesRegex(GenerationError, "contract check failed"):
                generate_story("He studies the river.", session_memory)
        self.assertEqual(session_memory.model_dump(), original)

    # AI-reported sentence count is checked as a structured result, not recounted in Python.
    def test_ai_sentence_count_outside_limit_is_rejected(self) -> None:
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(self.chapter, sentence_count=3)
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaisesRegex(GenerationError, "sentence count"):
                generate_story("He studies the river.", StoryMemory())

    # AI end-request classification makes next generation final without local phrase parsing.
    def test_ai_end_request_makes_next_generation_final(self) -> None:
        final_text = (
            "He walked to the ridge. The river moved below the road. "
            "He carried the camera toward the coast. The valley faded behind him. "
            "At sunset, he had left the valley for good."
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(
                final_text,
                ending="leave_valley",
                end_request_detected=True,
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            _, updated_memory = generate_story("Please finish this story now.", StoryMemory())
        self.assertEqual(updated_memory.state[ENDING_KEY], "leave_valley")
        self.assertEqual(updated_memory.step, 1)

    # The ninth accepted decision is final even when AI detects no early end request.
    def test_decision_limit_makes_generation_final(self) -> None:
        session_memory = StoryMemory(step=MAX_STORY_DECISIONS - 1)
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(
                "He reached the ridge. Clouds gathered above the river. "
                "He walked toward the road. A truck waited near the bridge. "
                "He left the valley before the rain began.",
                ending="leave_valley",
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            _, updated_memory = generate_story(
                "He walks toward the waiting truck.",
                session_memory,
                decision_limit_reached=True,
            )
        self.assertEqual(updated_memory.state[ENDING_KEY], "leave_valley")
        self.assertEqual(updated_memory.step, MAX_STORY_DECISIONS)

    # AI end detection and outcome label must agree with application decision limit.
    def test_inconsistent_ai_end_decision_is_rejected(self) -> None:
        session_memory = StoryMemory(step=4)
        original = session_memory.model_dump()
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(self.chapter, ending="leave_valley")
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaisesRegex(GenerationError, "terminal outcome"):
                generate_story("He walks to the bridge.", session_memory)
        self.assertEqual(session_memory.model_dump(), original)

    # A final drowning outcome is recorded only in returned session memory.
    def test_final_drowning_ending(self) -> None:
        final_text = (
            "He stepped into the river at the bend. The current closed over the camera strap. "
            "No cry crossed the still valley. By morning, the river had carried him onward, "
            "and he had drowned without a sound."
        )
        session_memory = StoryMemory()
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(
                final_text,
                ending="drowning",
                end_request_detected=True,
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            _, updated_memory = generate_story("End the story.", session_memory)
        self.assertEqual(updated_memory.state[ENDING_KEY], "drowning")
        self.assertIsNone(session_memory.state.get(ENDING_KEY))
        self.assertEqual(updated_memory.step, 1)

    # A final departure from the valley is also a permitted terminal outcome.
    def test_final_leaving_valley_ending(self) -> None:
        final_text = (
            "He took the ridge road beyond the last empty house. The valley narrowed behind him. "
            "He carried the camera and the sound of the church bell toward the coast. "
            "At sunset, he had left the valley for good."
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(
                final_text,
                ending="leave_valley",
                end_request_detected=True,
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            _, updated_memory = generate_story("End the story.", StoryMemory())
        self.assertEqual(updated_memory.state[ENDING_KEY], "leave_valley")

    # A valid AI photo decision decrements exactly one session exposure.
    def test_photo_decision_decrements_remaining_count(self) -> None:
        session_memory = StoryMemory(state={PHOTO_COUNT_KEY: "Five photographs remain."})
        photo_text = (
            "He lifted the old camera. He took a photograph of the bridge. "
            "The shutter clicked once in the quiet valley. A loose board shifted under his hand. "
            "He looked toward the road."
        )
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(photo_text, photo_taken=True)
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            _, next_session_memory = generate_story(
                "He looks over the bridge and considers a photograph.", session_memory
            )
        self.assertEqual(remaining_photo_count(session_memory), 5)
        self.assertEqual(remaining_photo_count(next_session_memory), 4)

    # AI cannot overwrite the exposure counter that Python owns.
    def test_reject_model_photo_count_mutation(self) -> None:
        session_memory = StoryMemory()
        original = session_memory.model_dump()
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(
                self.chapter,
                memory=MemoryDelta(
                    set=[MemorySet(section="state", key=PHOTO_COUNT_KEY, value="Four photographs remain.")]
                ),
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaisesRegex(GenerationError, "application owns"):
                generate_story("He examines the station timetable.", session_memory)
        self.assertEqual(session_memory.model_dump(), original)

    # A photo cannot be taken after all session exposures are spent.
    def test_reject_photo_after_exposures_spent(self) -> None:
        session_memory = StoryMemory(state={PHOTO_COUNT_KEY: "Zero exposures remain."})
        original = session_memory.model_dump()
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(self.chapter, photo_taken=True)
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaises(GenerationError):
                generate_story("Photograph the church.", session_memory)
        self.assertEqual(session_memory.model_dump(), original)

    # API errors leave caller-owned session memory unchanged.
    def test_api_failure_preserves_session_memory(self) -> None:
        session_memory = StoryMemory(step=2)
        original = session_memory.model_dump()
        client = Mock()
        client.responses.parse.side_effect = APIConnectionError(
            message="Connection error.",
            request=None,
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaisesRegex(GenerationError, "Could not connect"):
                generate_story("He returns to town.", session_memory)
        self.assertEqual(session_memory.model_dump(), original)

    # Missing credentials fail before the API client is constructed.
    def test_missing_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("story_memory.OpenAI") as client:
            with self.assertRaises(ConfigurationError):
                generate_story("He walks to the church.", StoryMemory())
        client.assert_not_called()

    # An unsupported SDK fails with setup guidance before constructing the API client.
    def test_unsupported_openai_sdk_version_fails_before_api(self) -> None:
        session_memory = StoryMemory()
        original = session_memory.model_dump()
        with patch("story_memory.version", return_value="3.11.0"), patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key"}
        ), patch("story_memory.OpenAI") as client:
            with self.assertRaisesRegex(ConfigurationError, "requires openai>=2.54,<3"):
                generate_story("He studies the station timetable.", session_memory)
        client.assert_not_called()
        self.assertEqual(session_memory.model_dump(), original)

    # Generated session changes never rewrite the on-disk seed or survive a reload.
    def test_session_memory_resets_to_read_only_seed(self) -> None:
        seed = StoryMemory(facts={"world.setting": "A Caribbean valley."})
        self.seed_path.write_text(seed.model_dump_json(), encoding="utf-8")
        original_bytes = self.seed_path.read_bytes()
        session_memory = load_memory(self.seed_path)
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(self.chapter, memory=MemoryDelta(events=["He reached the bridge."]))
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            _, next_session_memory = generate_story("He walks to the bridge.", session_memory)

        self.assertEqual(next_session_memory.step, 1)
        self.assertEqual(session_memory.step, 0)
        self.assertEqual(self.seed_path.read_bytes(), original_bytes)
        self.assertEqual(load_memory(self.seed_path), seed)

    # API contract failures leave caller-owned memory unchanged.
    def test_invalid_ai_contract_preserves_session_memory(self) -> None:
        session_memory = StoryMemory(step=1)
        original = session_memory.model_dump()
        invalid_results = (
            make_result(self.chapter, sentence_count=3),
            make_result(self.chapter, story_contract_passed=False),
        )
        client = Mock()
        for result in invalid_results:
            client.responses.parse.return_value = SimpleNamespace(output_parsed=result)
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
                "story_memory.OpenAI", return_value=client
            ), self.subTest(result=result):
                with self.assertRaises(GenerationError):
                    generate_story("He walks to the market.", session_memory)
            self.assertEqual(session_memory.model_dump(), original)

    # A delta that crosses the total memory limit is rejected before returning new state.
    def test_oversized_delta_preserves_session_memory(self) -> None:
        session_memory = StoryMemory(step=2, events=["x" * 900 for _ in range(80)])
        original = session_memory.model_dump()
        client = Mock()
        client.responses.parse.return_value = SimpleNamespace(
            output_parsed=make_result(
                self.chapter,
                memory=MemoryDelta(events=[f"{index}" + "y" * 995 for index in range(10)]),
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI", return_value=client
        ):
            with self.assertRaises(MemoryValidationError):
                generate_story("He sees the empty schoolhouse.", session_memory)
        self.assertEqual(session_memory.model_dump(), original)

    # An oversized in-memory canon stops before any OpenAI request.
    def test_oversized_memory_stops_before_api(self) -> None:
        oversized = StoryMemory(events=["x" * 999 for _ in range(100)])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI"
        ) as client:
            with self.assertRaises(StoryMemoryError):
                generate_story("He watches the valley.", oversized)
        client.assert_not_called()

    # An ended in-session story cannot receive another generation.
    def test_completed_story_rejects_more_generation(self) -> None:
        session_memory = StoryMemory(state={ENDING_KEY: "leave_valley"})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "story_memory.OpenAI"
        ) as client:
            with self.assertRaises(StoryAlreadyEndedError):
                generate_story("Continue.", session_memory)
        client.assert_not_called()




# Run this file directly for a focused local memory test suite.
if __name__ == "__main__":
    unittest.main()
