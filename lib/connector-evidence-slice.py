#!/usr/bin/env python3
"""Read a pinned local connector catalog and emit only requested evidence."""
import argparse
import hashlib
import json
import pathlib
import sys

DEFAULT_MAX_BYTES = 48 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="manifests/connector-capabilities.json")
    parser.add_argument("--id", action="append", required=True, dest="ids")
    parser.add_argument("--surface", action="append", required=True, dest="surfaces")
    parser.add_argument("--max-output-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()

    if args.max_output_bytes < 1 or len(args.ids) > 8 or len(args.surfaces) > 8:
        parser.error("positive byte limit and at most eight IDs/surfaces required")
    source = pathlib.Path(args.manifest)
    raw = source.read_bytes()
    manifest = json.loads(raw)
    connectors = manifest.get("connectors")
    if not isinstance(connectors, list):
        parser.error("invalid connector manifest")
    selected = []
    missing = []
    by_id = {c["id"]: c for c in connectors}
    for identifier in dict.fromkeys(args.ids):
        connector = by_id.get(identifier)
        if connector is None:
            missing.append(identifier)
            continue
        surfaces = connector.get("surfaces", {})
        chosen = {name: surfaces[name] for name in dict.fromkeys(args.surfaces) if name in surfaces}
        selected.append({
            "id": identifier,
            "tier": connector.get("tier"),
            "classification_reason": connector.get("classification_reason"),
            "surfaces": chosen,
        })
    document = {
        "contract": "CONNECTOR_EVIDENCE_SLICE_V1",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes_read_locally": len(raw),
        "source_transport_bytes": "UNKNOWN",
        "selected": selected,
        "missing_ids": missing,
        "qualification_note": "Static catalog observations do not establish current auth, health or mutation authority.",
    }
    output = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(output) > args.max_output_bytes:
        print("EVIDENCE_INCOMPLETE: projected output exceeds byte limit", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(output)
    print(f"projected_bytes={len(output)} local_source_bytes={len(raw)} external_transport_bytes=UNKNOWN", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
