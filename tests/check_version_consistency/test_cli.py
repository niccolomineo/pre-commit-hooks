"""End-to-end runs against throwaway repositories."""

from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_version_consistency.cli import main


def build(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def git_init(root: Path) -> None:
    for command in (
        ("git", "-c", "init.defaultBranch=main", "init", "--quiet"),
        ("git", "add", "--all"),
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)


@contextlib.contextmanager
def sandbox(files: dict[str, str], *, git: bool = False):
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        build(root, files)
        if git:
            git_init(root)
        with contextlib.chdir(root):
            yield root


def invoke(*argv: str) -> tuple[int, str]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(list(argv))
    return code, stream.getvalue()


AGREEING = {
    "pyproject.toml": '[project]\nname = "x"\nversion = "1.4.0"\n',
    "package.json": '{\n  "name": "x",\n  "version": "1.4.0"\n}\n',
    "src/pkg/__init__.py": '__version__ = "1.4.0"\n',
    "CHANGELOG.md": "# Changelog\n\n## [1.4.0] - 2026-08-18\n",
}
DRIFTED = AGREEING | {"src/pkg/__init__.py": '__version__ = "1.3.2"\n'}


class AgreeingRepositoryTests(unittest.TestCase):
    def test_passes_silently(self) -> None:
        with sandbox(AGREEING):
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")

    def test_passes_the_same_way_inside_a_git_repository(self) -> None:
        with sandbox(AGREEING, git=True):
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")

    def test_a_repository_with_one_manifest_passes(self) -> None:
        with sandbox({"pyproject.toml": '[project]\nversion = "1.0.0"\n'}):
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")


class DriftedRepositoryTests(unittest.TestCase):
    def test_names_the_odd_one_out_and_shows_the_rest(self) -> None:
        with sandbox(DRIFTED):
            code, output = invoke()
        self.assertEqual(code, 1)
        self.assertIn("src/pkg/__init__.py:1", output)
        self.assertIn("disagrees", output)
        self.assertIn("Expected 1.4.0 everywhere.", output)
        # The agreeing sources are listed too: that is what tells you which
        # side to fix.
        self.assertIn("pyproject.toml:3", output)
        self.assertIn("package.json:3", output)

    def test_quiet_prints_the_summary_only(self) -> None:
        with sandbox(DRIFTED):
            code, output = invoke("--quiet")
        self.assertEqual(code, 1)
        self.assertEqual(output.strip(), "1 disagreeing declaration (expected 1.4.0)")

    def test_canonical_flips_which_side_is_wrong(self) -> None:
        with sandbox(DRIFTED):
            code, output = invoke("--canonical", "src/pkg/__init__.py")
        self.assertEqual(code, 1)
        self.assertIn("Expected 1.3.2 everywhere.", output)

    def test_exclude_removes_a_declaration(self) -> None:
        with sandbox(DRIFTED):
            code, output = invoke("--exclude", "src/*")
        self.assertEqual(code, 0)
        self.assertEqual(output, "")

    def test_ignore_value_removes_a_declaration(self) -> None:
        with sandbox(DRIFTED):
            code, output = invoke("--ignore-value", "1.3.2")
        self.assertEqual(code, 0)
        self.assertEqual(output, "")


class ChangelogModeTests(unittest.TestCase):
    LAGGING = AGREEING | {
        "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [1.3.0] - 2026-01-01\n"
    }

    def test_lenient_accepts_a_release_in_progress(self) -> None:
        with sandbox(self.LAGGING):
            code, _ = invoke()
        self.assertEqual(code, 0)

    def test_strict_does_not(self) -> None:
        with sandbox(self.LAGGING):
            code, output = invoke("--changelog", "strict")
        self.assertEqual(code, 1)
        self.assertIn("CHANGELOG.md", output)


class GenericSourceTests(unittest.TestCase):
    def test_reads_a_format_that_is_not_built_in(self) -> None:
        files = AGREEING | {"pubspec.yaml": "name: x\nversion: 9.9.9\n"}
        with sandbox(files):
            code, output = invoke(
                "--source", r"pubspec.yaml:^version:\s*(?P<version>\S+)"
            )
        self.assertEqual(code, 1)
        self.assertIn("pubspec.yaml:2", output)


class InlineOptOutTests(unittest.TestCase):
    def test_a_marked_line_is_left_alone(self) -> None:
        files = DRIFTED | {
            "src/pkg/__init__.py": (
                '__version__ = "1.3.2"  # check-version-consistency: ignore\n'
            )
        }
        with sandbox(files):
            code, output = invoke()
        self.assertEqual(code, 0, output)


class ModeEquivalenceTests(unittest.TestCase):
    def test_a_git_repository_and_a_bare_directory_agree(self) -> None:
        with sandbox(DRIFTED):
            plain = invoke()
        with sandbox(DRIFTED, git=True):
            tracked = invoke()
        self.assertEqual(plain, tracked)


class UsageErrorTests(unittest.TestCase):
    def assertUsageError(self, *argv: str) -> None:
        quiet = io.StringIO()
        with (
            sandbox(AGREEING),
            contextlib.redirect_stderr(quiet),
            self.assertRaises(SystemExit) as raised,
        ):
            main(list(argv))
        self.assertEqual(raised.exception.code, 2)

    def test_a_source_without_a_separator_is_an_error(self) -> None:
        self.assertUsageError("--source", "nonsense")

    def test_a_source_without_a_group_is_an_error(self) -> None:
        self.assertUsageError("--source", "pubspec.yaml:^version")

    def test_an_unknown_changelog_mode_is_an_error(self) -> None:
        self.assertUsageError("--changelog", "sometimes")


if __name__ == "__main__":
    unittest.main()
