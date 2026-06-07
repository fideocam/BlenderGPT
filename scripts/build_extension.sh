#!/usr/bin/env bash
# Build BlenderGPT extension zip for extensions.blender.org (and local Install from Disk).
#
# Usage:
#   ./scripts/build_extension.sh
#   BLENDER=/path/to/Blender ./scripts/build_extension.sh
#
# Output:
#   dist/blender_gpt-<version>.zip   — upload this to extensions.blender.org
#   BlenderGPT-legacy.zip            — legacy layout (blender_gpt/ folder inside) for old install

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADDON_DIR="$ROOT/blender_gpt"
DIST_DIR="$ROOT/dist"
MANIFEST="$ADDON_DIR/blender_manifest.toml"

if [[ ! -f "$MANIFEST" ]]; then
  echo "error: missing $MANIFEST" >&2
  exit 1
fi

VERSION="$(grep -E '^version\s*=' "$MANIFEST" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"
if [[ -z "$VERSION" ]]; then
  echo "error: could not read version from blender_manifest.toml" >&2
  exit 1
fi

find_blender() {
  if [[ -n "${BLENDER:-}" && -x "$BLENDER" ]]; then
    echo "$BLENDER"
    return 0
  fi
  if command -v blender >/dev/null 2>&1; then
    command -v blender
    return 0
  fi
  local candidate
  for candidate in \
    "/Applications/Blender.app/Contents/MacOS/Blender" \
    /Applications/Blender\ *.app/Contents/MacOS/Blender; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

mkdir -p "$DIST_DIR"
EXT_ZIP="$DIST_DIR/blender_gpt-${VERSION}.zip"
LEGACY_ZIP="$ROOT/BlenderGPT-legacy.zip"

build_with_blender() {
  local blender_bin="$1"
  echo "Using Blender: $blender_bin"
  echo "Validating extension..."
  (cd "$ADDON_DIR" && "$blender_bin" --command extension validate)
  echo "Building extension zip..."
  (cd "$ADDON_DIR" && "$blender_bin" --command extension build)
  # Blender writes <id>-<version>.zip in the addon directory by default.
  local built=""
  for built in "$ADDON_DIR"/blender_gpt-"${VERSION}".zip "$ADDON_DIR"/*.zip; do
    if [[ -f "$built" ]]; then
      mv -f "$built" "$EXT_ZIP"
      echo "Extension zip: $EXT_ZIP"
      return 0
    fi
  done
  echo "error: blender extension build did not produce a zip in $ADDON_DIR" >&2
  return 1
}

build_manual_zip() {
  echo "Blender not found — building zip manually (no validation)."
  echo "Install Blender 4.2+ and re-run for full validate/build, or set BLENDER=/path/to/Blender"
  rm -f "$EXT_ZIP"
  (cd "$ADDON_DIR" && zip -r -q "$EXT_ZIP" . \
    -x "*__pycache__/*" \
    -x "*.pyc" \
    -x "*.DS_Store" \
    -x "*/.git/*")
  echo "Extension zip: $EXT_ZIP"
}

build_legacy_zip() {
  rm -f "$LEGACY_ZIP"
  (cd "$ROOT" && zip -r -q "$LEGACY_ZIP" blender_gpt \
    -x "*__pycache__/*" \
    -x "*.pyc" \
    -x "*.DS_Store")
  echo "Legacy zip:    $LEGACY_ZIP"
}

if BLENDER_BIN="$(find_blender)"; then
  build_with_blender "$BLENDER_BIN"
else
  build_manual_zip
fi

build_legacy_zip

echo ""
echo "Done."
echo "  Upload to extensions.blender.org: $EXT_ZIP"
echo "  Legacy manual install:            $LEGACY_ZIP"
