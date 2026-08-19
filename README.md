<img src="https://raw.githubusercontent.com/niccolomineo/django-temporal-inputs/main/icon.png" alt="django-temporal-inputs" width="128">

# pre-commit-hooks

Two [pre-commit](https://pre-commit.com) hooks for the kind of drift that no test
fails on. Nothing breaks when a new environment variable never reaches
`.env.example`, or when `pyproject.toml` and `__init__.py` stop agreeing on the
version — you find out from a teammate's afternoon, or from the release.

Both hooks work offline, have no runtime dependencies, and need no configuration
to start being useful.

```yaml
repos:
  - repo: https://github.com/niccolomineo/pre-commit-hooks
    rev: v0.1.0
    hooks:
      - id: check-env-example
      - id: check-version-consistency
```

## `check-env-example`

Every environment variable your code reads must be documented in `.env.example`,
and every variable in `.env.example` must be read by something. Both directions,
across Python, JavaScript/TypeScript, Go, Rust, Ruby, PHP, Compose files and
Dockerfiles.

```console
check .env.example is in sync with the code..............................Failed
- hook id: check-env-example
- exit code: 1

Read by the code, missing from .env.example:
  DATABASE_POOL_SIZE  web/lib/db.ts:8
  STRIPE_SECRET_KEY   api/settings.py:14  (+2 more)

In .env.example, never read by the code:
  LEGACY_SMTP_HOST    .env.example:22

2 missing, 1 unused
```

Python is parsed with `ast`, so commented-out code and lookalike strings never
produce a finding. → [Full documentation](docs/check-env-example.md)

## `check-version-consistency`

Every version a project declares — in its manifests, in a module-level
`__version__`, in the changelog — compared against the others.

```console
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
→ [Full documentation](docs/check-version-consistency.md)

## Why both hooks discover their own files

Each declares `pass_filenames: false` and finds the project's files itself, from
git's index. That is deliberate, and it is the same reason in both cases: the
question they answer is only meaningful with the whole project in view. "Nothing
reads this variable" and "these numbers disagree" cannot be decided from the
handful of files in one commit. As a result, a commit-time run and
`pre-commit run --all-files` in CI produce identical output.

## Requirements

Python 3.11 or newer. No runtime dependencies — [pre-commit](https://pre-commit.com)
and [prek](https://prek.j178.dev) both provision the interpreter themselves, so
nothing needs to be installed on your machine.

## License

MIT
