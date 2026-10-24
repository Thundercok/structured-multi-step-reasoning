# GSM8K collector/recovery/access design review — 2026-10-24

**Verdict: request design changes before implementation.** This reviews the
user-forwarded proposal, not an implemented collector. The 288-call / 294,912
generated-token envelope is planning arithmetic only; authorized inference and
embedding budget remains 0. No candidate questions, solutions or outcomes were
opened, no model loaded, no production implementation/protocol changed.
Checker C1–C3 remain closed within their previously accepted dry-run scope.

## D1 — [P1] Started-only attempts must consume calls and retain reservations

The proposed `K_done` includes only succeeded/failed attempts. Consequently
`K_remaining = K_all - K_done` includes an attempt with durable started event
but no terminal event. Resume redispatches it and the stated spent formula
also excludes its reservation. A two-condition example: first call succeeds,
second call runs but the process dies before outcome append. Resume sees one
condition remaining and dispatches again: **3 actual dispatches against a
2-call envelope**. Setting the same seed does not make this a free replay.
The same defect scales to the 288-condition frame.

Required contract: count every durable started event against the attempt cap;
retain its declared-token reservation until independently reconciled. An
orphan is `outcome_unknown`, never equivalent to unstarted. Only **never-started**
condition keys can dispatch under no-retry policy. Halt/quarantine unknowns;
do not declare a complete analysis bank while a required outcome is missing.
Any retry needs a new attempt ID, explicit authorization and additional budget,
not implicit permission from `--resume`.

`except BaseException` handles cooperative exceptions, not SIGKILL, power loss
or all crashes. Recovery must infer an unknown outcome from started-only state;
it cannot promise that every kill produces a failed event.

## D2 — [P1] Separate generation, PAL execution and analyzable record states

The proposal groups PAL timeout with unknown generation failure and reserves
1,024 tokens despite potentially having a completed generation with measured
tokens. Existing `_pal` records a failed tool execution as a **costed observation**
and returns the generated response for the existing scoring contract. The
protocol explicitly retains PAL failures; they are not missing generation rows.

Required contract: persist generation completion and public trace before PAL
execution; separately log tool started/outcome and the assembled record. A
known generation cost remains measured even if execution fails. A successful
generation plus a recorded tool failure can produce the same complete PAL
record the existing adapter would produce, without generation retry or a new
fallback. Recovery must never execute a saved program again silently. Unknown
generation/tool outcome or a torn record must remain incomplete until resolved
under an explicit policy. Do not treat 288 terminal ledger events as proof of
288 valid recipe records; the current evaluator rejects incomplete banks.

## D3 — [P2] Reject torn or inconsistent journals; never silently trim tails

The proposal says to back up a torn tail and resume, without defining whether
the malformed bytes are discarded or how their potentially dispatched call is
charged. A backup does not establish that it is safe to issue another call.

Required contract: fail closed on incomplete newline/JSON/hash/sequence,
duplicate starts/terminals, terminal-without-start or invalid transition. Keep
the original journal unchanged. A separate reviewed recovery action can retain
a byte-for-byte snapshot and produce a new recovery artifact with provenance;
normal `--resume` must not rewrite or trim evidence. The existing
`PilotCheckpoint._read` rejects a torn tail; copying its hash-chain pattern
does not authorize a weaker repair rule.

For valid journals, reconstruct from verified events and check any manifest
anchor against the chain. Explicitly handle interruption after journal fsync
but before manifest update. Rejection of configuration/integrity mismatch must
occur before rewriting manifests/reports/journals or modifying the lock file's
contents. Use an existing stable lock for resume; creation/locking rules for
new runs need a defined concurrency contract.

## D4 — [P2] Preserve the declared fixed baseline table and entry point

The proposal limits validation to two conditions. The current protocol says
to include **all three fixed conditions** in the eventual table. The evaluator
already reports selected rule, fitting-selected reference and DIRECT/COT/PAL.
These five named rows share three collected arms and do not fit 27 rules on
validation. Reporting predeclared baselines does not select a winner from them.

