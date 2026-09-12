"""Provision and inspect a bounded Linux cloud tool profile without account enrollment."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from cloud_apt import prepare_apt_profile

ROOT = Path(__file__).resolve().parents[1]


def probe(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        output = (result.stdout or result.stderr).splitlines()
        return result.returncode == 0, output[0][:300] if output else ""
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def run(command, env=None):
    subprocess.run(command, check=True, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "setup", "maintenance", "doctor"])
    parser.add_argument("--state-root", type=Path, default=Path(os.environ.get(
        "WORKSTATION_CLOUD_ROOT", str(Path.home() / ".local/share/engineering-workstation-bootstrap/cloud"))))
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifests/cloud.json").read_text())
    packages = manifest["packages"]
    missing = [item["package"] for item in packages if not shutil.which(item["command"])]
    if args.mode == "plan":
        print(json.dumps({"profile": manifest["profile"], "missingPackages": missing,
                          "nodeMajor": manifest["nodeMajor"], "pythonMinor": manifest["pythonMinor"],
                          "pendingCapabilities": manifest["pendingCapabilities"]}, indent=2))
        return 0

    args.state_root.mkdir(parents=True, exist_ok=True)
    receipt_path = args.state_root / "readiness.json"
    # Never leave an older PASS as the latest result after a failed attempt.
    receipt_path.write_text(json.dumps({"schemaVersion": 1, "result": "incomplete",
        "liveCloudCommissioned": False, "publicationCleared": False, "secretValues": False}) + "\n")

    if platform.system() != "Linux":
        raise SystemExit("Cloud provisioning requires a supported Ubuntu container.")
    os_release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    if os_release.get("ID", "").strip('"') != "ubuntu" or os_release.get("VERSION_ID", "").strip('"') not in manifest["supportedUbuntu"]:
        raise SystemExit("Use a qualified Ubuntu image version declared in manifests/cloud.json.")

    checks = []

    def record(name, passed, version="", path=""):
        checks.append({"capability": name, "state": "ready" if passed else "failed",
                       "version": version if passed else "", "executable": path})
        print(("PASS  " if passed else "FAIL  ") + name + ((": " + version) if passed and version else ""))

    python_ok = f"{sys.version_info.major}.{sys.version_info.minor}" == manifest["pythonMinor"]
    record("python-runtime", python_ok, platform.python_version(), sys.executable)
    node_ok, node_version = probe(["node", "--version"])
    node_ok = node_ok and node_version.split(".")[0] == "v" + str(manifest["nodeMajor"])
    record("node-runtime", node_ok, node_version, shutil.which("node") or "")
    if not (python_ok and node_ok):
        raise SystemExit("Select the declared Python/Node versions in the cloud image settings. No packages were changed.")

    apt_config = None
    if args.mode in ("setup", "maintenance"):
        apt_config = prepare_apt_profile(args.state_root)
        if apt_config:
            print("Bootstrap package operations exclude the unused LLVM source; global APT sources and signature checks are unchanged.")

    if args.mode in ("setup", "maintenance") and missing:
        prefix = [] if os.geteuid() == 0 else ["sudo", "-n"]
        if prefix and not probe(prefix + ["true"])[0]:
            raise SystemExit("Missing OS packages require provisioning with noninteractive administrator access: " + ", ".join(missing))
        apt_env = ["env", "APT_CONFIG=" + str(apt_config)] if apt_config else []
        run(prefix + apt_env + ["apt-get", "update"])
        run(prefix + apt_env + ["apt-get", "install", "--yes", "--no-install-recommends"] + missing)

    for item in packages:
        passed, version = probe([item["command"]] + item["versionArgs"])
        record(item["command"], passed, version, shutil.which(item["command"]) or "")
        package_ok, package_version = probe(["dpkg-query", "-W", "-f=${Version}", item["package"]])
        checks[-1]["osPackageVersion"] = package_version if package_ok else "not-owned-by-image-package"
        executable = shutil.which(item["command"])
        if executable:
            try:
                checks[-1]["executableSha256"] = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
            except OSError:
                checks[-1]["executableSha256"] = "unreadable"

    env = os.environ.copy()
    env["WORKSTATION_BOOTSTRAP_BROWSER_ROOT"] = str(args.state_root.resolve() / "browser")
    env["WORKSTATION_BROWSER_PYTHON"] = sys.executable
    env["WORKSTATION_BROWSER_INSTALL_DEPS"] = "1"
    if apt_config:
        env["APT_CONFIG"] = str(apt_config)
    browser_command = ["bash", str(ROOT / "bootstrap/configure-browser-gate.sh")]
    browser_ok = False
    if all(item["state"] == "ready" for item in checks):
        if args.mode in ("setup", "maintenance"):
            run(browser_command + ["setup"], env=env)
        result = subprocess.run(browser_command + ["--check"], env=env, check=False)
        browser_ok = result.returncode == 0
    record("locked-browser-startup", browser_ok)

    agents = []
    for command in manifest["optionalAgentCommands"]:
        passed, version = probe([command, "--version"])
        agents.append({"command": command, "state": "executable-only" if passed else "unavailable",
                       "version": version if passed else "", "authenticated": "not-tested"})

    receipt = {"schemaVersion": 1, "profile": manifest["profile"],
               "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "manifestSha256": hashlib.sha256((ROOT / "manifests/cloud.json").read_bytes()).hexdigest(),
               "browserLockSha256": hashlib.sha256((ROOT / "manifests/browser-requirements.txt").read_bytes()).hexdigest(),
               "result": "pass" if all(item["state"] == "ready" for item in checks) else "fail",
               "checks": checks, "agents": agents, "pendingCapabilities": manifest["pendingCapabilities"],
               "liveCloudCommissioned": False, "publicationCleared": False, "secretValues": False}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print("Receipt: " + str(receipt_path))
    print("This proves local container tool readiness only. Account access, effective permissions and publication clearance are separate.")
    return 0 if receipt["result"] == "pass" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit("Provisioning command failed with exit " + str(error.returncode) + ". Prior browser runtime remains intact.") from None
