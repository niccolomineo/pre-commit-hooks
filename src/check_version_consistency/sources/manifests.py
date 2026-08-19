"""Package manifests, read with the parser each format deserves."""

from __future__ import annotations

import configparser
import json
import re
import tomllib
from pathlib import Path

from ..declaration import Declaration, locate_line, usable


def _declare(
    path: Path, text: str, version: object, key: str, detail: str
) -> list[Declaration]:
    if not usable(version):
        return []
    assert isinstance(version, str)
    return [
        Declaration(
            version=version,
            path=path,
            line=locate_line(text, key, version),
            detail=detail,
        )
    ]


def read_pyproject(path: Path, text: str) -> list[Declaration]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    project = data.get("project", {})
    if "version" in project.get("dynamic", []):
        # The build backend fills this in; there is nothing here to disagree.
        return []
    if "version" in project:
        return _declare(path, text, project["version"], "version", "[project].version")
    poetry = data.get("tool", {}).get("poetry", {})
    return _declare(
        path, text, poetry.get("version"), "version", "[tool.poetry].version"
    )


def read_cargo(path: Path, text: str) -> list[Declaration]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    version = data.get("package", {}).get("version")
    if isinstance(version, dict):
        # version.workspace = true: the real value lives in the workspace root.
        version = None
    if version is None:
        version = data.get("workspace", {}).get("package", {}).get("version")
        detail = "[workspace.package].version"
    else:
        detail = "[package].version"
    return _declare(path, text, version, "version", detail)


def read_package_json(path: Path, text: str) -> list[Declaration]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    return _declare(path, text, data.get("version"), '"version"', "version")


def read_setup_cfg(path: Path, text: str) -> list[Declaration]:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    version = parser.get("metadata", "version", fallback=None)
    if version is not None and version.split(":")[0] in ("attr", "file"):
        # attr: pkg.__version__ and file: VERSION are dynamic.
        return []
    return _declare(path, text, version, "version", "[metadata] version")


_YAML_VERSION = re.compile(
    r"^version\s*:\s*[\"']?(?P<version>[^\"'\s#]+)", re.MULTILINE
)


def read_chart(path: Path, text: str) -> list[Declaration]:
    """Read a Helm chart's own version, not its appVersion."""
    match = _YAML_VERSION.search(text)
    if match is None:
        return []
    return _declare(path, text, match["version"], "version", "version")
