# Hotkey repair — ten tool actions, 2026-10-26

Observed M5: a shortcut sent while RAT was focused inserted Î into the editor;
no capture observed. A menu capture request hid the RAT window; capture/OCR
success was not established. Native original registration alone returned success.
Keyboard delivery by automation may differ from a physical user key press.

Source repair: Carbon dispatcher target, Cocoa local keycode/flags monitor for
Qt/IME input, deduplicated callback, explicit unregister/remove lifecycle, visible
OSStatus registration failures, stage logging. Local monitor requests no new
Accessibility/Input Monitoring access. Global Carbon delivery still needs live
acceptance from another app. No claim OCR/translation was retested.

See registration_lifecycle.json for the bounded native registration check.
Packaging output: dist/mini-m5-hotkey/. Build log is
/private/tmp/rat-mini-hotkey-fix-build.log. Build was dispatched at the ten-action
limit; completion and physical hotkey/global/capture/cancel checks remain pending.

Reference used during diagnosis: maintainer report about Option-letter/IME
interaction: https://github.com/sindresorhus/KeyboardShortcuts/issues/235
