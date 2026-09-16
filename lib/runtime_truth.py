#!/usr/bin/env python3
"""Verify that every managed-runtime declaration agrees with mise.toml."""

import argparse
import json
from pathlib import Path
import re
import sys
import tomllib


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()

    tools = tomllib.loads((root / "mise.toml").read_text(encoding="utf-8"))["tools"]
    expected = {"node": str(tools["node"]), "python": str(tools["python"])}
    cloud = json.loads((root / "manifests/cloud.json").read_text(encoding="utf-8"))
    homebrew = json.loads((root / "manifests/homebrew.json").read_text(encoding="utf-8"))
    brewfile = (root / "Brewfile").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/validate.yml").read_text(encoding="utf-8")

    package_names = {item["name"] for item in homebrew["packages"] if item["kind"] == "brew"}
    actual = {
        "manifests/cloud.json nodeMajor": str(cloud["nodeMajor"]),
        "manifests/cloud.json pythonMinor": str(cloud["pythonMinor"]),
        "manifests/homebrew.json Node formula": _formula_version(package_names, "node"),
        "manifests/homebrew.json Python formula": _formula_version(package_names, "python"),
        "Brewfile Node formula": _quoted_version(brewfile, "node"),
        "Brewfile Python formula": _quoted_version(brewfile, "python"),
        ".github/workflows/validate.yml node-version": _yaml_version(workflow, "node-version"),
        ".github/workflows/validate.yml python-version": _yaml_version(workflow, "python-version"),
    }
    expected_for = {
        key: expected["node"] if "node" in key.lower() else expected["python"]
        for key in actual
    }
    errors = [
        f"{key} is {value!r}; expected {expected_for[key]!r} from mise.toml"
        for key, value in actual.items()
        if value != expected_for[key]
    ]
    if errors:
        print("FAIL: managed runtime declarations have drifted:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"PASS: managed runtime truth is Node {expected['node']} and Python {expected['python']}")
    return 0


def _formula_version(names: set[str], runtime: str) -> str:
    matches = sorted(name.removeprefix(runtime + "@") for name in names if name.startswith(runtime + "@"))
    return matches[0] if len(matches) == 1 else ",".join(matches)


def _quoted_version(text: str, runtime: str) -> str:
    matches = re.findall(rf'^brew "{runtime}@([^"]+)"$', text, flags=re.MULTILINE)
    return matches[0] if len(matches) == 1 else ",".join(matches)


def _yaml_version(text: str, key: str) -> str:
    matches = re.findall(rf"^\s*{re.escape(key)}:\s*['\"]?([^'\"\s]+)", text, flags=re.MULTILINE)
    return matches[0] if len(matches) == 1 else ",".join(matches)


if __name__ == "__main__":
    raise SystemExit(main())
