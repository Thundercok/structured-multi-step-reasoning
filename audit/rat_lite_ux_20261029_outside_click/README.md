# RAT Lite .21 — outside-click dismissal

User resumed work with “tiếp tục”. Source repair only; no new automated tests,
smoke run, screenshot capture or native acceptance flow was initiated.

On macOS, foreign application activation no longer dismisses Minimal or the
Look reader. A native mouse-down monitor observes actual clicks outside RAT;
Qt screen coordinates and the existing window mask determine the hit region.
The monitor does not consume events or record pointer positions/input text.
Menus/dialogs retain their existing dismissal exemption. Close/Esc, retained
draft/results and Look's five-second peek expiry remain unchanged.

The event callback is retained for the shell lifetime and its monitor removed
on quit. If installation fails, Close/Esc remain available; focus-loss dismissal
is not silently restored. No keyboard monitor or new permission prompt is added.

This addresses a source-level focus-loss path that could hide Minimal during
tool interaction. It does not prove that it caused all earlier CUA timeouts.
Actual outside-click behavior, display coordinates and UI control remain
unverified on .21. Historical test counts do not validate this revision.

Package target: `dist/rat-lite-20261029-outside-click/`; build output is in
`build.log`. No running app was replaced or closed in this iteration.
Default LLM setting, shared business dispatcher, main integration, M3 and
Stage 0 are unchanged. Full ten-point native acceptance remains incomplete.
