#!/usr/bin/env python3
"""Check the source contract shared by the Cloud installer and hosted template."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = "/workspace/.codex-node/env.sh"


def check(script: str, guide: str, template: dict, manifest: dict) -> None:
    major = manifest["nodeMajor"]
    assert type(major) is int and major > 0
    assert template["runtime_manifest"] == "manifests/cloud.json"
    assert template["node_selection"] == "manifest-nodeMajor-via-workstation-cloud-node"
    assert template["setup"][0] == "bash bin/workstation-cloud-node"
    assert template["maintenance"][0] == "bash bin/workstation-cloud-node"
    assert template["environment_variables"]["BASH_ENV"] == ENV_FILE
    assert f"`BASH_ENV={ENV_FILE}`" in guide
    assert f"`NODE_SETUP_PASS major={major}`" in guide
    assert '"$ROOT/manifests/cloud.json"' in script
    assert '["nodeMajor"]' in script
    assert f"> {ENV_FILE}" in script
    assert f"line = '. {ENV_FILE}'" in script
    assert f"export BASH_ENV={ENV_FILE}" in script
    assert "node --version" in script
    assert "printf 'NODE_SETUP_PASS major=%s\\n' \"$NODE_MAJOR\"" in script
    assert "/workspace/.codex-node24/" not in script + guide + json.dumps(template)


def main() -> None:
    script = (ROOT / "bin/workstation-cloud-node").read_text()
    guide = (ROOT / "docs/CLOUD-SETUP.md").read_text()
    template = json.loads((ROOT / "manifests/connector-hosted-template.json").read_text())
    manifest = json.loads((ROOT / "manifests/cloud.json").read_text())
    check(script, guide, template, manifest)

    changed = json.loads(json.dumps(template))
    changed["environment_variables"]["BASH_ENV"] = "/workspace/.codex-node24/env.sh"
    try:
        check(script, guide, changed, manifest)
    except AssertionError:
        pass
    else:
        raise AssertionError("hosted BASH_ENV drift went undetected")

    print("PASS: Cloud installer, guide, and hosted template agree")


if __name__ == "__main__":
    main()
