# check-env-example

A [pre-commit](https://pre-commit.com) hook that keeps `.env.example` honest.

Every environment variable your code reads must be documented in `.env.example`,
and every variable in `.env.example` must be read by something. Both directions
are checked, offline, with no dependencies.

```console
$ pre-commit run --all-files
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

## Why

Forgetting to add a new variable to `.env.example` costs the next person on the
project half an hour, and there is no test that catches it: the app works fine
for you, because your own `.env` has the value.

[`clean-dotenv`](https://github.com/hija/clean-dotenv) solves the mirror problem
— it generates `.env.example` from your local `.env`. That file is gitignored,
so in CI there is nothing to generate from. This hook works the other way round:
it reads your *code*, which is right there in the repository, and is therefore
just as meaningful on a developer's machine as in a pipeline.

## Usage

```yaml
repos:
  - repo: https://github.com/niccolomineo/pre-commit-hooks
    rev: v0.1.0
    hooks:
      - id: check-env-example
```

The hook declares `pass_filenames: false` and discovers the project's files
itself, from git's index. That is deliberate: the "never read by the code" half
of the check is only correct when the whole project is in view. As a result a
commit-time run and `pre-commit run --all-files` in CI produce identical output.

## What counts as reading a variable

| Files | Recognised |
|---|---|
| `.py` | `os.environ["X"]`, `os.environ.get/setdefault/pop("X")`, `os.getenv("X")` |
| `.js .jsx .mjs .cjs .ts .tsx .mts .cts .vue .svelte .astro` | `process.env.X`, `process.env["X"]`, `import.meta.env.X`, `Deno.env.get("X")`, `Bun.env.X` |
| `.go` | `os.Getenv("X")`, `os.LookupEnv("X")` |
| `.rs` | `env::var("X")`, `env::var_os("X")` |
| `.rb` | `ENV["X"]`, `ENV.fetch("X")` |
| `.php` | `getenv('X')`, `$_ENV['X']` |
| `compose*.y{a}ml`, `docker-compose*.y{a}ml` | `${X}` interpolation, and bare names under `environment:` / `args:` |
| `Dockerfile*`, `*.Dockerfile`, `Containerfile*` | `ARG X` with no default |

Python is parsed with `ast` rather than matched with a regular expression, so
commented-out code and lookalike strings never produce a finding. For the other
languages a line that opens with a comment marker is skipped.

Compose gets its own reader, because it takes a variable from the host in two
unrelated ways. Alongside `${VAR}` interpolation, a bare name in a list —

```yaml
    environment:
      - DATABASE_URL      # read from the host
      - DEBUG=1           # set here, not read
```

— means "pass mine through", and carries no `$` for a pattern to latch onto.
`$${VAR}` is correctly left alone: it reaches the container as a literal.

### The allowlist

Variables that the operating system, the shell, the CI runner or a well-known
runtime supplies — `PATH`, `HOME`, `CI`, `NODE_ENV`, `PYTHONDEVMODE`,
`COMPOSE_FILE`, `GITHUB_*` — are allowed by default.

Allowed means the tool holds no opinion in *either* direction: documenting
`PYTHONDEVMODE` so a teammate knows to set it is no more of an error than
leaving it out, and no line of code will ever read it. `--ignore VAR` adds to
the same list, and `--no-default-allowlist` empties it.

### Framework helpers

Libraries that wrap the lookup are covered with `--extra-pattern`, so the hook
stays unopinionated about which one you use:

```yaml
- id: check-env-example
  args:
    # django-environ
    - --extra-pattern=.py:env(?:\.\w+)?\(\s*["'](?P<var>[A-Z0-9_]+)["']
```

```yaml
    # python-decouple
    - --extra-pattern=.py:config\(\s*["'](?P<var>[A-Z0-9_]+)["']
```

```yaml
    # any Vite-style prefix in a file type not scanned by default
    - --extra-pattern=.svelte:PUBLIC_(?P<var>[A-Z0-9_]+)
```

The expression must contain a `(?P<var>...)` group. Extra patterns are applied
on top of the built-in ones, not instead of them.

## Options

| Flag | Effect |
|---|---|
| `--example-file PATH` | Use this file instead of auto-discovering it |
| `--ignore VAR` | Never report this variable; repeatable |
| `--exclude GLOB` | Skip matching files; repeatable |
| `--extra-pattern EXT:REGEX` | Add a pattern for one extension; repeatable |
| `--no-unused` | Only check that used variables are documented |
| `--no-default-allowlist` | Report the OS and CI variables too |
| `--fix` | Append the missing variables to the example file |
| `--quiet` | Print the summary line only |

`--fix` appends `VAR=` with a `# used in path:line` comment, never touches an
existing value and never reorders the file. Like other fixing hooks it still
exits non-zero, so the modified file gets staged deliberately.

Exit codes: `0` clean, `1` findings, `2` bad usage.

### Escape hatches

Put `check-env-example: ignore` in a comment on the line, on either side:

```python
value = os.getenv("INTERNAL_ONLY")  # check-env-example: ignore
```

```dotenv
CONSUMED_BY_THE_PROXY=  # check-env-example: ignore
```

When no `.env.example`, `.env.sample`, `.env.template` or `env.example` exists,
the hook exits `0` without a word — a project that does not use one is not in
violation of anything.

## Monorepos

Declare the hook once per package, each with its own scope:

```yaml
- id: check-env-example
  name: check api/.env.example
  args: [--example-file=api/.env.example, --exclude=web/*]
- id: check-env-example
  alias: check-env-example-web
  name: check web/.env.example
  args: [--example-file=web/.env.example, --exclude=api/*]
```

## Requirements

Python 3.11 or newer. No runtime dependencies — pre-commit and
[prek](https://prek.j178.dev) both provision the interpreter themselves, so
nothing needs to be installed on your machine.

## License

MIT
