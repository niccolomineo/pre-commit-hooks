"""Parsing of the example file and the comparison that follows it."""

from __future__ import annotations

import unittest
from pathlib import Path

from check_env_example import example_file
from check_env_example.checker import check
from check_env_example.extractors import Reference


def parse(text: str):
    return example_file.parse(Path(".env.example"), text)


class ParsingTests(unittest.TestCase):
    def test_reads_keys_with_their_lines(self) -> None:
        parsed = parse("# comment\n\nFIRST=1\nSECOND=\n")
        self.assertEqual(
            [(entry.key, entry.line) for entry in parsed.entries],
            [("FIRST", 3), ("SECOND", 4)],
        )

    def test_accepts_the_export_prefix(self) -> None:
        parsed = parse("export EXPORTED=1\n")
        self.assertEqual([entry.key for entry in parsed.entries], ["EXPORTED"])

    def test_skips_comments_and_junk(self) -> None:
        parsed = parse("# KEY=1\n\nnot a line\nREAL=1\n")
        self.assertEqual([entry.key for entry in parsed.entries], ["REAL"])

    def test_records_duplicates(self) -> None:
        parsed = parse("SAME=1\nOTHER=2\nSAME=3\n")
        self.assertEqual([entry.key for entry in parsed.entries], ["SAME", "OTHER"])
        [duplicate] = parsed.duplicates
        self.assertEqual(
            (duplicate.key, duplicate.line, duplicate.first_line), ("SAME", 3, 1)
        )

    def test_marks_the_inline_opt_out(self) -> None:
        parsed = parse("KEPT=1  # check-env-example: ignore\nPLAIN=2\n")
        self.assertEqual([entry.ignored for entry in parsed.entries], [True, False])


class DiscoveryTests(unittest.TestCase):
    def test_prefers_the_conventional_order(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / ".env.sample").write_text("A=1\n")
            (root / ".env.example").write_text("A=1\n")
            self.assertEqual(example_file.discover(root).name, ".env.example")

    def test_returns_none_when_there_is_nothing(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            self.assertIsNone(example_file.discover(Path(name)))


class CheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = Reference(var="USED", path=Path("app.py"), line=3)

    def test_reports_a_variable_the_example_file_omits(self) -> None:
        result = check(example=parse("OTHER=1\n"), references=[self.reference])
        self.assertEqual([item.var for item in result.missing], ["USED"])
        self.assertEqual(result.missing[0].first.line, 3)

    def test_reports_a_documented_variable_nobody_reads(self) -> None:
        result = check(example=parse("USED=1\nORPHAN=2\n"), references=[self.reference])
        self.assertEqual([entry.key for entry in result.unused], ["ORPHAN"])

    def test_no_unused_silences_that_half(self) -> None:
        result = check(
            example=parse("USED=1\nORPHAN=2\n"),
            references=[self.reference],
            report_unused=False,
        )
        self.assertEqual(result.unused, ())
        self.assertTrue(result.ok)

    def test_counts_repeated_reads(self) -> None:
        references = [
            self.reference,
            Reference(var="USED", path=Path("other.py"), line=9),
        ]
        result = check(example=parse(""), references=references)
        self.assertEqual(result.missing[0].occurrences, 2)

    def test_the_default_allowlist_covers_os_variables(self) -> None:
        references = [Reference(var="PATH", path=Path("app.py"), line=1)]
        self.assertTrue(check(example=parse(""), references=references).ok)

    def test_the_default_allowlist_covers_ci_prefixes(self) -> None:
        references = [Reference(var="GITHUB_SHA", path=Path("app.py"), line=1)]
        self.assertTrue(check(example=parse(""), references=references).ok)

    def test_an_allowlisted_variable_is_still_used(self) -> None:
        # Documenting PATH is odd but legal; it must not then be called unused.
        references = [Reference(var="PATH", path=Path("app.py"), line=1)]
        result = check(example=parse("PATH=/usr/bin\n"), references=references)
        self.assertTrue(result.ok)

    def test_an_allowlisted_variable_is_not_unused_either(self) -> None:
        # PYTHONDEVMODE belongs in the example file for a human to set, and no
        # line of code will ever read it. Neither half of the check applies.
        result = check(example=parse("PYTHONDEVMODE=1\n"), references=[])
        self.assertTrue(result.ok)

    def test_ignore_silences_both_directions(self) -> None:
        result = check(
            example=parse("HANDLED_ELSEWHERE=\n"),
            references=[],
            allowlist={"HANDLED_ELSEWHERE"},
        )
        self.assertTrue(result.ok)

    def test_the_inline_opt_out_suppresses_unused(self) -> None:
        example = parse("ORPHAN=1  # check-env-example: ignore\n")
        self.assertTrue(check(example=example, references=[]).ok)

    def test_duplicates_reach_the_report(self) -> None:
        result = check(example=parse("SAME=1\nSAME=2\n"), references=[])
        self.assertEqual(len(result.duplicates), 1)
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
