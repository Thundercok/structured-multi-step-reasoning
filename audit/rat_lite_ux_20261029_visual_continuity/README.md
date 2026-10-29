# RAT Lite .22 — visual continuity repair

Trigger: user says the interface still looks jarring. Review used the
design:design-critique skill, supplied earlier images and current source;
no fresh screenshot or live UI inspection was performed.

Concrete source findings:
- Look changed from a 134px seated body to a floating head at 42% optical
  height solely because the reply was short. This changes silhouette, speech
  anchor and occupied bounds at once.
- Side speech was vertically centered around the mouth. Changing its height
  moved both its top and bottom, even while the character stayed fixed.

Changes:
- Look retains the seated silhouette at 134px optical height across waiting,
  processing and short/long replies. Errors retain the seated error pose at
  that same optical height. Floating-head assets are preserved for later use.
- Shared speech placement gains an opt-in bottom alignment, used by both corner
  Minimal and Look. Their side bubble grows upward from the character baseline;
  top/bottom fallback and screen clamping still apply. Other callers retain
  the existing default placement.
- .21's outside-click repair is included. No new animation is added. Large
  character scale, font16, width580 maximum and natural short width remain.

Package target: dist/rat-lite-20261029-continuity/. No tests, smoke run, screenshots
or automatic acceptance tour were run. No running app was replaced. The source
changes and successful packaging are not proof of improved live experience.

Still unresolved: pending/processing/result surface resizing, platform window
resize artifacts, optical tail attachment across error poses, and overflow
reading should be assessed in the intended build before claiming smoothness.
Full ten-point native acceptance remains incomplete. Business dispatch, default
LLM off, main integration, M3 and Stage0 are unchanged.
