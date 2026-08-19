"""The extraction layer: what counts as reading an environment variable."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from check_env_example.extractors import extract, is_scannable


def variables(name: str, text: str, extra=None) -> list[str]:
    return [reference.var for reference in extract(Path(name), text, extra)]


class PythonExtractionTests(unittest.TestCase):
    def test_finds_every_supported_form(self) -> None:
        source = (
            "import os\n"
            'a = os.environ["SUBSCRIPT"]\n'
            'b = os.environ.get("GET")\n'
            'c = os.environ.setdefault("SETDEFAULT", "x")\n'
            'd = os.environ.pop("POP")\n'
            'e = os.getenv("GETENV")\n'
            "from os import environ, getenv\n"
            'f = environ["BARE_SUBSCRIPT"]\n'
            'g = getenv("BARE_GETENV")\n'
        )
        self.assertEqual(
            variables("settings.py", source),
            [
                "SUBSCRIPT",
                "GET",
                "SETDEFAULT",
                "POP",
                "GETENV",
                "BARE_SUBSCRIPT",
                "BARE_GETENV",
            ],
        )

    def test_reports_the_real_line(self) -> None:
        source = 'import os\n\n\nvalue = os.getenv("LATE")\n'
        [reference] = extract(Path("settings.py"), source)
        self.assertEqual(reference.line, 4)

    def test_ignores_commented_out_code(self) -> None:
        source = 'import os\n# value = os.getenv("COMMENTED")\n'
        self.assertEqual(variables("settings.py", source), [])

    def test_ignores_a_non_literal_name(self) -> None:
        source = "import os\nvalue = os.getenv(name)\n"
        self.assertEqual(variables("settings.py", source), [])

    def test_survives_a_syntax_error(self) -> None:
        self.assertEqual(variables("broken.py", "def ("), [])

    def test_honours_the_inline_marker(self) -> None:
        source = 'import os\nv = os.getenv("SKIPPED")  # check-env-example: ignore\n'
        self.assertEqual(variables("settings.py", source), [])


class JavaScriptExtractionTests(unittest.TestCase):
    def test_finds_every_supported_form(self) -> None:
        source = (
            "const a = process.env.DOTTED;\n"
            'const b = process.env["BRACKET"];\n'
            "const c = import.meta.env.VITE_ONE;\n"
            'const d = Deno.env.get("DENO_ONE");\n'
            "const e = Bun.env.BUN_ONE;\n"
        )
        self.assertEqual(
            variables("app.ts", source),
            ["DOTTED", "BRACKET", "VITE_ONE", "DENO_ONE", "BUN_ONE"],
        )

    def test_ignores_a_commented_line(self) -> None:
        self.assertEqual(variables("app.ts", "// process.env.GONE\n"), [])

    def test_covers_the_component_dialects(self) -> None:
        for name in ("app.vue", "app.svelte", "app.astro", "app.mjs", "app.cts"):
            with self.subTest(name=name):
                self.assertEqual(variables(name, "process.env.X\n"), ["X"])


class OtherLanguageTests(unittest.TestCase):
    def test_go(self) -> None:
        source = 'os.Getenv("ONE")\nos.LookupEnv("TWO")\n'
        self.assertEqual(variables("main.go", source), ["ONE", "TWO"])

    def test_rust(self) -> None:
        source = 'env::var("ONE").unwrap();\nenv::var_os("TWO");\n'
        self.assertEqual(variables("main.rs", source), ["ONE", "TWO"])

    def test_ruby(self) -> None:
        source = "a = ENV['ONE']\nb = ENV.fetch('TWO')\n"
        self.assertEqual(variables("app.rb", source), ["ONE", "TWO"])

    def test_php(self) -> None:
        source = "$a = getenv('ONE');\n$b = $_ENV['TWO'];\n"
        self.assertEqual(variables("app.php", source), ["ONE", "TWO"])


class ComposeTests(unittest.TestCase):
    def test_finds_pass_through_entries(self) -> None:
        # A bare name under environment: means "hand my value through", which
        # is a host read carrying no $ for a pattern to latch onto.
        source = (
            "services:\n"
            "  app:\n"
            "    build:\n"
            "      args:\n"
            "        - BUILD_TOKEN\n"
            "    environment:\n"
            "      - DATABASE_URL\n"
            '      - "QUOTED_URL"\n'
            "      - EXPLICIT=literal\n"
            "    ports:\n"
            "      - 8000:8000\n"
        )
        self.assertEqual(
            variables("compose.yaml", source),
            ["BUILD_TOKEN", "DATABASE_URL", "QUOTED_URL"],
        )

    def test_finds_pass_through_in_the_mapping_spelling(self) -> None:
        source = (
            "services:\n  app:\n    environment:\n      DATABASE_URL:\n      DEBUG: 1\n"
        )
        self.assertEqual(variables("compose.yaml", source), ["DATABASE_URL"])

    def test_the_block_ends_with_its_indentation(self) -> None:
        source = (
            "services:\n"
            "  app:\n"
            "    environment:\n"
            "      - INSIDE\n"
            "  other:\n"
            "    image: postgres\n"
        )
        self.assertEqual(variables("compose.yaml", source), ["INSIDE"])

    def test_finds_host_interpolation(self) -> None:
        source = (
            "services:\n"
            "  app:\n"
            "    image: ${IMAGE}\n"
            "    environment:\n"
            "      A: ${WITH_DEFAULT:-x}\n"
            "      B: ${REQUIRED:?missing}\n"
            "      C: ${DASH_DEFAULT-x}\n"
        )
        self.assertEqual(
            variables("compose.yaml", source),
            ["IMAGE", "WITH_DEFAULT", "REQUIRED", "DASH_DEFAULT"],
        )

    def test_skips_the_escaped_form(self) -> None:
        # $${VAR} reaches the container literally; the host never expands it.
        self.assertEqual(variables("compose.yaml", "    command: $${INSIDE}\n"), [])

    def test_matches_the_named_variants(self) -> None:
        for name in ("compose.yml", "docker-compose.yaml", "docker-compose.ci.yml"):
            with self.subTest(name=name):
                self.assertEqual(variables(name, "image: ${X}\n"), ["X"])


class DockerfileTests(unittest.TestCase):
    def test_flags_a_build_arg_without_a_default(self) -> None:
        self.assertEqual(variables("Dockerfile", "ARG NEEDED\n"), ["NEEDED"])

    def test_ignores_a_build_arg_with_a_default(self) -> None:
        # It is self-contained, so there is nothing anyone has to supply.
        self.assertEqual(variables("Dockerfile", "ARG PYTHON_VERSION=3.13\n"), [])

    def test_matches_the_named_variants(self) -> None:
        for name in ("Dockerfile.preprod", "app.Dockerfile", "Containerfile"):
            with self.subTest(name=name):
                self.assertEqual(variables(name, "ARG NEEDED\n"), ["NEEDED"])


class ExtraPatternTests(unittest.TestCase):
    def test_applies_on_top_of_the_python_parser(self) -> None:
        extra = {".py": [re.compile(r"""env\(["'](?P<var>[A-Z0-9_]+)["']""")]}
        source = 'import os\na = os.getenv("NATIVE")\nb = env("DJANGO_ENVIRON")\n'
        self.assertEqual(
            variables("settings.py", source, extra), ["NATIVE", "DJANGO_ENVIRON"]
        )


class DeduplicationTests(unittest.TestCase):
    def test_the_same_variable_twice_on_one_line_counts_once(self) -> None:
        source = "const pair = [process.env.SAME, process.env.SAME];\n"
        self.assertEqual(variables("app.ts", source), ["SAME"])


class ScannabilityTests(unittest.TestCase):
    def test_recognises_what_it_can_read(self) -> None:
        for name in ("a.py", "a.ts", "compose.yaml", "Dockerfile"):
            with self.subTest(name=name):
                self.assertTrue(is_scannable(Path(name)))

    def test_rejects_the_rest(self) -> None:
        for name in ("README.md", "logo.png", "styles.css"):
            with self.subTest(name=name):
                self.assertFalse(is_scannable(Path(name)))

    def test_an_extra_pattern_opens_a_new_extension(self) -> None:
        self.assertTrue(is_scannable(Path("run.sh"), {".sh": []}))


if __name__ == "__main__":
    unittest.main()
