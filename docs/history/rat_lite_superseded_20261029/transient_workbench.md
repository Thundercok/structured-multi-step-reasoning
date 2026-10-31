# Transient Mini workbench — M5.14

RAT is a reusable RAT–CoT vertical slice. This is presentation policy over the
existing controller/service/tool contracts; no parallel business runtime, new
Agent planning loop or research campaign change.

## Presentation and state

Explicit launch, single-instance invocation or tray click can present/activate
RAT. `MiniShell` removes always-on-top behavior and dismisses after the app loses
activation, except during app-owned menus, native pickers and an active drag.
An initial activation guard avoids hiding the window before first use. Only
explicit presentation activates the LSUIElement app. Background completion,
captured-text events and result geometry changes never show a hidden window.

Escape/Cmd+W/hide, successful result copy, and successful open/reveal dismiss the
surface without clearing the QML draft, image snapshot, edited OCR or artifacts.
Closing a native dialog first closes that dialog. Quitting ends the in-memory
session; no claim of durable draft recovery across process restarts.

## Fixed-size placement

`mini_placement.place_panel` is pure geometry, including negative monitor origins.
RAT is always 122×128 logical pixels. User placement records a panel left/bottom
home. Expanded results choose a stable left/right dock and shift the workbench
when space requires it; collapse returns to home. Narrow screens constrain the
workbench, not RAT. A short hop includes both endpoints in the temporary window
bounds; masks track the visible panel and mascot, excluding the gap. Qt window
masks are a platform hint: real desktop click-through still needs acceptance.

The dock aligns near the input for small workbenches and near the top of large
ones. Background changes can update hidden geometry but cannot steal focus.
Reduced-motion presentation skips the hop.

## One content area

Result, OCR editing and inspectable image preview occupy the same body. Going
back preserves the edit; the previous translation is labelled stale and cannot
be copied until the edit is translated. There is one workbench collapse control,
one image/request summary and one composer. This does not introduce feature
modes. Settings preserve their existing explicit Save and Advanced configuration.

## Tool corrections

Spotlight retries a timeout at most once per scope within the original 12-second
budget and at most three concurrent children. It never expands scope or retries
a permission failure. Partial rows remain verified. Real M5.13 observation:
first search 0/3 timeout; explicit retry 3/3 complete in 435 ms. This establishes
intermittency, not a proven OS/library/TCC root cause.

Bundled NMT now segments punctuation-delimited sentences (with conservative
abbreviation handling), retains separators and uses beam size 4/coverage penalty
0.2. Units contain at most 256 source tokens; none are dropped. Cancellation is
checked between units rather than per generated token because CTranslate2's
per-token callback supports greedy decoding only. Structural verification still
does not certify semantic completeness; public omissions require live review.

References:
- https://doc.qt.io/qt-6/qwindow.html#setMask
- https://opennmt.net/CTranslate2/python/ctranslate2.Translator.html#ctranslate2.Translator.translate_batch

Actual build/test/UI outcomes are kept in audit/rat_mini_m514_20261027; this
contract is not by itself a declaration of full acceptance or main integration.
