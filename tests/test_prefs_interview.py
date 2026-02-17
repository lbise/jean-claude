from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jean_claude.llm.mock import MockLLMClient
from jean_claude.prefs.interview import run_interview
from jean_claude.prefs.store import PreferencesStore


class InterviewFlowTestCase(unittest.TestCase):
    def test_interview_updates_and_saves_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PreferencesStore(path=Path(temp_dir) / "prefs.json")
            client = MockLLMClient()
            responses = iter(
                [
                    "I like sci-fi thrillers, mostly movies, in English with subtitles.",
                    "y",
                ]
            )
            output_lines: list[str] = []

            profile = run_interview(
                client=client,
                model="mock-v1",
                store=store,
                max_turns=1,
                input_fn=lambda _prompt: next(responses),
                output_fn=output_lines.append,
            )

            self.assertIn("sci-fi", profile["genres_like"])
            self.assertEqual(profile["movie_vs_series"], "movies")
            self.assertEqual(profile["subtitles"], "prefer_subtitles")

            loaded = store.load()
            self.assertEqual(loaded["movie_vs_series"], "movies")
            self.assertIn("Great. I saved your baseline preferences.", "\n".join(output_lines))


if __name__ == "__main__":
    unittest.main()
