# Smart Notes software fixture audit

Software checks: PASS. No live model or UI acceptance.

The 800 prompt / 125 completion tokens are assigned by fixture_model. They test accounting only and are not inference measurements.

Serialized JSON sizes: 3816 bytes full / 785 bytes packed. This makes no claim of semantic equivalence; it measures representation size only. It does not measure tokenizer counts, full inference cost, or online speedup.

Document Observation Pack: 2589 bytes full / 824 bytes packed (68.17% representation reduction).

PASS applies to input excerpts, source hash, structure and requested mutations. Summaries, interpretations and suggested actions remain unverified. Artifacts and revisions are in artifacts.json.
