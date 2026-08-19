"""Decide which of the collected declarations are wrong."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from . import semver
from .declaration import Declaration
from .sources import Collected


@dataclass(frozen=True, slots=True)
class Finding:
    declaration: Declaration
    message: str


@dataclass(frozen=True, slots=True)
class Report:
    expected: str | None
    declarations: tuple[Declaration, ...]
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings


def _expected(
    manifests: Sequence[Declaration], canonical: str | None
) -> tuple[str | None, Declaration | None]:
    """Pick the value everything else has to match."""
    if canonical is not None:
        for declaration in manifests:
            if declaration.path.as_posix() == canonical:
                return declaration.version, declaration
    if not manifests:
        return None, None
    # No canonical source named: the value most sources agree on wins, and the
    # first one in path order breaks a tie, so the answer never depends on the
    # order the filesystem happened to hand files over in.
    counts = Counter(declaration.version for declaration in manifests)
    best = max(
        counts.items(), key=lambda item: (item[1], -_first_index(manifests, item[0]))
    )
    return best[0], None


def _first_index(manifests: Sequence[Declaration], version: str) -> int:
    return next(
        index
        for index, declaration in enumerate(manifests)
        if declaration.version == version
    )


def check(
    collected: Collected,
    *,
    canonical: str | None = None,
    changelog_mode: str = "lenient",
    tag: str | None = None,
) -> Report:
    """Compare every declaration and return what does not line up."""
    manifests = sorted(collected.manifests, key=lambda item: item.path.as_posix())
    changelog = collected.changelog
    changelog_declaration = (
        changelog.declaration
        if changelog is not None and changelog_mode != "off"
        else None
    )

    declarations = tuple(manifests) + (
        (changelog_declaration,) if changelog_declaration is not None else ()
    )
    if len(declarations) < 2:
        # Nothing to disagree with.
        return Report(expected=None, declarations=declarations, findings=())

    expected, canonical_declaration = _expected(manifests, canonical)
    if expected is None:
        return Report(expected=None, declarations=declarations, findings=())

    findings: list[Finding] = []
    for declaration in manifests:
        if declaration.version != expected:
            findings.append(
                Finding(
                    declaration=declaration,
                    message=(
                        f"disagrees with {canonical_declaration.path}"
                        if canonical_declaration is not None
                        else "disagrees"
                    ),
                )
            )

    if changelog_declaration is not None and changelog_declaration.version != expected:
        behind = semver.is_behind(changelog_declaration.version, expected)
        lenient_release_in_progress = (
            changelog_mode == "lenient"
            and behind
            and changelog is not None
            and changelog.has_unreleased
        )
        if not lenient_release_in_progress:
            findings.append(
                Finding(
                    declaration=changelog_declaration,
                    message=(
                        "ahead of the manifests"
                        if not behind
                        else "behind, with no Unreleased section above it"
                        if changelog_mode == "lenient"
                        else "behind"
                    ),
                )
            )

    if tag is not None and semver.is_behind(expected, tag):
        findings.append(
            Finding(
                declaration=Declaration(
                    version=tag, path=Path("(git tag)"), line=0, detail="git describe"
                ),
                message="a released tag is ahead of the declared version",
            )
        )

    return Report(
        expected=expected, declarations=declarations, findings=tuple(findings)
    )