Required contract: keep the primary contrast fixed as selected rule minus
fitting-selected fixed reference; retain the three descriptive fixed rows.
Never score all 27 candidate rules to redesign the winner on validation. Reuse
`fit_selection(items, records)` with fitting metadata/records and its existing
`selected_rule` / `fixed_reference` fields, rather than the proposed incompatible
`fit_selection(fitting_records, rules)` signature. Keep the supported
`python -m experiments.research_study` entry point; any new resume/seal/validate
flags and schema adapters need explicit design and tests, not assumed existing
CLI support. Do not silently change the protocol to fit the draft.

## D5 — [P2] A protected folder and two timestamps do not enforce blinding

Validation outputs can appear in the common calls journal, partial traces,
records, logs, exception messages or the old combined pilot report. Moving
only `validation_records.json` leaves other exposure routes open. A directory
named `protected/` is not an access boundary; application timestamps cannot
audit arbitrary external reads or eliminate selection bias completely.

Required contract: name the operator/reviewer roles and enumerate every artifact
that can reveal validation outputs or scores. Fitting/report commands must not
open those outcome payloads before sealing; structural metadata/hash checks
can remain separate. Suppress pre-seal validation summaries/log echoes and
record access through the supported commands. Record manual prior exposure as
well, without claiming the application detects all filesystem reads. If both
roles' outputs are collected first as in the current protocol, an agreed
custodian/process must protect the journal and bank as well as derived files.
An alternative collection chronology is a prospective protocol change to
review separately, not an implicit guarantee from the folder layout.

## D6 — [P2] Seal external hashes and pin the whole execution contract

A literal SHA-256 of the final selection file cannot ordinarily be stored
inside that same file as its own full-byte checksum. Store the selection-file
hash in the manifest/seal record; if hashing a payload excluding a checksum
field, specify that canonical encoding and scope explicitly. Use atomic writes
and fsync with defined commit/recovery ordering, including directory durability
where a power-loss claim is intended. Hashing does not prevent a writer from
altering both file and manifest; preserve the trusted sealed record separately.

Resume identity must cover the full source/configuration/environment contract:
dataset role/group/order selection, source/protocol/checker/parser/voting/PAL
helper hashes, all model/tokenizer/template content and provenance, suffixes,
caps/temperature/thinking, strategy order and seed derivation, PAL timeout,
cost schema and package/platform identity. Model weights and config alone are
insufficient. Never update old source hashes to force historical replay or
resume compatibility.

## Implementation sequence after design correction

1. Write fixture-only state-machine/journal code: durable starts and terminal
   events, unknown-outcome accounting, monotonic attempt IDs, no silent retry.
   Keep generation/tool/record stages distinct and preserve measured costs.
2. Add identity-checked locking/resume which dispatches never-started keys
   only. Verify crash windows around each persistence boundary, fsync failures,
   malformed/torn chains, mismatches and concurrent writers. Check unchanged
   bytes for rejected resumes and never fabricate completeness.
3. Add fitting seal and gated report orchestration using existing fitter and
   evaluator semantics. Check no validation payload/report/log is consumed
   before the seal; changing validation outcomes must leave selection identical.
   Retain all three fixed descriptive baselines and the one primary contrast.
4. Only after offline review, return to data/configuration/human review and
   explicit inference authorization. None of these implementation steps opens
   the 48/48 candidate or passes Stage 0.

Required fixture cases include: hard-stop after started; generation success
before PAL; PAL failure/timeout; crash after terminal before record; crash after
record before manifest; already-complete output rejection; no retry of orphan
or failed generation; distinct expressions not merged by value; hash/seed/
tokenizer/source mismatch; and pre-seal validation access refusal. Run the
mandatory research regressions if the harness changes. This design review has
not run new software tests because no implementation was changed.

## Source basis

Compared against `docs/gsm8k_development_validation_protocol_20261004.md`,
`docs/gsm8k_development_review_readiness_20261023.md`,
`experiments/research_pilot.py`, `experiments/gsm8k_routing_baseline.py`,
`experiments/order_pilot_checkpoint.py` and `qwen_mlx_backend.py`. The attached
proposal remains a proposal; its command/schema names are not software
acceptance evidence. [Review provenance](provenance.json) records hashes and
the supplied attachment identity without copying candidate content.
