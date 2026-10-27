# Mini — bounded Agent loop, source only (2026-10-27)

User approved connecting the real reasoning loop and requested the lightest
implementation. This is source work only: no tests, app launch, model calls,
screenshots, build or ZIP for this change. The existing M5.16 package predates
it; its 17 software checks do not validate this source revision.

## Execution and cost

All business execution retains MiniSession → AgentExecutionService → registered
reasoning tools/ActionDispatcher → observed artifacts and verifiers. Clear
single-operation inputs keep the existing deterministic service lifecycle and
make no planning LLM call. This path is not labelled live model CoT. A translation
provider may itself use cloud; that is distinct from Agent planning.

Compound typed goals detected by the ingress router, and typed goals the router
cannot resolve, enter the existing AssistantRuntime. Mini now enables its real
planner with a compact operation-list declaration. The same runtime performs
native tool decisions, consumes observations, checks execution, reconciles the
declared outcomes and finishes or reports incomplete work. No alternate Agent
loop, framework, dependency or local reasoning model was added. Two tool steps
plus a reserved finish keep a simple multi-step slice within the existing cap:
at most 4 cloud requests and 2048 reported generated tokens per execution, 45 s.
Prompt context retains its existing size bound; these are engineering caps, not
learned optimal stopping or proof of NCKH quality. Unknown usage remains unknown.

CloudModelClient now requests a JSON object carrying the planner schema; shared
runtime schema validation remains authoritative. Invalid plans/errors do not
become a deterministic fallback advertised as model reasoning. The planner no
longer imports the excluded local SLM when a client is supplied, and its catalog
excludes operations marked model_visible=False. Mini still uses the configured
cloud provider/key; without one it reports the limitation. No cloud call was
made to verify provider JSON compatibility in this revision.

Canonical missing-input questions retain the compound goal and at most four
short dialogue messages for resumption. A new explicit request clears the old
pending operation. Allowed-folder metadata reaches the existing context builder;
no personal-file index, document reader or permission expansion was introduced.
The compound ingress remains conservative rules, not a guarantee of semantic
intent recognition. Leading explicit translation payloads and pasted passages
are not split into commands by the new compound-goal rule.

## Projection and boundaries

Worker progress uses actual tool steps and structural checks, without exposing
thoughts, prompts or raw model completions. The public Agent conclusion remains
beside the observed artifact, so a preview/file list cannot silently replace the
answer to a compound request. Incomplete scope is labelled partial. Optional
acceptance recordings distinguish direct_tool/model_loop, request counts,
controller decisions and public operation/verification metadata.

Apply/Undo/open/reveal remain explicit trusted UI actions; their hidden tool
contracts and approval pins are unchanged. No filesystem mutation was executed.
One input, draft/OCR retention, fixed mascot and restored production layout stay
in place. Main composition/UI integration and recipient M3 remain gated. Shared
planner fixes are reused infrastructure, not main Mini-profile integration.
Research scope, strategy harness, learned stopping policies and Stage 0 are
unchanged. Compact operation declarations do not prove intent completeness.

## Later bounded verification (only on explicit request)

First check direct inputs avoid planning calls, compound inputs reach the real
planner, missing key fails honestly, hidden mutation operations stay unavailable,
and clarification retains the original goal. Then one real configured-model
conversation using existing capabilities, e.g. find a named file and translate an
explicit short sentence. A file hit is metadata, never proof of reading its
contents. Preserve actual failures, receipts and public outputs. Synthetic tests
cannot establish live CoT/Agent acceptance. Do not automatically retest or build.
