# check-version-consistency

A [pre-commit](https://pre-commit.com) hook for projects that state their
version in more than one place.

When `pyproject.toml` says 1.4.0 and `__init__.py` still says 1.3.2, nothing
fails — not the tests, not the build, not CI. You find out from the release.

```console
$ pre-commit run --all-files
check the project version is declared consistently.......................Failed
- hook id: check-version-consistency
- exit code: 1

The project declares 2 different versions:

  1.4.0  package.json:3           version
  1.4.0  pyproject.toml:3         [project].version
  1.3.2  src/pkg/__init__.py:1    __version__            <- disagrees
  1.3.2  CHANGELOG.md:5           ## [1.3.2] - 2026-02-11  <- behind, with no Unreleased section above it

Expected 1.4.0 everywhere.
```

Every declaration is listed, not only the failing ones: seeing that two sources
already say 1.4.0 is what tells you which side to fix.

## Why not just use a bumping tool

`commitizen` and `bump-my-version` will happily rewrite a list of
`version_files` for you — as long as every release goes through them. This hook
asks a different question, and asks it of the repository as it stands: *are
these numbers the same?* It does not care how they got there, it needs no
configuration to start working, and it keeps being true after someone edits a
version by hand.

## Usage

```yaml
repos:
  - repo: https://github.com/niccolomineo/pre-commit-hooks
    rev: v0.1.0
    hooks:
      - id: check-version-consistency
```

The hook declares `pass_filenames: false` and finds the manifests itself, from
git's index — comparing versions only means anything with all of them in view.
A commit-time run and `pre-commit run --all-files` in CI therefore produce
identical output.

A project with fewer than two declarations exits `0` in silence. There is
nothing to disagree with, and nothing to configure to say so.

## What it reads

| File | Where the version comes from | Skipped when |
|---|---|---|
| `pyproject.toml` | `[project].version`, or `[tool.poetry].version` | `dynamic = ["version"]` |
| `Cargo.toml` | `[package].version`, or `[workspace.package].version` | `version.workspace = true` |
| `package.json`, `manifest.json` | `version` | the key is absent |
| `setup.cfg` | `[metadata] version` | `attr:` or `file:` |
| `Chart.yaml` | the chart's `version`, never its `appVersion` | |
| `__init__.py`, `version.py`, `_version.py` | a module-level `__version__` | it is computed rather than literal |
| `CHANGELOG.md`, `CHANGES.md`, `HISTORY.md`, `NEWS.md` | the topmost released `##` heading | see below |

TOML, JSON, config and Python files are parsed rather than pattern-matched, and
`0.0.0` placeholders are ignored everywhere.

### The changelog

A changelog legitimately lags: you bump the version, then write the entry. The
default `--changelog lenient` allows exactly that, and no more — the topmost
released heading may sit *behind* the manifests while an `## [Unreleased]`
section is open above it, and may never run *ahead* of them.

`--changelog strict` requires an exact match; `--changelog off` stops reading
it. Headings inside a code fence are not mistaken for releases, and a leading
`v` is stripped.

## Options

| Flag | Effect |
|---|---|
| `--canonical PATH` | Name the source of truth instead of letting the majority decide |
| `--exclude GLOB` | Skip matching files; repeatable |
| `--source GLOB:REGEX` | Read a version from a format that is not built in; repeatable |
| `--ignore-value VERSION` | Treat a value as a placeholder; repeatable |
| `--changelog {strict,lenient,off}` | How much the changelog is allowed to lag |
| `--check-tag` | Also fail when the latest git tag is ahead of the declared version |
| `--quiet` | Print the summary line only |

Without `--canonical`, the expected value is the one most sources agree on,
with the first path alphabetically breaking a tie — so the answer never depends
on the order the filesystem handed the files over in.

Exit codes: `0` clean, `1` findings, `2` bad usage.

### Other ecosystems

`--source` covers the formats that are not built in, without the tool having to
know about any of them:

```yaml
- id: check-version-consistency
  args:
    - --source=pubspec.yaml:^version:\s*(?P<version>\S+)
    - --source=*.gemspec:\.version\s*=\s*["'](?P<version>[^"']+)
```

### Escape hatch

Put `check-version-consistency: ignore` in a comment on the line:

```python
__version__ = "0.0.0"  # check-version-consistency: ignore
```

## Monorepos

One version per repository is the assumption. For several independently
versioned packages, declare the hook once per package and scope each with
`--exclude`:

```yaml
- id: check-version-consistency
  name: check api version
  args: [--exclude=web/*]
- id: check-version-consistency
  alias: check-version-consistency-web
  name: check web version
  args: [--exclude=api/*]
```

## Requirements

Python 3.11 or newer, for `tomllib`. No runtime dependencies — pre-commit and
[prek](https://prek.j178.dev) both provision the interpreter themselves.

## License

MIT
