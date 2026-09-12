#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-0.1.0-dev}"
DIST="$ROOT/dist"
STAGE="$DIST/engineering-workstation-bootstrap-$VERSION"
ARCHIVE="$DIST/engineering-workstation-bootstrap-$VERSION.tar.gz"
CHECKSUM="$ARCHIVE.sha256"
TARFILE="$DIST/engineering-workstation-bootstrap-$VERSION.tar"

rm -rf "$DIST"
mkdir -p "$STAGE"

for path in AGENTS.md CLAUDE.md CONTRIBUTING.md SECURITY.md LICENSE README.md Brewfile mise.toml Makefile install.sh bin bootstrap config manifests docs lib skills validation packaging; do
  cp -R "$ROOT/$path" "$STAGE/"
done

find "$STAGE" -type f -name '*.sh' -exec chmod 755 {} +
find "$STAGE/bin" -type f -exec chmod 755 {} +

printf '%s\n' "$VERSION" > "$STAGE/VERSION"
# Normalize timestamps before archiving; gzip -n removes its own timestamp/name.
find "$STAGE" -exec touch -h -t 202001010000 {} +

COPYFILE_DISABLE=1 tar \
  --no-xattrs \
  --exclude='.DS_Store' \
  -cf "$TARFILE" \
  -C "$DIST" \
  "$(basename "$STAGE")"
gzip -n -9 -c "$TARFILE" > "$ARCHIVE"
rm -f "$TARFILE"

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$ARCHIVE" > "$CHECKSUM"
else
  sha256sum "$ARCHIVE" > "$CHECKSUM"
fi

printf 'Package: %s\nChecksum: %s\n' "$ARCHIVE" "$CHECKSUM"
