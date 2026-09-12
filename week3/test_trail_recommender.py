import ast
import builtins
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import trail_recommender as app


class FakeResponse:
    def __init__(self, value):
        self.output_text = json.dumps(value)


class FakeResponses:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(next(self.values))


class FakeClient:
    def __init__(self, values):
        self.responses = FakeResponses(values)


def good_guard(language="en"):
    return {"status": "valid", "language": language, "reason": ""}


def good_result(match="good"):
    return {
        "match": match,
        "needs_more_info": False,
        "note": "Have a great hike!",
        "recommendations": [
            {
                "name": "Example Trail",
                "location": "Example Park, U.S.",
                "summary": "A pleasant route with a nice view.",
                "fit": "It matches your time and route preference.",
                "facts": ["Loop route", "Free parking"],
                "before_you_go": ["Check current conditions."],
                "sources": [
                    {
                        "name": "Hiking Project",
                        "url": "https://www.hikingproject.com/trail/1/example",
                    }
                ],
            }
        ],
    }


class TrailRecommenderTests(unittest.TestCase):
    def test_geography_is_first_and_questions_are_short(self):
        self.assertEqual(app.QUESTIONS[0][0], "location")
        for _, question, _ in app.QUESTIONS:
            self.assertLessEqual(len(question), 140)
            self.assertLessEqual(len(question.split()), 24)

    def test_unicode_answer_survives_guard(self):
        client = FakeClient([good_guard("zh")])
        session = app.InterviewSession()
        answer = "纽约附近的森林步道 🥾"
        with patch.object(builtins, "input", return_value=answer):
            result = app.ask_question(client, session, "location", "Where?")
        self.assertEqual(result, answer)
        self.assertEqual(session.language, "zh")

    def test_guard_retries_then_returns_none(self):
        client = FakeClient([good_guard()] * 3)
        session = app.InterviewSession()
        with patch.object(builtins, "input", side_effect=["", "", ""]):
            result = app.ask_question(client, session, "route", "Which route?")
        self.assertIsNone(result)
        self.assertEqual(len(session.asked), 3)

    def test_source_url_must_be_allowlisted(self):
        result = good_result()
        result["recommendations"][0]["sources"][0]["url"] = "https://example.com/trail"
        self.assertFalse(app.valid_result(result))

    def test_result_accepts_allowed_source(self):
        self.assertTrue(app.valid_result(good_result()))

    def test_tool_payload_has_both_tools_and_source_filter(self):
        client = FakeClient([good_result()])
        session = app.InterviewSession(answers={"location": "Seattle"})
        app.search(client, session, "")
        payload = client.responses.calls[0]
        types = [item["type"] for item in payload["tools"]]
        self.assertEqual(types, ["tool_search", "function", "web_search"])
        self.assertEqual(
            payload["tools"][2]["filters"]["allowed_domains"],
            app.SOURCE_DOMAINS,
        )

    def test_render_does_not_show_internal_meta(self):
        with patch("builtins.print") as printer:
            app.render(good_result(), "")
        output = "\n".join(str(call.args[0]) for call in printer.call_args_list)
        self.assertNotIn("model", output.lower())
        self.assertNotIn("question count", output.lower())
        self.assertNotIn("program design", output.lower())

    def test_render_mentions_close_match_after_relaxation(self):
        with patch("builtins.print") as printer:
            app.render(good_result("partial"), "popularity")
        output = "\n".join(str(call.args[0]) for call in printer.call_args_list)
        self.assertIn("Not a good match", output)

    def test_max_control_nesting_is_four(self):
        source = Path(app.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        control = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)

        def depth(node, current=0):
            current += isinstance(node, control)
            return max([current] + [depth(child, current) for child in ast.iter_child_nodes(node)])

        self.assertLessEqual(depth(tree), 4)


if __name__ == "__main__":
    unittest.main()
