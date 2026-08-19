"""The comparison rules, including the changelog's licence to lag."""

from __future__ import annotations

import unittest
from pathlib import Path

from check_version_consistency import semver
from check_version_consistency.checker import check
from check_version_consistency.declaration import Declaration
from check_version_consistency.sources import Collected
from check_version_consistency.sources.changelog import Changelog


def manifest(version: str, name: str) -> Declaration:
    return Declaration(version=version, path=Path(name), line=1, detail="version")


def changelog(version: str | None, *, unreleased: bool = False) -> Changelog:
    declaration = (
        Declaration(
            version=version,
            path=Path("CHANGELOG.md"),
            line=3,
            detail=f"## [{version}]",
            is_changelog=True,
        )
        if version is not None
        else None
    )
    return Changelog(declaration=declaration, has_unreleased=unreleased)


class AgreementTests(unittest.TestCase):
    def test_matching_manifests_pass(self) -> None:
        collected = Collected(
            manifests=(
                manifest("1.4.0", "pyproject.toml"),
                manifest("1.4.0", "package.json"),
            ),
            changelog=None,
        )
        self.assertTrue(check(collected).ok)

    def test_a_single_declaration_has_nothing_to_disagree_with(self) -> None:
        collected = Collected(
            manifests=(manifest("1.4.0", "pyproject.toml"),), changelog=None
        )
        self.assertTrue(check(collected).ok)

    def test_no_declaration_at_all_passes(self) -> None:
        self.assertTrue(check(Collected(manifests=(), changelog=None)).ok)


class DisagreementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collected = Collected(
            manifests=(
                manifest("1.4.0", "package.json"),
                manifest("1.4.0", "pyproject.toml"),
                manifest("1.3.2", "src/pkg/__init__.py"),
            ),
            changelog=None,
        )

    def test_the_majority_sets_the_expected_value(self) -> None:
        result = check(self.collected)
        self.assertEqual(result.expected, "1.4.0")
        self.assertEqual(
            [str(finding.declaration.path) for finding in result.findings],
            ["src/pkg/__init__.py"],
        )

    def test_canonical_overrides_the_majority(self) -> None:
        result = check(self.collected, canonical="src/pkg/__init__.py")
        self.assertEqual(result.expected, "1.3.2")
        self.assertEqual(len(result.findings), 2)

    def test_an_unknown_canonical_path_falls_back_to_the_majority(self) -> None:
        result = check(self.collected, canonical="nowhere.toml")
        self.assertEqual(result.expected, "1.4.0")

    def test_a_two_way_split_is_decided_by_path_order(self) -> None:
        collected = Collected(
            manifests=(
                manifest("2.0.0", "package.json"),
                manifest("1.0.0", "pyproject.toml"),
            ),
            changelog=None,
        )
        # Deterministic, so the answer never depends on filesystem order.
        self.assertEqual(check(collected).expected, "2.0.0")


class ChangelogRuleTests(unittest.TestCase):
    def collected(self, version, **kwargs):
        return Collected(
            manifests=(
                manifest("1.4.0", "pyproject.toml"),
                manifest("1.4.0", "package.json"),
            ),
            changelog=changelog(version, **kwargs),
        )

    def test_a_matching_changelog_passes(self) -> None:
        self.assertTrue(check(self.collected("1.4.0")).ok)

    def test_lenient_allows_lagging_while_a_release_is_open(self) -> None:
        result = check(
            self.collected("1.3.0", unreleased=True), changelog_mode="lenient"
        )
        self.assertTrue(result.ok)

    def test_lenient_still_rejects_lagging_with_no_unreleased_section(self) -> None:
        result = check(self.collected("1.3.0"), changelog_mode="lenient")
        self.assertFalse(result.ok)
        self.assertIn("Unreleased", result.findings[0].message)

    def test_lenient_never_allows_the_changelog_to_run_ahead(self) -> None:
        result = check(
            self.collected("1.5.0", unreleased=True), changelog_mode="lenient"
        )
        self.assertFalse(result.ok)
        self.assertIn("ahead", result.findings[0].message)

    def test_strict_requires_an_exact_match(self) -> None:
        result = check(
            self.collected("1.3.0", unreleased=True), changelog_mode="strict"
        )
        self.assertFalse(result.ok)

    def test_off_ignores_the_changelog_entirely(self) -> None:
        self.assertTrue(check(self.collected("0.1.0"), changelog_mode="off").ok)

    def test_the_changelog_alone_is_not_a_disagreement(self) -> None:
        collected = Collected(
            manifests=(manifest("1.4.0", "pyproject.toml"),),
            changelog=changelog("1.4.0"),
        )
        self.assertTrue(check(collected).ok)


class TagTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collected = Collected(
            manifests=(
                manifest("1.4.0", "pyproject.toml"),
                manifest("1.4.0", "package.json"),
            ),
            changelog=None,
        )

    def test_a_tag_behind_the_version_is_normal(self) -> None:
        self.assertTrue(check(self.collected, tag="1.3.0").ok)

    def test_a_tag_equal_to_the_version_is_normal(self) -> None:
        self.assertTrue(check(self.collected, tag="1.4.0").ok)

    def test_a_tag_ahead_of_the_version_is_a_finding(self) -> None:
        result = check(self.collected, tag="1.5.0")
        self.assertFalse(result.ok)
        self.assertIn("tag is ahead", result.findings[0].message)


class SemverTests(unittest.TestCase):
    def test_orders_releases(self) -> None:
        self.assertTrue(semver.is_behind("1.3.0", "1.4.0"))
        self.assertTrue(semver.is_behind("1.9.0", "1.10.0"))
        self.assertFalse(semver.is_behind("2.0.0", "1.4.0"))

    def test_trailing_zeros_do_not_decide_anything(self) -> None:
        self.assertFalse(semver.is_behind("1.4", "1.4.0"))
        self.assertFalse(semver.is_behind("1.4.0", "1.4"))

    def test_a_pre_release_comes_before_its_release(self) -> None:
        self.assertTrue(semver.is_behind("1.4.0rc1", "1.4.0"))
        self.assertTrue(semver.is_behind("1.4.0-rc.1", "1.4.0"))


if __name__ == "__main__":
    unittest.main()
