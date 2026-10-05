Cascade on run11 trace (571 lines), gen02_tune. Committed before PAL/ReAct/ToT results are read.
Policy V: COT; if verifier flags (or COT hit length cap) -> escalate to E; else stop. E = PAL (arith), SC (order). Fixed now.
Cost = prompt+completion tokens of every arm actually run.
Per family vs always-COT, always-E, oracle: accuracy, mean tokens, 95% cluster-bootstrap CI of (V - COT) accuracy.
V promising only if delta >= +5pp with CI lower bound > 0 AND mean tokens <= 0.6 x always-E. Else no cascade claim.
Verifier rules were written after seeing these errors (in-sample): any claim needs confirmation on fresh gen02_v2 dev items.
