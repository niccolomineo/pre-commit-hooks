"""Reading a version out of each supported format."""

from __future__ import annotations

import unittest
from pathlib import Path

from check_version_consistency.sources.changelog import read_changelog
from check_version_consistency.sources.dunder import read_dunder
from check_version_consistency.sources.manifests import (
    read_cargo,
    read_chart,
    read_package_json,
    read_pyproject,
    read_setup_cfg,
)


def only(declarations) -> tuple[str, int]:
    [declaration] = declarations
    return declaration.version, declaration.line


class PyprojectTests(unittest.TestCase):
    def test_reads_the_project_table(self) -> None:
        text = '[project]\nname = "x"\nversion = "1.4.0"\n'
        self.assertEqual(
            only(read_pyproject(Path("pyproject.toml"), text)), ("1.4.0", 3)
        )

    def test_falls_back_to_poetry(self) -> None:
        text = '[tool.poetry]\nname = "x"\nversion = "2.0.1"\n'
        self.assertEqual(
            only(read_pyproject(Path("pyproject.toml"), text)), ("2.0.1", 3)
        )

    def test_skips_a_dynamic_version(self) -> None:
        # The build backend fills it in, so there is nothing to disagree with.
        text = '[project]\nname = "x"\ndynamic = ["version"]\n'
        self.assertEqual(read_pyproject(Path("pyproject.toml"), text), [])

    def test_survives_broken_toml(self) -> None:
        self.assertEqual(read_pyproject(Path("pyproject.toml"), "[project"), [])


class CargoTests(unittest.TestCase):
    def test_reads_the_package_table(self) -> None:
        text = '[package]\nname = "x"\nversion = "0.3.1"\n'
        self.assertEqual(only(read_cargo(Path("Cargo.toml"), text)), ("0.3.1", 3))

    def test_skips_an_inherited_version(self) -> None:
        text = '[package]\nname = "x"\nversion.workspace = true\n'
        self.assertEqual(read_cargo(Path("Cargo.toml"), text), [])

    def test_reads_the_workspace_root(self) -> None:
        text = '[workspace.package]\nversion = "0.3.1"\n'
        self.assertEqual(only(read_cargo(Path("Cargo.toml"), text)), ("0.3.1", 2))


class PackageJsonTests(unittest.TestCase):
    def test_reads_the_version(self) -> None:
        text = '{\n  "name": "x",\n  "version": "1.4.0"\n}\n'
        self.assertEqual(
            only(read_package_json(Path("package.json"), text)), ("1.4.0", 3)
        )

    def test_skips_a_file_without_one(self) -> None:
        self.assertEqual(read_package_json(Path("package.json"), '{"name": "x"}'), [])

    def test_skips_the_semantic_release_placeholder(self) -> None:
        text = '{"version": "0.0.0-development"}'
        self.assertEqual(read_package_json(Path("package.json"), text), [])


class SetupCfgTests(unittest.TestCase):
    def test_reads_the_metadata_section(self) -> None:
        text = "[metadata]\nname = x\nversion = 1.4.0\n"
        self.assertEqual(only(read_setup_cfg(Path("setup.cfg"), text)), ("1.4.0", 3))

    def test_skips_an_indirect_version(self) -> None:
        text = "[metadata]\nversion = attr: mypkg.__version__\n"
        self.assertEqual(read_setup_cfg(Path("setup.cfg"), text), [])


class ChartTests(unittest.TestCase):
    def test_reads_the_chart_version_not_the_app_version(self) -> None:
        text = "apiVersion: v2\nname: x\nversion: 1.4.0\nappVersion: 9.9.9\n"
        self.assertEqual(only(read_chart(Path("Chart.yaml"), text)), ("1.4.0", 3))


class DunderTests(unittest.TestCase):
    def test_reads_a_module_level_assignment(self) -> None:
        text = '"""Doc."""\n\n__version__ = "1.4.0"\n'
        self.assertEqual(only(read_dunder(Path("__init__.py"), text)), ("1.4.0", 3))

    def test_reads_an_annotated_assignment(self) -> None:
        text = '__version__: str = "1.4.0"\n'
        self.assertEqual(only(read_dunder(Path("_version.py"), text)), ("1.4.0", 1))

    def test_ignores_one_nested_in_a_function(self) -> None:
        text = 'def f():\n    __version__ = "1.4.0"\n'
        self.assertEqual(read_dunder(Path("__init__.py"), text), [])

    def test_ignores_a_computed_value(self) -> None:
        text = "__version__ = metadata.version(__name__)\n"
        self.assertEqual(read_dunder(Path("__init__.py"), text), [])

    def test_survives_a_syntax_error(self) -> None:
        self.assertEqual(read_dunder(Path("__init__.py"), "def ("), [])


class ChangelogTests(unittest.TestCase):
    def test_reads_the_bracketed_spelling(self) -> None:
        text = "# Changelog\n\n## [1.4.0] - 2026-08-18\n\n## [1.3.0] - 2026-01-01\n"
        found = read_changelog(Path("CHANGELOG.md"), text)
        self.assertEqual(
            (found.declaration.version, found.declaration.line), ("1.4.0", 3)
        )
        self.assertFalse(found.has_unreleased)

    def test_reads_the_bare_spelling(self) -> None:
        text = "# Changelog\n\n## 1.4.0 - 2026-08-18\n"
        found = read_changelog(Path("CHANGELOG.md"), text)
        self.assertEqual(found.declaration.version, "1.4.0")

    def test_notes_an_unreleased_section_and_skips_past_it(self) -> None:
        text = "## [Unreleased]\n\n## [1.3.0] - 2026-01-01\n"
        found = read_changelog(Path("CHANGELOG.md"), text)
        self.assertTrue(found.has_unreleased)
        self.assertEqual(found.declaration.version, "1.3.0")

    def test_strips_a_v_prefix(self) -> None:
        found = read_changelog(Path("CHANGELOG.md"), "## v1.4.0\n")
        self.assertEqual(found.declaration.version, "1.4.0")

    def test_ignores_headings_inside_a_code_fence(self) -> None:
        text = "```\n## [9.9.9]\n```\n\n## [1.4.0] - 2026-08-18\n"
        found = read_changelog(Path("CHANGELOG.md"), text)
        self.assertEqual(found.declaration.version, "1.4.0")

    def test_copes_with_no_release_at_all(self) -> None:
        found = read_changelog(Path("CHANGELOG.md"), "# Changelog\n\n## [Unreleased]\n")
        self.assertIsNone(found.declaration)
        self.assertTrue(found.has_unreleased)


if __name__ == "__main__":
    unittest.main()
