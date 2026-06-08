"""Smoke tests for datasetcard. No network, no third-party deps."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datasetcard import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    profile_dataset,
    build_croissant,
    build_card_markdown,
    build_datasheet,
)
from datasetcard.cli import main  # noqa: E402

DEMO = os.path.join(os.path.dirname(__file__), "..", "demos", "01-basic", "signups.csv")


class TestMetadata(unittest.TestCase):
    def test_tool_constants(self):
        self.assertEqual(TOOL_NAME, "datasetcard")
        self.assertTrue(TOOL_VERSION)


class TestProfile(unittest.TestCase):
    def setUp(self):
        self.profile = profile_dataset(DEMO)

    def test_shape(self):
        self.assertEqual(self.profile.num_rows, 8)
        self.assertEqual(self.profile.num_columns, 6)

    def test_types_inferred(self):
        types = {c.name: c.dtype for c in self.profile.columns}
        self.assertEqual(types["user_id"], "integer")
        self.assertEqual(types["score"], "float")
        self.assertEqual(types["signup_date"], "date")
        self.assertEqual(types["active"], "boolean")
        self.assertEqual(types["email"], "text")

    def test_missing_counted(self):
        score = next(c for c in self.profile.columns if c.name == "score")
        self.assertEqual(score.missing, 1)
        self.assertEqual(score.count, 7)

    def test_numeric_stats(self):
        age = next(c for c in self.profile.columns if c.name == "age")
        self.assertEqual(age.min, 23)
        self.assertEqual(age.max, 52)
        self.assertIsNotNone(age.mean)

    def test_pii_detection(self):
        flagged = {f["column"] for f in self.profile.pii_flags}
        self.assertIn("email", flagged)

    def test_sha256_stable(self):
        self.assertEqual(self.profile.sha256, profile_dataset(DEMO).sha256)


class TestArtifacts(unittest.TestCase):
    def setUp(self):
        self.profile = profile_dataset(DEMO)

    def test_croissant_valid(self):
        doc = build_croissant(self.profile)
        self.assertEqual(doc["@type"], "sc:Dataset")
        self.assertEqual(len(doc["recordSet"][0]["field"]), 6)
        self.assertEqual(doc["distribution"][0]["sha256"], self.profile.sha256)
        json.dumps(doc)  # serializable

    def test_card_markdown(self):
        md = build_card_markdown(self.profile)
        self.assertIn("# Dataset Card for", md)
        self.assertIn("## Provenance", md)
        self.assertIn(self.profile.sha256, md)

    def test_datasheet(self):
        sheet = build_datasheet(self.profile)
        self.assertIn("Composition", sheet["sections"])
        self.assertIn("Motivation", sheet["sections"])


class TestCLI(unittest.TestCase):
    def test_profile_table(self):
        self.assertEqual(main(["profile", DEMO]), 0)

    def test_profile_json(self):
        self.assertEqual(main(["--format", "json", "profile", DEMO]), 0)

    def test_croissant(self):
        self.assertEqual(main(["croissant", DEMO]), 0)

    def test_card(self):
        self.assertEqual(main(["card", DEMO]), 0)

    def test_datasheet(self):
        self.assertEqual(main(["datasheet", DEMO]), 0)

    def test_missing_file_nonzero(self):
        self.assertEqual(main(["profile", "does_not_exist.csv"]), 1)


if __name__ == "__main__":
    unittest.main()
