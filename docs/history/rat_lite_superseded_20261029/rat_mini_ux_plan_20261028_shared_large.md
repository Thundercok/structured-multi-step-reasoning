# RAT Mini — self-critique and next UX plan

2026-10-28, Asia/Saigon. Planning only: no new implementation, tests or UI tour
performed for this review. Review uses design:design-critique framework.

## Evidence and scope

- Actual .18 Minimal: audit/rat_mini_speech_20261028/quiet-clipboard/16-shared-large-minimal18.png
- Actual .18 Look idle: audit/rat_mini_speech_20261028/quiet-clipboard/17-shared-large-look-idle18.png
- Actual .17 errors: 14-error17-attempt.png and 15-error17-retry.png in the same audit.
- Actual .17 long text: 12-overflow17-top.png and 13-overflow17-bottom.png.
- User full-screen size observations: user-size-look.png / user-size-minimal.png.

Do not present .17 error/long screenshots as fresh .18 acceptance. The user's
screenshot establishes that Look was visible despite a CUA timeout; disappearance
and retained-scroll failure were not established by that timeout.

User stylistic decision is fixed: BOTH LARGE, shared size. Keep the current
134px body optical target, 16px text, 580px shared panel/speech maximum and
original sprite proportions. Natural-width short speech remains appropriate;
shared size does not require empty padding to a fixed width for every sentence.
Mini is main RAT's reusable vertical slice. Default LLM remains off. Existing
service, dispatcher, tool results and verification remain the execution path.
Main UI integration, recipient M3 and Stage 0 are separate gates.

## Assessment

.18 improves size consistency, while the visual language remains split: Minimal
is an input card with its own footer/background; Look is a speech bubble. Equal
numerical size alone does not unify this interaction. The large character is a
user choice to preserve. The next priority is layout, continuity and clarity.

The gap/tail still leaves the character and surface visually detached. Developer
footer text competes with the task. The genuine disabled-provider error offers
Retry, although unchanged configuration cannot resolve it. Long text can be
scrolled; its visual affordance improved in .17. Pending copy preserves the
current result, but hidden Look makes the next action hard to discover. Physical
hotkey, robust retained-scroll recall and multi-display behavior are unaccepted.
Actual offline translations contain awkward phrases; these are a separate
quality backlog, not evidence for enabling an LLM in this UX iteration.

## Ten-point implementation plan (proposed, not implemented)

1. **One shared visual surface.** Extract the background, border, corner, tail
   and occupied bounds already in SpeechBubble into a reusable visual container.
   Compose the existing selectable speech renderer and existing Mini composer
   inside it; preserve their separate text/read versus input responsibilities.
   Acceptance: Minimal and Look visibly share the same surface, and business
   execution remains outside both presentation components.

2. **Freeze the shared LARGE profile.** Keep 134px body ink height and 16px
   text as the default; expose common padding, control scale, radius and maximum
   width through one Mini profile. Preserve pose aspect ratios and wide error
   silhouette. Acceptance: compare all poses at the same native display scale,
   without resizing differently sized screenshot crops to equal display widths.

3. **Connect surface and character optically.** Place from actual visualBounds
   and speechAnchor rather than transparent host edges alone. Use one corner
   home and baseline for Look/Minimal; tune gap and tail together so the tail
   reads as the rat speaking. Acceptance: idle, short, long and error remain
   visibly attached and avoid overlap on the tested screen edges.

4. **Stabilize transitions before adding motion.** Keep the mascot home fixed
   while the surface grows from its near edge. Pending clipboard input must not
   resize or replace the current reading task. Restore task scroll and selection
   before revealing a retained result. Acceptance: short→long→error→Minimal→Look
   has no gratuitous relocation or flash of unrelated text. Add only a brief
   optional opacity transition after geometry is stable; honor reduced motion.

5. **Remove developer chrome.** Move Mini · Speech source, version information
   and permanent shortcut explanations into Help/menu. Keep one input and Send
   primary in Minimal; keep current-task actions primary in Look. Put less-used
   display/settings actions in the shared secondary menu. Acceptance: the first
   glance identifies the text and the next action without reading a toolbar.

6. **Make quiet Clipboard discoverable.** Keep copy silent, latest pending input
   separate and explicit opening required. When the character is visible, use a
   small attached pending cue; when hidden, expose the same pending/open action
   from tray/recall. Show source preview only on explicit inspection. Acceptance:
   A remains readable while B is pending, and opening B is predictable without
   automatic popup or another translation request from RAT's own Copy.

7. **Make long reading comfortable.** Keep the persistent overflow thumb and
   continuation cue. Tune line length, paragraph spacing, padding and a bounded
   viewport as a coherent large-text layout; use the existing workbench for an
   explicit wider reading choice if needed. Acceptance: all final lines are
   reachable, selection/Copy returns the intended displayed text, and scroll
   returns to the previous position after dismissal/recall on the same task.

8. **Map errors to a useful next action.** Reuse shared execution error codes
   and recovery guidance in the Look projection. online_translation_not_enabled
   should name the disabled setting and offer Settings; reserve Retry for a
   condition that can change without configuration. Keep source_ref and seated
   error pose. Acceptance: cause→corrective action→retry→actual successful result
   on the same source; a second identical failure is not successful recovery.

9. **Specify focus and keyboard behavior precisely.** Distinguish visual peek,
   reading engagement and keyboard ownership. Enter/typing belongs to the
   composer; text selection/copy belongs to the reader. Audit Esc, outside click,
   drag, context menu and global tap/hold shortcut through the existing shell and
   interaction state. Acceptance: no unnecessary focus theft, no click activating
   the wrong build, no result loss; physical hotkey remains pending until observed.

10. **One bounded final acceptance pass.** Complete source changes before checks.
    Run only checks relevant to changed geometry/components/contracts, then one
    build and a continuous real-backend UI flow: summon→copy→explicit open→read
    →queue→long scroll→error→correct settings→retry→close→recall. Keep raw receipts
    and comparable full-context screenshots, including failures. Identify the
    exact build and isolate QA data; preserve the user's existing session. Report
    what passed, what failed, and what remains unaccepted. No blanket future test
    permission or main/research acceptance is implied by this proposed batch.

Suggested order: 1–5 together establish coherent visual continuity; 6–9 complete
interaction/recovery; 10 validates the result. Avoid repeated partial rebuilds
for each cosmetic adjustment. Maintain one reviewable source-complete iteration.
