# RAT app icons

Prepared raster icon resources, exported on 2026-10-29. These are imagegen
adaptations of the user's selected screenshots, not pixel-identical crops or
vector originals. Original screenshots remain in `docs/design/rat-app-icon-20261028/`.

| ID | Intended use | Preview | macOS resource |
| --- | --- | --- | --- |
| `rat-default` | Full RAT default: sitting in papers | [PNG](rat-default.png) | [ICNS](rat-default.icns) |
| `rat-lite` | RAT Lite default, lowercase `lite` badge | [PNG](rat-lite.png) | [ICNS](rat-lite.icns) |
| `rat-paper-stack` | Alternative: carrying papers | [PNG](rat-paper-stack.png) | [ICNS](rat-paper-stack.icns) |
| `rat-classic` | First artwork, retained as alternative | [PNG](rat-classic.png) | [ICNS](rat-classic.icns) |

Each entry includes a square 1024px PNG with exterior transparency, a native
`.icns`, and a `.iconset` containing the 10 macOS slots from 16px to 1024px
(including Retina variants). `manifest.json` records file paths and SHA-256 hashes.
Small sizes are downsampled from the master, not separately redrawn; the `lite`
badge is intended for Dock-sized display and is not guaranteed readable at 16px.

Masters: `docs/design/rat-app-icon-20261028/masters/`.
Export with `python tools/export_rat_app_icons.py` on macOS; this only converts
the prepared artwork using `sips` and `iconutil`, with a PNG-backed ICNS container
writer if `iconutil` rejects the iconset. It does not call imagegen,
run application tests, build an app, or install anything.
See the adjacent design directory's `production-prompts.md` for imagegen prompts.

## Integration status

The assets are prepared for future integration. No runtime icon selector,
persistence, bundle changes, installed-app updates or Dock acceptance is claimed.
`rat.spec` still uses root `rat.icns`; Mini's existing build script still uses
`tools/rat_translate.icns`. When development resumes, use `rat-default.icns` for
full RAT and `rat-lite.icns` for RAT Lite. Keep existing bundle identifiers and
paths unless separately requested; Lite development is currently paused.

The user's later notebook artwork is preserved as an additional candidate in
the design backlog. Its generated cutouts contain a defective patch in the tile
interior and are deliberately excluded from this ready-to-use catalog. A clean
notebook master is still required before exporting that option.

The local `iconutil` invocation rejected the generated iconsets; the ICNS files
were assembled using the PNG-backed container writer. This is recorded per icon
in the manifest. App/Finder/Dock display has not been checked.
