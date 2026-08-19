"""End-to-end runs against throwaway repositories.

The fixtures are built at test time rather than committed, so that the tool's
own dogfooding run never has to scan a deliberately broken project.
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_env_example.cli import main


def build(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def git_init(root: Path) -> None:
    run = ("git", "-c", "init.defaultBranch=main", "init", "--quiet")
    subprocess.run(run, cwd=root, check=True, capture_output=True)
    subprocess.run(("git", "add", "--all"), cwd=root, check=True, capture_output=True)


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


CLEAN = {
    ".env.example": "DATABASE_URL=\nSECRET_KEY=\n",
    "app.py": 'import os\nos.environ["DATABASE_URL"]\nos.getenv("SECRET_KEY")\n',
}
BROKEN = {
    ".env.example": "DATABASE_URL=\nLEGACY_SMTP_HOST=\n",
    "app.py": 'import os\nos.environ["DATABASE_URL"]\n',
    "web/db.ts": "export const size = process.env.DATABASE_POOL_SIZE;\n",
}


class CleanRepositoryTests(unittest.TestCase):
    def test_passes_silently(self) -> None:
        with sandbox(CLEAN):
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")

    def test_passes_the_same_way_inside_a_git_repository(self) -> None:
        with sandbox(CLEAN, git=True):
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")

    def test_passes_when_there_is_no_example_file(self) -> None:
        with sandbox({"app.py": 'import os\nos.getenv("ANYTHING")\n'}):
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")


class BrokenRepositoryTests(unittest.TestCase):
    def test_reports_both_directions(self) -> None:
        with sandbox(BROKEN):
            code, output = invoke()
        self.assertEqual(code, 1)
        self.assertIn("DATABASE_POOL_SIZE", output)
        self.assertIn("web/db.ts:1", output)
        self.assertIn("LEGACY_SMTP_HOST", output)
        self.assertIn(".env.example:2", output)
        self.assertIn("1 missing, 1 unused", output)

    def test_quiet_prints_the_summary_only(self) -> None:
        with sandbox(BROKEN):
            code, output = invoke("--quiet")
        self.assertEqual(code, 1)
        self.assertEqual(output.strip(), "1 missing, 1 unused")

    def test_ignore_drops_a_variable(self) -> None:
        with sandbox(BROKEN):
            code, output = invoke("--ignore", "DATABASE_POOL_SIZE", "--no-unused")
        self.assertEqual(code, 0)
        self.assertEqual(output, "")

    def test_exclude_drops_a_file(self) -> None:
        with sandbox(BROKEN):
            code, output = invoke("--exclude", "web/*", "--no-unused")
        self.assertEqual(code, 0)
        self.assertEqual(output, "")


class ModeEquivalenceTests(unittest.TestCase):
    """The hook must not care whether git is present or what changed."""

    def test_a_git_repository_and_a_bare_directory_agree(self) -> None:
        with sandbox(BROKEN):
            plain = invoke()
        with sandbox(BROKEN, git=True):
            tracked = invoke()
        self.assertEqual(plain, tracked)

    def test_an_untracked_file_is_not_scanned(self) -> None:
        # It is not part of the commit, so it must not fail the commit.
        with sandbox(CLEAN, git=True) as root:
            (root / "stray.py").write_text('import os\nos.getenv("STRAY")\n')
            code, output = invoke()
        self.assertEqual(code, 0)
        self.assertEqual(output, "")


class FixTests(unittest.TestCase):
    def test_appends_the_missing_keys(self) -> None:
        with sandbox(BROKEN, git=True) as root:
            code, output = invoke("--fix", "--no-unused")
            written = (root / ".env.example").read_text()
        self.assertEqual(code, 1, "a modified file must still fail the run")
        self.assertIn("added 1 missing variable", output)
        self.assertIn("# used in web/db.ts:1", written)
        self.assertIn("DATABASE_POOL_SIZE=", written)
        self.assertIn("DATABASE_URL=", written)

    def test_running_it_twice_settles(self) -> None:
        with sandbox(BROKEN, git=True) as root:
            invoke("--fix", "--no-unused")
            first = (root / ".env.example").read_text()
            code, _ = invoke("--fix", "--no-unused")
            second = (root / ".env.example").read_text()
        self.assertEqual(code, 0)
        self.assertEqual(first, second)


class UsageErrorTests(unittest.TestCase):
    def assertUsageError(self, *argv: str) -> None:
        quiet = io.StringIO()
        with (
            sandbox(CLEAN),
            contextlib.redirect_stderr(quiet),
            self.assertRaises(SystemExit) as raised,
        ):
            main(list(argv))
        self.assertEqual(raised.exception.code, 2)

    def test_a_missing_example_file_is_an_error(self) -> None:
        self.assertUsageError("--example-file", "nowhere.env")

    def test_a_malformed_extra_pattern_is_an_error(self) -> None:
        self.assertUsageError("--extra-pattern", "py:no-group-here")

    def test_an_extra_pattern_without_a_separator_is_an_error(self) -> None:
        self.assertUsageError("--extra-pattern", "nonsense")


if __name__ == "__main__":
    unittest.main()
