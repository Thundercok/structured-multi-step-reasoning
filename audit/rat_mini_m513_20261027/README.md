# RAT Mini M5.13 — source changes, unverified

2026-10-27. User requested Finder, screenshot ingress, OCR paragraph handling and
the agreed UX improvements. Code edited; no tests, smoke, app launch or capture
in this iteration. A separate M5.13 package build completed with exit 0 after
source completion; metadata/source hashes are in package.json and the build log
is build.log. Package: ../../../dist/mini-m513/RAT Mini.zip (0.5.13, 20261027.7),
ARM64/macOS 14+, ad-hoc signed, not notarized. No runtime source was changed
during or after the build. Existing M5.12 package remains unchanged. M5.13 is not an accepted
release or a friend-ready app.

## Implemented in source

- Drop, explicit image paste and picker call the same ingress/controller and
  `capture_translate` → capture tool → observed source_ref → translation tool.
  Image paste auto-starts; text paste still waits for Send/Enter. Retains any
  typed language instruction. No mode selector.
- Bounded in-memory thumbnail (640×360 maximum) with an opaque image-provider
  URL; no image bytes/base64 in snapshots, logs or persistent preview files.
- File promise drag types registered on the app-owned Qt Cocoa view, preserving
  existing registrations. Promises take precedence over a possible drag icon.
  Actual macOS screenshot thumbnail reception is still unverified.
- Previous request shown with Edit; restores text and retained image for a new
  submission. For an existing image, Edit reuses the observed/corrected source
  instead of recapturing and losing OCR edits. Optional language instructions
  route in shared headless orchestration. Retry uses the same shared service.
- Error/partial states expose Retry, Choose image or Choose folder as applicable.
  Shorter paper padding, full mascot fit rather than fixed crop, mascot retained
  beside results, discoverable paperclip, legible capture instruction.
- Basic settings show roots and target language. Provider, source override,
  model, key and fallback live under Advanced. Existing preferences preserved;
  keys remain in Keychain. FolderDialog passes QUrl through a typed adapter.
- Conservative OCR soft-wrap joining, original text + derivation retained and
  structurally verified; user correction remains a separate child artifact.
  See ../../../docs/contracts/ocr_soft_wrap.md.

## Finder — cause not yet established

Historical M5.12 evidence: frozen app timed out on all three roots; the source
provider outside app found the public PDF in Documents. Old subprocess code
discarded stderr, so those runs do not establish permission, index or library
conflict as the cause.

Source now opens only the allowed root for an access check, classifies bounded
stderr, separates system-child environment/cwd/stdin from the frozen runtime,
and preserves timeout rows/cancellation/identity and scope verification.
Root counts, elapsed time, runtime, codes and return codes are recorded without
paths/query/content in a replaceable `last-finder.json` receipt under Mini state.
No global search, file walk fallback, index rebuild, TCC reset or security grant.
Package recipe adds clear Documents/Desktop/Downloads usage messages; Apple says
these are optional but recommended, so their previous absence is not a proven
cause. This is diagnostic hardening and a candidate mitigation, not a verified
Finder fix.

Primary implementation references:

- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#macos
- https://developer.apple.com/documentation/appkit/nsfilepromisereceiver/readabledraggedtypes
- https://developer.apple.com/documentation/bundleresources/information-property-list/nsdesktopfolderusagedescription
- https://doc.qt.io/qt-6/qquickimageprovider.html

## Pending acceptance

After an explicit test request: one packaged Finder run against the provenance
PDF within a selected scope; inspect the new diagnostic if it fails. One native
screenshot thumbnail drop and one image paste, with OCR/edit/retry. Check paper
layout/focus on the actual UI and retain product screenshots. Only repeat the
failed section. Recipient M3 and signed/notarized distribution remain pending.

Business tools, shared execution and verification paths are implemented. This
iteration does not establish live Agent/model planning or main UI integration.
Mini remains the reusable RAT–CoT vertical slice; Stage 0 is unchanged.
