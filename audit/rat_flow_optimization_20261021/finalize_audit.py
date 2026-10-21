"""Collect this delivery's evidence without modifying application sources."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


baseline = json.loads((HERE / 'source_start.json').read_text())
new_files = ['rat/engine/execution.py', 'tests/test_execution_flow.py',
             'tests/test_flow_interaction.py', 'docs/rat_flow_optimization_20261021.md']
end = {}
patch = []
for name in [*baseline, *new_files]:
    source = ROOT / name
    target = HERE / 'source_end' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    end[name] = sha(source)
    start = HERE / 'source_start' / name
    before = start.read_text().splitlines(keepends=True) if start.exists() else []
    patch.extend(difflib.unified_diff(before, source.read_text().splitlines(keepends=True),
                 fromfile=f'session_start/{name}' if start.exists() else '/dev/null',
                 tofile=f'session_end/{name}'))
save('source_end.json', end)
(HERE / 'changes_from_start.patch').write_text(''.join(patch))
changed = [name for name in baseline if baseline[name] != end[name]]
unchanged = [name for name in baseline if baseline[name] == end[name]]
save('session_delta.json', {'changed_existing': changed, 'new_files': new_files,
                           'unchanged_baseline_files': unchanged})

status = subprocess.run(['git', 'status', '--short', '--branch'], cwd=ROOT,
                        capture_output=True, text=True)
(HERE / 'git_status_end.txt').write_text(status.stdout + status.stderr)
whitespace = {}
for label, args in [('all', []), ('scoped', ['--', *changed])]:
    result = subprocess.run(['git', 'diff', '--check', *args], cwd=ROOT,
                            capture_output=True, text=True)
    (HERE / f'git_diff_check_{label}.txt').write_text(result.stdout + result.stderr)
    whitespace[label] = {'exit_code': result.returncode,
                         'output': f'git_diff_check_{label}.txt'}

xml = ET.parse(HERE / 'delivery-final.xml').getroot()
cases = xml.findall('.//testcase')
test_counts = {}
for case in cases:
    classname = case.attrib.get('classname', '')
    test_counts[classname] = test_counts.get(classname, 0) + 1
suite = {'cases': len(cases),
         'unique_cases': len({(c.attrib.get('classname'), c.attrib['name']) for c in cases}),
         'failures': len(xml.findall('.//failure')), 'errors': len(xml.findall('.//error')),
         'skipped': len(xml.findall('.//skipped')), 'by_module': test_counts,
         'raw': 'delivery-final.xml', 'command': 'delivery-final.command.json'}

command_names = ['delivery-final', 'candidate-build-final', 'candidate-inspection-final',
                 'candidate-help-final', 'native-delivery', 'startup-probe-final']
commands = {name: json.loads((HERE / f'{name}.command.json').read_text())
            for name in command_names}
bundle = json.loads((HERE / 'bundle_check.json').read_text())
native_path = 'native-sessions/20261021T041439Z-6c2634cd'
native = json.loads((HERE / native_path / 'session.json').read_text())
guards = json.loads((HERE / native_path / 'fixture_guard.json').read_text())
events = [json.loads(line) for line in
          (HERE / native_path / 'fixture_events.jsonl').read_text().splitlines()]
timing = json.loads((HERE / 'startup_final/startup_probe.json').read_text())
prior = json.loads((ROOT / 'audit/rat_native_permissions_20261020/bundle_check.json').read_text())
existing_path = ROOT / 'dist/rat.app/Contents/MacOS/rat'
existing = {'executable': str(existing_path), 'sha256': sha(existing_path),
            'prior_audit_sha256': prior['executable_sha256']}
existing['matches_prior_audit'] = existing['sha256'] == existing['prior_audit_sha256']

assert suite['unique_cases'] == suite['cases'] == 186
assert suite['failures'] == suite['errors'] == suite['skipped'] == 0
assert all(value['exit_code'] == 0 for value in commands.values())
assert all(bundle['checks'].values()) and bundle['status'] == 'passed'
assert native['status'] == 'exited' and native['exit_code'] == 0
assert not guards['blocked_operations'] and not native['blocked_operations']
assert guards['real_model_calls'] == guards['real_file_or_app_launches'] == 0
assert not native['embedding_loaded'] and existing['matches_prior_audit']
assert {'open_double', 'preview_double', 'synthetic_embed', 'synthetic_strategy'} <= {e['kind'] for e in events}
assert whitespace['scoped']['exit_code'] == 0
assert all(end[name] == digest for name, digest in timing['candidate_source_sha256'].items())

validation = {'status': 'passed_with_scope_limits', 'tests': suite,
              'final_command_exit_codes': {name: value['exit_code'] for name, value in commands.items()},
              'bundle': {key: bundle[key] for key in ['bundle', 'status', 'checks', 'executable_sha256']},
              'native_fixture': {'path': native_path, 'status': native['status'],
                                 'exit_code': native['exit_code'], 'guards': guards},
              'startup_probe': 'startup_final/startup_probe.json',
              'existing_app': existing, 'whitespace': whitespace,
              'scope_limits': ['No real model inference, download or quality claim',
                               'No production policy activated; reviewed compatible host composition required',
                               'Native source Cocoa fixture; frozen candidate inspected and CLI-smoked, not GUI-accepted',
                               'Hotkey disabled in native fixture; Accessibility not re-tested or changed',
                               'Open/preview are doubles; no personal-file indexing or real app launches',
                               'Fixture startup measurements do not establish native hotkey or online latency',
                               'Global diff whitespace findings are outside this delivery; scoped check passes',
                               'General streaming, document continuation and recovery polish remain later work']}
save('validation.json', validation)

(HERE / 'native_observations.md').write_text('''# Final Cocoa fixture observations

Source: CUA native accessibility observations in this Codex conversation, final
session `20261021T041439Z-6c2634cd`, process 63592. These are recorded observations;
no screenshot files are claimed. Open/preview callbacks are doubles, and the
controller backend/policy are synthetic. The final source snapshot matches the
tested and packaged source.

1. The window opened with the composer focused and no input.
2. Pasting `flow` showed two authored TXT hits, `flow-first.txt` and
   `flow-second.txt`. The editor retained `flow` and focus.
3. Tab → Space → Return → Escape returned to the composer with `flow` retained.
   `fixture_events.jsonl` independently records preview/open of the first file.
4. Replacing the draft with `giải thích fixture` and pressing Return showed
   `Đây là kết quả fixture synthetic; không gọi model thật.` with one public
   observed step. The event log records synthetic embedding and strategy COT.
5. Pasting `Bản nháp còn giữ`, expanding with Command-L, then collapsing with
   Command-L retained that exact draft, editor focus and the answer in both states.
6. Command-Q ended the process. The subsequent AX read reported procNotFound;
   the session record and wrapper confirm a clean exit 0, no model loads or
   blocked operations. No permission toggle or global event tap was used.

Earlier fixture sessions remain in `native-sessions/` for traceability. The first
also confirmed draft retention; the middle session did not confirm that step
after a user-activity interruption and is not used as its evidence.
''')

median = timing['medians']
rows = '\n'.join(f'| {metric} | {median["baseline"][metric]:.2f} | {median["candidate"][metric]:.2f} |'
                 for metric in ['import_ms', 'constructor_ms', 'show_and_events_ms', 'widgets_after_construct'])
report = f'''# RAT flow delivery — 2026-10-21

Implemented the authorized priorities 1–3: a shared desktop execution request and
worker factory, reduced synchronous UI startup work, and default progressive
finder interaction with retained state. RAT and CoT remain one system. No research
claims, Stage 0 status, model defaults or production policy activation changed.

## Changes

- Existing assistant, selected-document QA, composed reasoning and direct-operation
  workers share one factory. Conversation/turn/generation identities are reused;
  mismatched results are rejected. Document QA retains precedence. Direct actions
  retain their existing dispatcher/receipt scope and generation delivery guard.
- A host-supplied already-composed engine can execute the existing controller from
  the regular composer. Compatibility is revalidated; production rejects synthetic
  bundles. No automatic model/provider/policy loader was added. Quotas preserve
  zero, unsupported controls fail explicitly, and the original cost ledger remains
  attached. Completion alone is not marked verified; private reasoning is not
  exposed as public step text.
- Secondary schedule/club/embedded-settings pages construct once on demand. Initial
  index metadata and embedded model listings move off the GUI thread. Startup no
  longer probes model-service availability; configured name is not a ready claim.
  The separate modal settings dialog keeps its previous behavior.
- Finder starts with file retrieval available and scans app metadata after show.
  Its coordinator survives catalog delivery, preserving monotonic query IDs and
  suppressing stale queued results. Default scene/finder have explicit env=0 opt-outs.
- Tests cover actual QThreads, composer/controller delivery, lazy reuse, blocked
  metadata I/O, keyboard interaction, draft/caret/focus retention, catalog races,
  identity rejection, cancellation, zero quotas and synthetic-policy rejection.

The session delta contains {len(changed)} modified existing files and {len(new_files)} new
source/test/doc files. {len(unchanged)} captured baseline files are unchanged, including
the reasoning runtime/bundle, MetaReasoner, AssistantRuntime and packaging spec.
Use `changes_from_start.patch` and source snapshots instead of attributing the
checkout's many unrelated changes to this delivery.

## Validation

- Final combined run: **186 unique cases passed**, no failures/errors/skips,
  across 17 selectors. This includes the required 29 research regression cases
  and 20 new execution/interaction cases. `delivery-final.command.json` preserves
  exact argv/environment; JUnit and stdout are raw evidence. Overlapping earlier
  runs are not added to this count.
- Final Cocoa source fixture: default finder, keyboard preview/open, composer
  through synthetic composed controller, compact/expanded draft retention and
  clean exit were observed. See `native_observations.md` and the raw session.
  Hotkey is disabled; actual open/preview are doubles; no personal files, model
  inference, network access, app launches or permission changes were exercised.
- Separate candidate build, CLI `--help`, strict/deep codesign, exact entitlements,
  bundle ID and grammar resource passed. Fourteen embedded Python modules match
  final source bytecode. The frozen candidate GUI has not been acceptance-tested.
- Scoped `git diff --check` passes. The global check reports six whitespace
  findings in unrelated files; they were left untouched.
- Initial failures are retained: `focused` exposed null prompt-token adaptation;
  `focused-r2` and `composed-ui-debug` exposed a wrong AgentStep keyword in a Qt
  callback. Both defects were fixed before green runs. The later catalog/query-ID
  race was fixed and its regression case is included in the final 186.

## Startup fixture measurement

Three alternating baseline/current fresh-process pairs, offscreen Qt, empty
authored DB/catalog/model doubles, uncontrolled OS caches/background activity.
The baseline uses captured UI sources from this session's start. Medians:

| Metric | Baseline | Final source |
| --- | ---: | ---: |
{rows}

Times are milliseconds; widget count is a count. Import, construction and
show/event processing are separate samples, not a measured native end-to-end
interaction. Construction still takes about {median['candidate']['constructor_ms']/1000:.2f} seconds
in this fixture. These measurements establish neither global-hotkey latency,
model latency, model quality nor a universal speedup. Per-run values and source
hashes are in `startup_final/startup_probe.json`; the earlier probe remains intact.

## Reviewable artifacts and remaining work

Candidate: `{bundle['bundle']}`

Candidate executable SHA-256: `{bundle['executable_sha256']}`

The existing `dist/rat.app` was not replaced. Its executable SHA-256 remains
`{existing['sha256']}`, matching the preceding native-permissions audit. No git
commit, branch, push, pull or reset was performed. No installer/permission refresh
is implied by the candidate build.

See `docs/rat_flow_optimization_20261021.md` for composition and compatibility
behavior. Model setup stays deferred. An explicitly supplied compatible
production bundle/backend is needed to activate the controller branch outside
fixtures; no reviewed policy was assumed. General chat streaming, broader
document continuation and recovery polish remain separate work.
'''
(HERE / 'report.md').write_text(report)

excluded = {'test-state', 'pyinstaller-cache', '__pycache__'}
manifest = {}
for path in sorted(HERE.rglob('*')):
    relative = path.relative_to(HERE)
    if (not path.is_file() or any(part in excluded for part in relative.parts)
            or path.name in {'.DS_Store', 'artifact_manifest.json'}):
        continue
    manifest[str(relative)] = {'sha256': sha(path), 'bytes': path.stat().st_size}
save('artifact_manifest.json', manifest)
print(json.dumps({'status': validation['status'], 'tests': suite['unique_cases'],
                  'source_changes': len(changed) + len(new_files),
                  'manifest_files': len(manifest), 'report': str(HERE / 'report.md')}))
