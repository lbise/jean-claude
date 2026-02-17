from __future__ import annotations

import unittest

from jean_claude.prefs.profile import default_user_profile, missing_profile_fields, normalize_user_profile


class PreferencesProfileTestCase(unittest.TestCase):
    def test_default_profile_shape(self) -> None:
        profile = default_user_profile()
        self.assertEqual(profile["subtitles"], "unknown")
        self.assertEqual(profile["genres_like"], [])
        self.assertIsNone(profile["release_year_min"])

    def test_normalize_profile_handles_invalid_values(self) -> None:
        profile = normalize_user_profile(
            {
                "genres_like": "sci-fi, thriller",
                "release_year_min": "2025",
                "release_year_max": "1990",
                "movie_vs_series": "both",
                "subtitles": "prefer_subtitles",
            }
        )
        self.assertEqual(profile["genres_like"], ["sci-fi", "thriller"])
        self.assertEqual(profile["release_year_min"], 1990)
        self.assertEqual(profile["release_year_max"], 2025)

    def test_missing_profile_fields(self) -> None:
        missing = missing_profile_fields(default_user_profile())
        self.assertIn("genres_like", missing)
        self.assertIn("languages", missing)
        self.assertIn("examples", missing)


if __name__ == "__main__":
    unittest.main()
