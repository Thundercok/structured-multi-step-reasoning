# Approved RAT Workbench reference

The user approved the compact, separate-compartment design on 2026-10-15,
including the more prominent mouse: 104px desktop and 80px narrow artwork.
The default plan specimen is approximately 520 × 335 CSS px.

- `approved-desktop.png`: approved default composition.
- `approved-fragment.html`: frozen editable HTML reference, not a native app.
- `reference-narrow.png`, `reference-expanded.png`, `reference-dark.png`:
  illustrative additional presentation states.
- `browser-validation.json`: browser-only interaction/layout evidence.
- `manifest.json`: hashes and native source baseline at handoff.

All depicted work is synthetic UI content. The HTML uses a local timer and
fixed sample interactions. Do not port those fixtures into production or infer
native functionality, model speed or model quality from this packet.

Implement in native PyQt using
[`../../prompts/antigravity_rat_workbench_20261015.md`](../../prompts/antigravity_rat_workbench_20261015.md)
and the [detailed handoff](../../rat_workbench_design_20261015.md).
Keep this reference packet unchanged; place native implementation evidence in a
separate directory. No publication or Git push is authorized by this packet.
