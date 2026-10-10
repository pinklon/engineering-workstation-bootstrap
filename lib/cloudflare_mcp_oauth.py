#!/usr/bin/env python3
"""Secret-free Cloudflare MCP OAuth startup diagnosis for managed Codex hosts.

This does not read OAuth stores, grant new scopes, refresh tokens, or mutate MCP
configuration. A transport being configured is not evidence of valid OAuth.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

SERVERS = {
    "cloudflare-api": "mcp.cloudflare.com",
    "cloudflare-observability": "observability.mcp.cloudflare.com",
}
SCHEMA = "ghostmesh-cloudflare-mcp-oauth-diagnostic-v1"


def classify(text: str) -> str:
    s = text.lower()
    if any(x in s for x in ("invalid_grant", "invalid_token", "refresh token was rejected",
                            "token is not active", "oauth authorization required")):
        return "REAUTH_REQUIRED"
    if any(x in s for x in ("invalid_client", "client registration failed")):
        return "CLIENT_REGISTRATION_REQUIRED"
    if any(x in s for x in ("connection timed out", "connection refused",
                            "timeout", "temporarily unavailable", "http 502",
                            "http 503", "http 504", "dns failure")):
        return "RETRYABLE_PROVIDER_FAILURE"
    if any(x in s for x in ("oauth", "authrequired", "authorization required", "unauthorized")):
        return "AUTH_UNVERIFIED"
    return "NO_AUTH_FAILURE_OBSERVED"


def inventory(codex: str, timeout: int = 12) -> list[dict]:
    completed = subprocess.run([codex, "mcp", "list", "--json"],
                               text=True, capture_output=True, timeout=timeout, check=False)
    if completed.returncode:
        raise RuntimeError("Codex MCP metadata inventory failed; no credentials were read")
    items = json.loads(completed.stdout)
    if not isinstance(items, list):
        raise ValueError("Codex MCP inventory format is not supported")
    result = []
    by_name = {x.get("name"): x for x in items if isinstance(x, dict)}
    for name, expected_host in SERVERS.items():
        item = by_name.get(name)
        row = {"connector": name, "endpoint_host": expected_host,
               "state": "UNAVAILABLE", "configured": False, "enabled": False,
               "reconnect_command": "codex mcp login " + name}
        if item is not None:
            url = (item.get("transport") or {}).get("streamable_http", {}).get("url")
            # Codex may use another transport serialization; normalize without copying URLs.
            if url is None:
                t = item.get("transport")
                if isinstance(t, dict):
                    for v in t.values():
                        if isinstance(v, dict) and isinstance(v.get("url"), str):
                            url = v["url"]
                            break
            if url is None and isinstance(item.get("transport"), dict):
                url = item["transport"].get("url")
            host = urlsplit(url).hostname if isinstance(url, str) else None
            row["configured"] = True
            row["enabled"] = bool(item.get("enabled"))
            row["state"] = ("WRONG_ENDPOINT" if host and host != expected_host
                            else "POLICY_DISABLED" if not row["enabled"]
                            else "CONFIGURED_AUTH_UNVERIFIED")
        result.append(row)
    return result


def report(codex: str, startup_log: Path | None) -> dict:
    rows = inventory(codex)
    outcome = "NO_STARTUP_LOG"
    if startup_log:
        if not startup_log.is_file() or startup_log.stat().st_size > 1048576:
            raise ValueError("startup log must be an existing file no larger than 1 MiB")
        content = startup_log.read_text(encoding="utf-8", errors="replace")
        for row in rows:
            # Only a matching connector name's log lines can classify its state.
            lines = [line for line in content.splitlines()
                     if row["connector"] in line.lower() or
                     (row["connector"] == "cloudflare-api" and
                      "mcp.cloudflare.com" in line.lower()) or
                     (row["connector"] == "cloudflare-observability" and
                      "observability.mcp.cloudflare.com" in line.lower())]
            failure = classify("\n".join(lines))
            if failure != "NO_AUTH_FAILURE_OBSERVED" and row["state"] == "CONFIGURED_AUTH_UNVERIFIED":
                row["state"] = failure
        outcome = "LOG_CLASSIFIED_NOT_AUTH_CANARY"
    for row in rows:
        row["next_action"] = (
            "Reauthorize once in an owner-interactive Terminal; run a fresh read-only canary"
            if row["state"] == "REAUTH_REQUIRED" else
            "Review OAuth client registration with provider; do not delete credential store"
            if row["state"] == "CLIENT_REGISTRATION_REQUIRED" else
            "Retry with bounded backoff; retain existing OAuth credentials"
            if row["state"] == "RETRYABLE_PROVIDER_FAILURE" else
            "Inspect endpoint/profile before authentication"
            if row["state"] == "WRONG_ENDPOINT" else
            "Do not infer authenticated from configuration; qualify an actual read-only canary"
        )
    return {"schema": SCHEMA, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "surface": "local-codex-cli", "scope": outcome, "secret_values": False,
            "oauth_credential_store_inspected": False, "provider_mutation": False,
            "connectors": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "reconnect-help"])
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--startup-log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "reconnect-help":
        print("In an owner-interactive Mac Terminal, finish active Codex sessions, then:")
        for name in SERVERS:
            print("  codex mcp login " + name)
        print("Complete each Cloudflare browser consent flow. Do not paste tokens.")
        print("Then start a fresh Codex session and verify read-only tool calls.")
        return 0
    try:
        data = report(args.codex, args.startup_log)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print("UNAVAILABLE: " + type(exc).__name__ + " (no credential or config changes)", file=sys.stderr)
        return 2
    encoded = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            print("REFUSE: destination already exists; receipt must be immutable", file=sys.stderr)
            return 3
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(encoded)
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
