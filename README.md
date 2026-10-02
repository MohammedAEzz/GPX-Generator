# Naveera GPX Generator for macOS

A Python/Tkinter GUI for real-road GPX test files. No accounts or API credentials required. Coordinates are sent to the selected OSRM routing service. Default: public router.project-osrm.org; use test data and avoid bulk routing.

## Run from source

Install Python 3.12 from python.org (includes Tkinter on macOS), then:

```bash
cd naveera-gpx
python3 app.py
```

Normal: name, current/start location, pickup, dropoff → two GPX files.
Pooled: name, start, ordered pickup/dropoff stops → one GPX per driving leg. Use ↑/↓ to set order. The tool follows this order; it does not optimize or validate passenger pickup-before-dropoff relationships. Consecutive identical coordinates merge, preserving labels; later returns to that location stay separate. Coordinates are latitude, longitude, not addresses. Same address with different coordinates will not merge.

Load/save JSON to reuse inputs. See `python3 generator.py --help` for JSON examples and CLI options. Output includes timestamped GPX waypoint files and manifest.json linking each leg to passengers/stops. Pause settings affect timestamps between files; they do not simulate a stationary dwell inside a GPX. Routing snaps to the road network; manifest reports snapped endpoints. Existing output folders containing files are protected from overwriting. Failed runs may leave partial output; select another folder for retry.

## Build and share through GitHub

1. Create a GitHub repository and upload the **contents** of this folder to its root, including `.github/workflows/macos.yml`.
2. Open Actions → Build macOS DMG → Run workflow. Download the arm64 / x86_64 artifacts when complete.
3. For a team download link, create and push a version tag, such as `v1.0.0`, or create a GitHub Release with that tag. The workflow attaches DMGs to the release.
4. Teammates download **arm64** for M-series Macs or **x86_64** for Intel Macs. Open the DMG and drag NaveeraGPX into Applications.

Private repositories require team access for downloads. Builds are unsigned and not notarized. macOS may block first launch; after verifying the release source, use System Settings → Privacy & Security → Open Anyway. Signed, notarized distribution requires your Apple Developer credentials and a separate signing/notarization setup. Do not disable Gatekeeper globally.

The Linux authoring environment validates Python and generator logic, but cannot build or visually test the native macOS app. GitHub Actions performs the macOS build; test the downloaded app on a Mac before distributing broadly.

## Build locally on a Mac

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyinstaller==6.16.0
pyinstaller --noconfirm --clean --windowed --name NaveeraGPX --osx-bundle-identifier tech.naveera.gpx app.py
mkdir -p dmg-stage
cp -R dist/NaveeraGPX.app dmg-stage/
ln -s /Applications dmg-stage/Applications
hdiutil create -volname NaveeraGPX -srcfolder dmg-stage -ov -format UDZO NaveeraGPX.dmg
```

The local build targets your Mac's architecture. No Python installation is needed by teammates using the bundled app. Internet access and macOS's built-in curl are needed for routing.
