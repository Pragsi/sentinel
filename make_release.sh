#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "Usage: ./make_release.sh 1.3.0"; exit 1; }
ZIP="Sentinel_${VERSION}.zip"
rm -f "$ZIP" "$ZIP.sha256"
zip -r "$ZIP" sentinel install.sh sentinel-update-helper README.md -x "*/__pycache__/*"
sha256sum "$ZIP" > "$ZIP.sha256"
echo "Created $ZIP and $ZIP.sha256"
