# RAT app icon — user selection, 2026-10-28

The user initially supplied an icon with “new app icon!”, then replaced that
selection with “on second thoughts, i like this more, this pls”. The second
artwork below is the current selection for full RAT.

![Selected RAT icon artwork — v2](../design/rat-app-icon-20261028/rat-app-icon-selected-v2-source-screenshot.png)

The original screenshot is preserved in the repository because its supplied
location was a temporary macOS screenshot directory. The selected artwork shows
RAT sitting amid scattered papers and open yellow folders, holding a pencil and
a sheet of paper, with its tail holding a magnifying glass. The background is a
muted green rounded square. This supersedes the first icon choice and is separate
from runtime mascot pose selection.

The [first icon screenshot](../design/rat-app-icon-20261028/rat-app-icon-source-screenshot.png)
is retained as a superseded alternative, not the current selection.

## Future app-icon selection option

User requested saving another artwork to backlog and specified that RAT should
later offer an option to change its app icon. This is a future settings/UI
customization feature; implementation is deferred.

![Alternative icon — RAT carrying a stack of papers](../design/rat-app-icon-20261028/rat-app-icon-paper-stack-option-source-screenshot.png)

This original screenshot is preserved from the user's temporary macOS screenshot
file, supplied at 23:47 on 2026-10-28. It shows RAT carrying a tall paper stack
and a pencil, with its tail holding a magnifying glass, against a muted green
rounded square.

Keep this artwork as an additional selectable-icon candidate. It does not
supersede the selected v2 icon above. Future work should prepare the icon assets,
provide previews and an explicit selection control, persist the user's choice,
and establish which app surfaces/platforms actually reflect the change before
claiming app-icon switching works. No icon-switching behavior is implemented by
this backlog update.

## Prepared assets — 2026-10-29

The user requested proper reusable icon resources and a small lowercase `lite`
label for Mini, now named RAT Lite. See the [asset catalog](../../rat/assets/app_icons/README.md)
and [preparation prompts](../design/rat-app-icon-20261028/production-prompts.md).
Full RAT default, Lite default, paper-stack and first-artwork alternatives now
have prepared masters, 1024px PNGs, native macOS ICNS resources and 10-slot
Retina iconsets. The masters are imagegen adaptations, not exact pixel crops.

The [later notebook artwork](../design/rat-app-icon-20261028/rat-app-icon-notebook-option-source-screenshot.png)
is also preserved as an alternative. Generated cutouts have an unwanted damaged
patch in the upper-left tile interior after repair attempts; it remains pending
a clean master and is excluded from the usable icon catalog.

App-icon selection UI, persistence and packaging integration remain deferred.
No installed app icon has changed. Full RAT still references `rat.icns` and the
Mini build script still references `tools/rat_translate.icns`; the prepared
replacements are `rat/assets/app_icons/rat-default.icns` and `rat-lite.icns`.
Respect the user's decision to pause Lite development; preparing its icon assets
does not resume its implementation or rename identifiers. No application build,
test, launch or UI acceptance was performed.
