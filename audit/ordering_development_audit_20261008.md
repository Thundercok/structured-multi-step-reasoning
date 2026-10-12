# Ordering certificate development audit — 2026-10-08

Status: DEVELOPMENT ONLY; CORRECTED EVIDENCE ASSESSMENT. No test-answer solving
or new real-model run. The former draft overstated cost savings, safety, hardware
causality and statistical power; those conclusions are withdrawn below.

## Scope and source verification

Development consists of 31 exposed items: 8 train and 23 calibration from
`data/order_certificate_candidate_v1/dataset.json`, originating in `gen02_tune`.
The 100 prospective test questions are not evaluated in this audit.

The exact query-only solver was independently rerun on the 31 development items
during the offline review: all parsed, had a unique asked occupant and matched
development gold; mean assignments checked was approximately 3,697. These are
local development diagnostics, not human gold sign-off or held-out evidence.
Historical timing figures (3.14 ms mean, 97.19 ms total) lacked a retained raw
timing artifact and are not carried forward as a reproducible measurement.
The solver uses zero model tokens but nonzero CPU. It is a deployable baseline,
not an oracle or a theoretical accuracy upper bound.

## Reported real-pilot telemetry — raw artifacts unavailable

The pasted log described Qwen3-8B-4bit, seed 42, on two completed development
items. The named directory `audit/order_certificate_pilot_dev8_20261008` was not
present when inspected. No completed eight-item raw pilot is available to verify
its model revision, prompts, executions, termination reasons or token counters.
Keep the reported figures below only as an unverified record of the submission.

| Item | Arm | Reported answer | Reported gate/termination | Reported prompt + completion tokens |
| --- | --- | --- | --- | ---: |
| `order_0000_en_orig` (gold Carol) | PAL certificate | Carol | VALID | 162 + 156 = 318 |
| same | Candidate selection | empty | length | 669 + 3,072 = 3,741 |
| same | Native thinking | empty | length | 87 + 1,024 = 1,111 |
| `order_0001_en_orig` (gold Frank) | PAL certificate | Frank | INVALID | 163 + 210 = 373 |
| same | Candidate selection | empty | length | 943 + 3,072 = 4,015 |
| same | Native thinking | empty | length | 92 + 1,024 = 1,116 |

These numbers cannot establish that 8 items completed or that the loaded weights
matched the stated revision. Slow generation alone does not establish RAM/swap
causality. No throughput or full-study duration estimate is validated here.

## Calculation corrections

Conditionally on the log being accurate, with the same fallback for both gates:

| Policy | Correct / 2 | Total selected-path model tokens | Mean tokens |
| --- | ---: | ---: | ---: |
| W-certificate | 2 | 318 + 373 = 691 | 345.5 |
| Verified-certificate | 1 | 318 + (373 + 4,015) = 4,706 | 2,353 |
| Fixed candidate selection | 0 | 3,741 + 4,015 = 7,756 | 3,878 |

Verified / fixed-candidate ratio = `4706 / 7756 = 0.606756`.
Escalation rate = 1/2; mean initial cost = 345.5; conditional rejected-item
fallback cost = 4,015. Thus `345.5 + 0.5 × 4015 = 2353`, reproducing the policy
cost. Counting PAL alone omits the very fallback the policy invokes.

Frank is a correct answer according to the reported gold. Its invalid witness
does not demonstrate an incorrect-answer false accept by W. It is a rejection
of a correct initial answer and, if fallback is empty, one escalation-harmed
answer. Certificate validity and answer accuracy are distinct measurements.

## Statistical and generalization corrections

The previous CI-width illustrations were not a power analysis: no justified
alternative, discordance model, implemented boundary-safe rule or power curve
was retained. Therefore the claims that N=100 universally fails −2 pp, N≥400
guarantees sufficient power, or −5 pp gives 80% power are withdrawn.

The current −5 pp margin and 1,024 native-token cap remain proposed development
settings, not accepted decisions. The named boundary method is not implemented
or reviewed. A degenerate bootstrap cannot currently establish success. Do not
relax a margin or freeze settings merely to obtain a gate pass.

The symbolic solver and generic certificate verifier share a strict query
parser. No open-language experiment demonstrates verifier generalization beyond
that parser; generic verification also includes exact uniqueness solving.

## Software correction and next gate

The collector now pins mode/data/settings/source/runtime before resume, journals
each completed generation and execution, and labels mock evidence explicitly.
Shared scoring handles selected-output truncation, first-stage gate confusion,
and every invoked stage's token cost. See the
[fresh offline validation](order_certificate_pilot_fix_validation_20261008.md).
Old smoke/source manifests are historical and must not be rewritten.

Assessment: share the corrected software evidence with its caveats; **real-model
quality claims still need raw evidence and independent review**. Next: review
adapter/token accounting, collect a small exposed-development pilot when power
and resources permit, then decide statistical method, sample size/margin and
execution freeze. Human test review and the existing Stage 0 are not passed.
