"""Validate the project version and an optional Git tag before packaging."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def project_version() -> tuple[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject_version = tomllib.load(handle)["project"]["version"]
    version_source = (ROOT / "lume" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', version_source, re.MULTILINE)
    if not match:
        raise ValueError("VERSION is missing from lume/version.py")
    return str(pyproject_version), match.group(1)


def tag_base_version(tag: str) -> str:
    value = tag.strip()
    if value.startswith("refs/tags/"):
        value = value.removeprefix("refs/tags/")
    if not value.startswith("v"):
        raise ValueError(f"release tag must start with v: {tag}")
    base = value[1:].split("-", 1)[0]
    if not re.fullmatch(r"\d+\.\d+\.\d+", base):
        raise ValueError(f"release tag has an invalid version: {tag}")
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="optional Git tag, for example v1.1.1")
    args = parser.parse_args()

    pyproject, source = project_version()
    if pyproject != source:
        print(f"version mismatch: pyproject.toml={pyproject}, lume/version.py={source}", file=sys.stderr)
        return 1
    if args.tag and tag_base_version(args.tag) != pyproject:
        print(f"tag {args.tag} does not match project version {pyproject}", file=sys.stderr)
        return 1
    print(pyproject)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
