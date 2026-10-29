# Larger Look mascot and continued acceptance — 2026-10-28

The user approved continuing the ten-point plan and requested a slightly larger
seated rat in Look. This authorizes the bounded checks/build/native observations
in this turn only. Mini remains the reusable proof of concept for main RAT.

## Changes

- Look's host increased from 80×84 to 96×100 logical pixels. Seated optical-height
  target increased from 70 to 86 (about 23%); floating head target remains 36.
  Wide poses still fit inside the host using MascotPose's existing constraints.
- Python profile constants now supply the initial QML dimensions and seated
  optical-height target, keeping placement and rendering in sync. Existing
  SpeechBubble, MascotPose, shared placement and tool execution were reused.
- Explicit recall in Look now retains reading intent, including while an
  accepted task is still running. Passive Clipboard ingress still uses its
  separate transient presentation path. This fixes a case where an explicitly
  reopened result could continue toward automatic disappearance.

## Software/package evidence

- 31 placement/Look/default-LLM checks passed (`tests.log`), including both former
  and enlarged host sizes in the shared geometry cases.
- Six Look checks passed after the recall change (`tests-recall.log`), then six
  after extending the recall guard to busy work (`tests-recall-busy.log`). These
  are overlapping changed-area runs, not 12 distinct new tests.
- One targeted passive-window test passed after a 5.2-second Qt wait
  (`tests-auto-hide.log`); whole window hidden, not just speech. Offscreen
  software behavior is not a native timer/energy measurement.
- .13 and .14 builds are retained for recovery. Final requested delivery is
  `dist/mini-speech-20261028-large-corner-final/RAT Mini.app`, planned build .15,
  with ZIP beside it. Final build/signature/hash status is in `status.json`.

Final .15 build completed. Its ad-hoc signature passed strict/deep verification;
ZIP SHA-256 is in `zip-sha256-final.txt`. No native .15 screenshot is claimed.

## Native observations with actual backends

Diagnostic .13/.14 copies used unique bundle identities and isolated state and
receipt paths; their code/QML came from the matching product build. Only identity,
LSEnvironment and ad-hoc signature differed. Original .8 process/session was
preserved. No assistant answers or model results were injected into UI.

CUA could bind after recalling through Mini's existing `present_running_mini`
activation API. Several initial binds to hidden/accessory windows still timed
out. All actual field edits, menu interaction and copy actions used CUA.

- `02-look-larger-idle.png`: native .13 seated rat, speech tail, status dot and
  one-line `Copy chữ để dịch`. Confirms the visual change on that display.
- `03-clipboard-observation.png`: native .13 working state after selecting/copying
  `Good morning.` in TextEdit. Receipt in `receipts/` records the real
  capture_text/source_ref → translate_text result `Chào buổi sáng.`, completed,
  offline_argos, zero LLM calls. The result screenshot attempt timed out after
  the transient window ceased being accessible; do not relabel the working image.
- `05-look-idle-14.png`: native .14 idle projection. Capture scale differs from
  the .13 image; do not compare pixel heights across these images as a resource
  or optical-size measurement.
- `06-recalled-translation-14.png` and `07-queued-copy-14.png`: real .14 short
  responses. The last filename describes the attempted scenario, not a passed
  queue assertion. Text changed instead of providing a clean retained-result
  observation. Other global clipboard changes were observed during this run,
  and explicit recall could coincide with work. The busy-recall guard was fixed
  afterward in .15; this flow has not been repeated natively on .15.
- .14 receipts also include a real Hello world → Xin chào thế giới result,
  completed, offline_argos and zero LLM calls. Source changes outside the intended
  pair were retained in the raw receipts rather than rewritten as successful tests.

The test-owned TextEdit document was the public test document created in the
previous turn; its text was updated only for the test phrases. CUA reported an
external window change once; state was refreshed before further actions.
All isolated QA processes were stopped at the end, so they no longer monitor
the global clipboard. The normal user Mini session remains untouched.

## Translation/resource observations

`translation-observations.json` records four actual source-service requests
through MiniSession/registered translation tools, with no LLM calls. Greetings
and a short library paragraph completed; `fire it up for me` became
`Đốt nó lên cho tôi`, still inappropriate for the user's app-launch context.
No phrase-specific replacement, new provider or LLM was introduced to conceal it.
These service timings are not copy-to-screen latency or model-quality estimates.

`process-sample.txt` is one QA process observation (idle/hidden): 0.0% CPU and
53,504 KiB RSS at that instant. It is not a workload, peak-memory or energy profile.
Package size, resident memory and full inference cost remain different quantities.

## Ten-point plan outcome

1. **Exact build:** .13/.14 QA identities and state were isolated; original .8
   preserved. .15 final native launch is not claimed.
2. **Short wrapping:** native .13 idle phrase is one line; regression passed.
3. **Real Clipboard:** actual .13/.14 captures/translations completed with receipts
   and zero LLM calls; working UI was captured.
4. **Intrusiveness:** fixed corner and larger seated sprite observed. No broad
   claim that automatic response is comfortable during normal work.
5. **Hide/recall:** passive hide passed the software check. Native recall attempts
   motivated the busy/retained-result reading fix; .15 native confirmation pending.
6. **Copy concurrency:** attempted but not accepted; global source contention
   and recall timing prevented a controlled native queue result.
7. **Long reading/edges:** enlarged geometry passed software cases; native long
   scrolling/dragging/restore remains unverified for this build.
8. **Error recovery:** source behavior retained; no new native error acceptance.
9. **Quality/resources:** four actual backend observations and one process sample
   saved, with the idiom failure and measurement limits explicit.
10. **Shared repair/main gate:** fixes remain in shared speech/lifecycle/profile
    components. Main UI integration, recipient M3 and Stage 0 remain open.

Next native scope should be a controlled retained-result/next-copy/own-copy run
on .15, followed by one long passage. Avoid repeating all passing software checks
without a relevant change. No automatic future testing permission is inferred.
