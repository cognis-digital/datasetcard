"""Hardening tests: bad input, edge cases, error paths."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datasetcard.core import profile_dataset, TOOL_NAME, TOOL_VERSION  # noqa: E402
from datasetcard.cli import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(suffix: str, content: str) -> str:
    """Write content to a named temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


# ---------------------------------------------------------------------------
# core.py — input validation
# ---------------------------------------------------------------------------

class TestUnsupportedExtension(unittest.TestCase):
    """Unsupported file extension raises ValueError with a helpful message."""

    def test_xlsx_raises_valueerror(self):
        path = _write(".xlsx", "fake")
        try:
            with self.assertRaises(ValueError) as ctx:
                profile_dataset(path)
            self.assertIn(".xlsx", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_parquet_raises_valueerror(self):
        path = _write(".parquet", "PAR1")
        try:
            with self.assertRaises(ValueError):
                profile_dataset(path)
        finally:
            os.unlink(path)


class TestMalformedJsonl(unittest.TestCase):
    """Malformed JSONL line raises ValueError, not a raw json.JSONDecodeError."""

    def test_bad_json_line(self):
        path = _write(".jsonl", '{"a": 1}\n{bad json\n')
        try:
            with self.assertRaises(ValueError) as ctx:
                profile_dataset(path)
            msg = str(ctx.exception)
            self.assertIn("line 2", msg)
        finally:
            os.unlink(path)

    def test_non_object_json_line(self):
        """A JSONL line that is an array (not object) raises ValueError."""
        path = _write(".jsonl", '{"a": 1}\n[1, 2, 3]\n')
        try:
            with self.assertRaises(ValueError) as ctx:
                profile_dataset(path)
            self.assertIn("JSON object", str(ctx.exception))
        finally:
            os.unlink(path)


class TestEmptyFile(unittest.TestCase):
    """Completely empty files (no columns) raise ValueError."""

    def test_empty_csv(self):
        path = _write(".csv", "")
        try:
            with self.assertRaises(ValueError) as ctx:
                profile_dataset(path)
            self.assertIn("no columns", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_empty_jsonl(self):
        path = _write(".jsonl", "\n\n")
        try:
            with self.assertRaises(ValueError) as ctx:
                profile_dataset(path)
            self.assertIn("no columns", str(ctx.exception))
        finally:
            os.unlink(path)


class TestMaxSamplesValidation(unittest.TestCase):
    """Negative max_samples raises ValueError."""

    def setUp(self):
        self.path = _write(".csv", "a,b\n1,2\n")

    def tearDown(self):
        os.unlink(self.path)

    def test_negative_max_samples(self):
        with self.assertRaises(ValueError) as ctx:
            profile_dataset(self.path, max_samples=-1)
        self.assertIn("max_samples", str(ctx.exception))

    def test_zero_max_samples_ok(self):
        """max_samples=0 is valid; samples list will just be empty."""
        profile = profile_dataset(self.path, max_samples=0)
        self.assertEqual(profile.columns[0].samples, [])


class TestHeaderOnlyCsv(unittest.TestCase):
    """CSV with only a header row (no data rows) produces a valid profile."""

    def test_header_only(self):
        path = _write(".csv", "col_a,col_b\n")
        try:
            profile = profile_dataset(path)
            self.assertEqual(profile.num_rows, 0)
            self.assertEqual(profile.num_columns, 2)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# cli.py — exit-code contract
# ---------------------------------------------------------------------------

class TestCLIExitCodes(unittest.TestCase):
    """CLI exit codes: 0 success, 1 file-not-found, 2 parse/validation error."""

    def test_missing_file_exit_1(self):
        self.assertEqual(main(["profile", "no_such_file_xyz.csv"]), 1)

    def test_unsupported_extension_exit_2(self):
        path = _write(".xlsx", "fake")
        try:
            self.assertEqual(main(["profile", path]), 2)
        finally:
            os.unlink(path)

    def test_malformed_jsonl_exit_2(self):
        path = _write(".jsonl", "{bad\n")
        try:
            self.assertEqual(main(["profile", path]), 2)
        finally:
            os.unlink(path)

    def test_valid_input_exit_0(self):
        path = _write(".csv", "x,y\n1,2\n3,4\n")
        try:
            self.assertEqual(main(["profile", path]), 0)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# core constants — TOOL_NAME and TOOL_VERSION now defined in core
# ---------------------------------------------------------------------------

class TestCoreConstants(unittest.TestCase):
    def test_tool_name_defined_in_core(self):
        self.assertEqual(TOOL_NAME, "datasetcard")

    def test_tool_version_nonempty(self):
        self.assertTrue(TOOL_VERSION)


if __name__ == "__main__":
    unittest.main()
