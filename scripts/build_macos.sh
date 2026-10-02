#!/usr/bin/env bash
# Build NaveeraGPX.app and a DMG for this Mac's architecture.
# Uses the pinned interpreter in .python-version (uv-managed CPython).
# Refuses to package Apple's system Tcl/Tk.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash "$ROOT/scripts/bootstrap_venv.sh"

echo "Packaging with this interpreter:"
.venv/bin/python "$ROOT/scripts/check_tk.py"

ARCH="$(uname -m)"
case "$ARCH" in
  arm64|x86_64) ;;
  *)
    echo "Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

VERSION="$(.venv/bin/python -c 'import naveera_gpx; print(naveera_gpx.__version__)')"
ASSETS="$ROOT/naveera_gpx/presentation/assets"

# App icon: build AppIcon.icns from the 1024px source PNG.
ICONSET="$ROOT/build/AppIcon.iconset"
ICNS="$ROOT/build/AppIcon.icns"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ASSETS/app_icon_1024.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$ASSETS/app_icon_1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"

.venv/bin/python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name NaveeraGPX \
  --icon "$ICNS" \
  --osx-bundle-identifier tech.naveera.gpx \
  --specpath "$ROOT/build" \
  --collect-all certifi \
  --add-data "$ASSETS:naveera_gpx/presentation/assets" \
  "$ROOT/app.py"

APP="$ROOT/dist/NaveeraGPX.app"
if [[ ! -d "$APP" ]]; then
  echo "PyInstaller did not produce $APP" >&2
  exit 1
fi

# Third-party license texts for everything bundled (see THIRD_PARTY_NOTICES.md).
LICENSES="$APP/Contents/Resources/licenses"
mkdir -p "$LICENSES"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$ROOT"/licenses/* "$LICENSES/"
PY_BASE="$(.venv/bin/python -c 'import sys; print(sys.base_prefix)')"
PY_VER="$(.venv/bin/python -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
cp "$PY_BASE/lib/python${PY_VER}/LICENSE.txt" "$LICENSES/Python-LICENSE.txt"
SITE="$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
cp "$SITE"/certifi-*.dist-info/licenses/LICENSE "$LICENSES/certifi-LICENSE"
cp "$SITE"/pyinstaller-*.dist-info/licenses/COPYING.txt "$LICENSES/PyInstaller-COPYING.txt"

# Menu-bar / Finder name and version. Editing Info.plist invalidates PyInstaller's
# ad-hoc signature, so the bundle is re-signed ad hoc below (or with a real identity).
PLIST="$APP/Contents/Info.plist"
plutil -replace CFBundleName -string "Naveera GPX" "$PLIST"
plutil -replace CFBundleDisplayName -string "Naveera GPX" "$PLIST"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
plutil -replace LSApplicationCategoryType -string "public.app-category.developer-tools" "$PLIST"
if [[ -z "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  codesign --force --deep --sign - "$APP"
  echo "Ad-hoc signed (not a Developer ID signature; Gatekeeper still treats the app as unsigned)."
fi

sign_if_configured() {
  local app="$1"
  if [[ -z "${APPLE_SIGNING_IDENTITY:-}" ]]; then
    echo "Signing skipped (APPLE_SIGNING_IDENTITY is not set)."
    return 0
  fi
  echo "Signing with identity set in APPLE_SIGNING_IDENTITY."
  codesign --force --deep --options runtime --timestamp --sign "$APPLE_SIGNING_IDENTITY" "$app"
  if [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]]; then
    local zip="$ROOT/dist/NaveeraGPX-notarize.zip"
    rm -f "$zip"
    ditto -c -k --keepParent "$app" "$zip"
    xcrun notarytool submit "$zip" \
      --apple-id "$APPLE_ID" \
      --team-id "$APPLE_TEAM_ID" \
      --password "$APPLE_APP_SPECIFIC_PASSWORD" \
      --wait
    xcrun stapler staple "$app"
    rm -f "$zip"
    echo "Notarization submitted and stapled."
  else
    echo "Notarization skipped (APPLE_ID, APPLE_TEAM_ID, or APPLE_APP_SPECIFIC_PASSWORD is not set)."
  fi
}

sign_if_configured "$APP"

STAGE="$ROOT/dist/dmg-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="$ROOT/dist/NaveeraGPX-${ARCH}.dmg"
rm -f "$DMG"
hdiutil create -volname NaveeraGPX -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Built $DMG"
ls -lh "$APP" "$DMG"
