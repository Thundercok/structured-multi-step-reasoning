# RAT Lite .26 — repair from user-provided .25 screenshots

User supplied 16:28:00 / 16:28:04 / 16:28:29 screenshots on 2026-10-29 and
reported the UI as wrong. These are observations of the user's real .25 UI;
no screenshots were automatically captured by the agent.

Visible failures: large seated mascot at composer entry despite the requested
small head; empty reader space above input; two Close controls; a clipped long
placeholder; a disabled, truncated instruction in the secondary menu.

Source causes: head profile was gated behind successful selection capture, while
the app launched into the composer. SpeechBubble reserved reader padding and an
action rail even with no reader text. Its Close coexisted with the composer's
Close/footer. Input used large-profile sizing and a verbose placeholder.

Source repairs:

- All compact entry and reading states use the existing small head and 64×64
  host. No selection-success gate or pose change is required to see it.
- Empty composer reserves only its own height; no empty reader or header rail.
- Compact Send/More/Close share one row. When reader text is present, its Close
  replaces the inline Close. Expanded controls keep their existing footer.
- Compact input starts at300, grows to360 when needed, and says `Bạn cần gì?`.
  Shortcut hint is the short `Quick Look · ⌥⇧Space`. Font16 remains.
- Removed the disabled instructional menu row. Explicit permission/recovery
  actions remain in the menu and real selection-error notices.
- Submission captures actual current composer dimensions, including when no
  reader text exists. Geometry retention still uses bounded reader scrolling.

No business contract, selection adapter, dispatch path or provider changed.
The broader single-reader expanded-layout repair remains pending. Source version
is .26. Packaging/opening is recorded separately if completed; software tests,
UI tours and automatic screenshots remain unperformed. Passing build/startup
does not establish visual acceptance. Stage0/main/M3 gates remain unchanged.
