# Workbench revision review — 2026-10-16

Verdict: the two previously reported blockers are resolved for a feature-flagged
trial. No additional blocking finding in this scoped review.

- Verified matching source hashes against the supplied Cocoa capture manifest.
- Inspected the refreshed dark and source-detail images. Previously unreadable
  table, dialogue and composer text is now visible.
- Reviewed active scene ownership and observable accepted callbacks in the detail
  regression; unchanged revisions remain mounted, and real revision changes save
  state before detaching. Explicit collapsed disclosure states are restored.
- Independently ran all eight UI modules and the original active-detail probe:
  **156 passed, 3 subtests passed in 37.36s**. See `tests.xml`.
- Native capture metadata now accurately labels mocked Qt fixture replay and
  widget capture. Native IME composition and live-model UI behavior remain
  unverified; this review did not launch another Cocoa session.
- The nine native MLX backend-run source hashes from the separate document-service
  task still match. No inference or UI integration was performed in this review.

Keep `RAT_WORKBENCH_SCENE` default off pending user evaluation. Next integration
boundary: connect selected-document UI work to the resident MLX service with
worker ownership, execution guards, cancellation and shutdown intact.
