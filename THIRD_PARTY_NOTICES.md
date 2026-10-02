# Third-party notices

The macOS app bundles the following components. Their license texts are copied into
`NaveeraGPX.app/Contents/Resources/licenses/` by `scripts/build_macos.sh`.

| Component | Version | License | Text |
| --- | --- | --- | --- |
| CPython (python-build-standalone, via uv) | 3.12.14 | PSF License Agreement | `Python-LICENSE.txt`, copied from the pinned interpreter at build time |
| Tcl | 9.0.4 | Tcl/Tk license (BSD-style) | [`licenses/Tcl-license.terms`](licenses/Tcl-license.terms) |
| Tk | 9.0.4 | Tcl/Tk license (BSD-style) | [`licenses/Tk-license.terms`](licenses/Tk-license.terms) |
| certifi | 2026.7.22 | MPL-2.0 | `certifi-LICENSE`, copied from the installed package at build time |
| PyInstaller bootloader | 6.22.3 | GPL-2.0 with bootloader exception | `PyInstaller-COPYING.txt`, copied from the installed package at build time |

Route geometry comes from the OSRM demo server; map data © OpenStreetMap contributors (ODbL).
