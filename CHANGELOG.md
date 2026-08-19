# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-19

### Added

#### `check-env-example`

- Report environment variables read by the code but absent from `.env.example`.
- Report variables documented in `.env.example` that nothing reads.
- Report keys declared twice in the example file.
- Python sources parsed with `ast`; JavaScript, TypeScript, Go, Rust, Ruby, PHP
  and Dockerfiles matched by pattern.
- Compose files read for both `${VAR}` interpolation and the bare names listed
  under `environment:` and `args:`.
- Default allowlist for operating system, CI and well-known runtime variables,
  applied in both directions.
- `--extra-pattern` for framework helpers such as django-environ.
- `--fix`, appending missing variables with a `# used in path:line` comment.
- Inline `check-env-example: ignore` escape hatch on either side of the check.

#### `check-version-consistency`

- Compare the version declared in `pyproject.toml`, `Cargo.toml`,
  `package.json`, `manifest.json`, `setup.cfg`, `Chart.yaml`, a module-level
  `__version__` and the changelog.
- Skip declarations that are dynamic, inherited from a workspace or a `0.0.0`
  placeholder.
- Report the full picture, marking the declarations that disagree.
- `--changelog lenient` by default, allowing the changelog to lag while an
  `Unreleased` section is open but never to run ahead.
- `--canonical` to name the source of truth instead of following the majority.
- `--source GLOB:REGEX` for ecosystems that are not built in.
- `--check-tag`, failing when the latest git tag is ahead of the declared
  version.
- Inline `check-version-consistency: ignore` escape hatch.

[0.1.0]: https://github.com/niccolomineo/pre-commit-hooks/releases/tag/v0.1.0
