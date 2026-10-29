# RAT Lite .28.1 — source handoff

The user reports that selecting text and pressing the shortcut on the running
.28 does not respond. Existing bounded journal shows `selection → invoked →
capture_requested → capture_started → capture_failed → presented`; it does not
record the failure reason. This establishes receipt and capture failure only;
it does not distinguish Accessibility, source-app change, unsupported AX
selection, or another failure. No claim that the bug is fixed is justified.
The current source records only a whitelist of safe reason codes for future
capture errors. The running .28 predates that change and still has no reason.

Source changes made afterward:
- Larger seated companion: host 144, optical target 112 logical px; dimensions
  describe source, not a visual measurement or acceptance.
- Shared `revise_observed_result` capability takes a pinned translation/analysis/
  revision artifact, checks kind/revision/expiry, invokes the opted-in cloud client,
  creates an observed result revision and structurally verifies parent hash/ref.
  Semantic correctness remains unverified. Explicit result-revision phrases route
  through MiniSession/service/dispatcher; a captured source is not relabeled as
  the model result. This is a direct model-backed tool, not proof of a live Agent loop.
- Bounded in-memory public turns and public tool-step projections are saved with
  the task tray; private thoughts are not exposed. The menu opens a Workbench
  surface with conversation, public steps and source/result. It uses a three-column
  layout on wider surfaces and stacks on narrower ones. This is an initial
  projection, not full source navigation or complete conversation context packing.
- `20261029.28.1` distinguishes this source from the running .28 package.

No tests, build, launch, live shortcut or model acceptance were run for these
changes. In particular the Workbench, result-revision routing, larger character
and failure-code reporting require a later explicitly requested build and user
operation. Existing .28 test batch from the prior turn had 8 passed / 4 failed;
one of these new changes has been verified by that historical batch. Main
integration, recipient M3 and research Stage 0 remain independent gates.
