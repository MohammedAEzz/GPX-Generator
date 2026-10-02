# Naveera GPX Generator for macOS

A desktop app that writes real-road GPX files for the Naveera simulator. A normal trip produces two files (driver start to pickup, then pickup to drop-off). A pooled trip produces one file per driving leg, in the order you enter, with no route optimization.

Coordinates are sent to the public OSRM server at `router.project-osrm.org` (or another OSRM base URL you pass to the CLI). Use made-up test coordinates. There is no account and no API key.

## Why Tkinter

The window is Tkinter (`ttk`) on **Tcl/Tk 9.0.4 / Aqua**, from the uv-managed CPython **3.12.14** build (python-build-standalone). That build was checked on this project: a Tk window opens and closes with no deprecation warning.

macOS `/usr/bin/python3` (3.9.6) links Apple's Tcl/Tk **8.5.9** in `/System/Library/Frameworks/Tk.framework`. That Tk is deprecated and is not used to run or package this app. The project does not set `TK_SILENCE_DEPRECATION`. The fix is a supported Tk, not a hidden warning.

Tkinter is the GUI toolkit because it is already in that Python, it looks native under Aqua, and it avoids shipping a second UI stack. PyInstaller **6.22.3** is pinned because the 6.16 line added collection of Tcl/Tk from python-build-standalone and current 6.22 builds understand Tcl/Tk 9.

## Set up the same environment for running and packaging

