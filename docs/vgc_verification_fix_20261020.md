# VGC calculation correction — 2026-10-20

## Cause

The legacy CPA branch inserted fixed values (64 credits, 7.20 prior CPA, fixed new grades/credits) into a program even when the query did not provide the new course details. Its expression used round(...), outside the current independent arithmetic checker's no-call grammar. The checker correctly returned unverifiable; the UI integration test incorrectly demanded valid. Tuition used similar fixed inputs. Neither a program reproducing its own output nor a fixed example establishes that it solved the user's question.

## Changes

The legacy MetaReasoner PAL branch now accepts only explicit literal requests supported by the shared arithmetic checker. Missing/unsupported word-problem interpretations ask for complete inputs or a supported expression, return unverifiable, and expose no numeric witness. It no longer supplies fixed CPA/tuition figures or reports 45 model tokens and 98% confidence for deterministic examples. Successful literal arithmetic is checked and returns its actual witness with zero model tokens.

The MetaReasoner result retains a numeric 0.0 compatibility sentinel where confidence is not estimated, with confidence_kind=not_estimated. The reasoning card shows Chưa ước lượng instead of a probability; unsuccessful verification no longer marks its trace sufficient. The shared trace's older numeric confidence schema remains unchanged; this sentinel is not a measured confidence or quality score.

Greeting detection now matches phrase boundaries: hi inside nhiêu must not redirect a CPA question into a greeting.

VGC arithmetic acceptance thresholds and grammar were not broadened. Unsupported round calls stay unverifiable, wrong witnesses stay invalid, and inaccurate decimal approximations do not pass the tight numeric tolerance. Exact source excerpts may pass only in the source_excerpt scope; paraphrases/semantic relations remain unchecked. Document execution summaries now state those limits rather than claiming source/entity authenticity.

## Tests and limits

Old VGC tests were aligned with this existing checker contract: source paraphrases do not imply entailment, division by zero is not a verifiable calculation, and deterministic operations do not manufacture confidence/model tokens. New tests distinguish valid arithmetic, missing CPA/tuition inputs, scalar precision, unsupported rounding and greeting substring collisions. See audit/vgc_verification_fix_20261020/tests.log.

No model inference, research-policy fit, prompt change or Stage 0 change occurred. The opt-in online policy adapter remains separate from legacy intent branches. No generalized CPA/tuition parser was added; users can provide a supported arithmetic expression, while future word-problem support needs a real input/execution contract. Unrelated dirty UI/runtime/research changes are preserved. No commit/push.