Install [uv](https://docs.astral.sh/uv/), then from this folder:

```bash
bash scripts/bootstrap_venv.sh
.venv/bin/python scripts/check_tk.py
```

`bootstrap_venv.sh` reads `.python-version` (`3.12.14`), creates `.venv` with `uv venv --managed-python --python 3.12.14` (uv-managed only, so a Homebrew or python.org 3.12.14 with a different Tk is never picked up), and installs the pinned files `requirements.txt` and `requirements-dev.txt`. `check_tk.py` prints the Python path, `info patchlevel`, and `tk windowingsystem`, and exits if Tk is older than 8.6 or the windowing system is not `aqua`.

Compare that with the system interpreter (do not use it for this app):

```bash
/usr/bin/python3 -c "import tkinter; print(tkinter.Tcl().eval('info patchlevel'))"
```

That prints `8.5.9`.

## Run from source

```bash
.venv/bin/python app.py
```

```bash
.venv/bin/python generator.py --help
.venv/bin/python generator.py --input trip.json --output ~/Documents/NaveeraGPX
```

The GUI asks for a normal trip (passenger name, driver start, pickup, drop-off) or a pooled trip (pool name, driver start, and an ordered list of pickup/drop-off steps). Each pooled step has a passenger name and coordinates. Add, remove, and reorder stops with the row buttons. Switching between Normal and Pooled keeps what you already typed in the other form.

Speed and the output folder are in Settings. Open Trip / Save Trip (JSON) reuse a trip. Generate runs on a background thread; the window reads a queue on the main thread so it stays responsive, and a progress bar shows while it runs. Open Output Folder uses the macOS `open` command.

The window uses the native Aqua theme and follows Light/Dark Mode. Coordinate fields check themselves as you type (✓ with the parsed value, or the error in red). The pooled list numbers each stop, marks invalid coordinates, and previews how many physical stops remain after consecutive shared stops merge. The menu bar has **Naveera GPX → About Naveera GPX**, **File** (New Trip ⌘N, Open Trip… ⌘O, Save Trip… ⌘S, Generate GPX ⌘↩, Open Output Folder ⇧⌘O), **Edit**, and **Window**. Quitting (⌘Q or the close button) while a run is in progress asks for confirmation.

The app icon is `naveera_gpx/presentation/assets/app_icon_1024.png` (from `Midnight blue GPX route pin.png`). The build script turns it into `AppIcon.icns` for Finder and the Dock; the window and About panel load the bundled PNGs.

Each successful run creates a new folder named `{trip}-{timestamp}` inside the output folder, writes the GPX files there, then renames that folder into place. A failed run is renamed to `{trip}-{timestamp}.failed` and contains `ERROR.txt`. Generate again to start a new folder. Previous runs are left as they are.

If the driver is already at a stop, that stop stays in the summary and in `manifest.json` and no GPX is written for it. Consecutive steps that share coordinates become one physical stop and one incoming GPX, and every passenger name and pickup/drop-off action is kept. A later return to those coordinates is a new leg.

`manifest.json` records the road-snapped start and end of each leg. GPX files are GPX 1.1 with `<metadata><name>` and timestamped `<wpt>` points named `Route Point N`. There is no `<trk>`. Timestamps increase across points and across legs.

Routing errors (timeout, HTTP errors such as 429 or 5xx, invalid JSON, `NoRoute`, missing geometry) are shown as those failures. The app does not invent a straight line.

### JSON shape

Normal:

```json
{"type":"normal","name":"Passenger A","start":[39.69,-105.08],
 "pickup":[39.698010,-105.070418],"dropoff":[39.710486,-105.064513]}
```

Pooled (step order is the driving order):

```json
{"type":"pooled","name":"Pool A","start":[39.69,-105.08],"steps":[
  {"kind":"pickup","name":"Passenger A","point":[39.698010,-105.070418]},
  {"kind":"pickup","name":"Passenger B","point":[39.698010,-105.070418]},
  {"kind":"dropoff","name":"Passenger A","point":[39.710486,-105.064513]}
]}
```

Optional fields: `speed_mph` (default 20), `pause_seconds` (default 0). The examples above are format samples, not a stored trip. The app does not search for a start point.

## Tests

```bash
.venv/bin/python -m pytest -q
NAVEERA_LIVE_OSRM=1 .venv/bin/python -m pytest -q tests/test_live_osrm.py
```

The default run is offline and uses a fake router. The live test makes one request to the public OSRM server.

## Build a DMG on this Mac

```bash
bash scripts/build_macos.sh
```

The script recreates `.venv` when the interpreter is not 3.12.14, prints the Python and Tcl/Tk versions, refuses Tk older than 8.6 or a non-Aqua window system, then runs PyInstaller and `hdiutil`. Output:

- `dist/NaveeraGPX.app`
- `dist/NaveeraGPX-arm64.dmg` or `dist/NaveeraGPX-x86_64.dmg` for the Mac you built on

The bundled app includes its own Python and Tcl/Tk. Teammates do not install Python. Routing uses Python's `urllib` with the pinned `certifi` CA bundle so HTTPS works inside the frozen app (a bundled app often cannot use a system Python certificate store, and shelling out to `curl` is unnecessary). Check a built app with:

```bash
dist/NaveeraGPX.app/Contents/MacOS/NaveeraGPX --self-test
dist/NaveeraGPX.app/Contents/MacOS/NaveeraGPX --live-route
```

```bash
dist/NaveeraGPX.app/Contents/MacOS/NaveeraGPX --gui-self-test          # mock router
dist/NaveeraGPX.app/Contents/MacOS/NaveeraGPX --gui-self-test --live   # real OSRM
```

`--self-test` prints `info patchlevel` and `windowingsystem`, then writes a GPX with a mock router. `--live-route` makes one real OSRM request. `--gui-self-test` builds the real window (icons, menus, About), loads a pooled trip with a shared pickup, and generates through the window's background job.

After PyInstaller, the script sets `CFBundleName`/`CFBundleDisplayName` to "Naveera GPX" and the version from `naveera_gpx/__init__.py`, then re-signs the bundle ad hoc because editing `Info.plist` invalidates PyInstaller's ad-hoc signature. Ad-hoc is not a Developer ID signature; Gatekeeper still treats the download as unsigned.

## GitHub releases

The workflow `.github/workflows/macos.yml` runs on `workflow_dispatch` and on tags that start with `v`. It uses `astral-sh/setup-uv` with Python **3.12.14** (the same pin as `.python-version`), creates `.venv` from that interpreter, runs `scripts/check_tk.py` on both the Apple Silicon runner (`macos-15`) and the Intel runner (`macos-15-intel`), runs the tests, and builds a DMG per architecture. A tag push attaches both DMGs to the GitHub Release.

1. Push this folder to the repository root, including `.github/workflows/macos.yml`.
2. For a one-off build, open Actions → Build macOS DMG → Run workflow, then download the artifacts.
3. For a team download link, push a tag such as `v1.0.0`. The workflow publishes `NaveeraGPX-arm64.dmg` and `NaveeraGPX-x86_64.dmg` on that release.

M-series Macs use the arm64 DMG. Intel Macs use the x86_64 DMG. Open the DMG and drag Naveera GPX to Applications, or run it from the mounted volume.

## Gatekeeper

These builds are unsigned and not notarized unless you configure the optional signing secrets below. macOS may say the app cannot be opened because Apple cannot check it for malicious software. After you confirm the file came from your GitHub release:

- Right-click the app in Finder, choose **Open**, then **Open** again, or
- Go to System Settings → Privacy & Security and choose **Open Anyway**.

Do not disable Gatekeeper.

## Optional signing and notarization

Signing runs only when the environment is set. Local builds and GitHub Actions skip it when the values are absent. Do not commit these values.

| Variable | Role |
| --- | --- |
| `APPLE_SIGNING_IDENTITY` | `codesign` identity, for example `Developer ID Application: Name (TEAMID)` |
| `APPLE_ID` | Apple ID used by `notarytool` |
| `APPLE_TEAM_ID` | Ten-character team id |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password for `notarytool` |

On GitHub, add them as Actions secrets with those names. The workflow passes them into `scripts/build_macos.sh`. If `APPLE_SIGNING_IDENTITY` is missing, the script prints `Signing skipped` and still writes the DMG. If the identity is set but the notarization trio is not, the app is signed and notarization is skipped.

## Licenses

Bundled third-party components and their licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The build copies every license text into `NaveeraGPX.app/Contents/Resources/licenses/`.

## Layout

- `naveera_gpx/domain/` — coordinates, trip model, consecutive-stop merging, leg planning, GPX writing. No Tk and no network.
- `naveera_gpx/data/osrm.py` — OSRM client. Timeouts, HTTP errors, and bad payloads become typed routing errors.
- `naveera_gpx/presentation/` — the queue-based job, the Tk window (`gui.py`), and icon / menu bar / About window (`branding.py`, `assets/`).
- `generator.py` — command-line entry.
- `app.py` — window, `--self-test`, `--live-route`, and `--gui-self-test`.

Tests inject a fake router through the routing interface. The window does not merge stops or call OSRM itself.
