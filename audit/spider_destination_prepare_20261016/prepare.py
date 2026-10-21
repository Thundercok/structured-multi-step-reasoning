"""Prepare import into a separate destination checkout; no source deletion/push."""
from pathlib import Path
import hashlib,json,shutil,stat,subprocess
root=Path(__file__).resolve().parents[2]
out=Path(__file__).resolve().parent
target=Path((out/'checkout_path.txt').read_text().strip())
assert (target/'.git').is_dir()
assert not (target/'spider').exists()
existing={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file()}
base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=target,text=True).strip()
source=root/'spider'
shutil.copytree(source,target/'spider',copy_function=shutil.copy2)
files=[]
for p in sorted(source.rglob('*')):
 if p.is_file():
  relative=p.relative_to(source)
  data=p.read_bytes();q=target/'spider'/relative
  assert data==q.read_bytes() and stat.S_IMODE(p.stat().st_mode)==stat.S_IMODE(q.stat().st_mode)
  files.append({'path':str(Path('spider')/relative),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'mode':oct(stat.S_IMODE(p.stat().st_mode))})
metadata=target/'migration';assert not metadata.exists();metadata.mkdir()
shutil.copy2(root/'work/spider-extraction-20261016/patches/0001-fix-workspace-manifest-syntax.patch',metadata/'0001-fix-spider-workspace-manifest-syntax.patch')
(metadata/'spider-source-manifest.json').write_text(json.dumps({'origin_repository':'https://github.com/Thundercok/structured-multi-step-reasoning','origin_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'upstream':'https://github.com/spider-rs/spider','destination':'https://github.com/Thundercok/tdtu-timetable-compiler','source_prefix':'spider/','date':'2026-10-16','file_count':len(files),'note':'Working-tree snapshot includes local/ignored files; upstream differences are not claimed fully reviewed. Root Cargo.toml remains pristine; apply supplied patch only in a separate build copy.','files':files},indent=2))
(target/'SPIDER_IMPORT.md').write_text('''# Spider import — independent project

The owner selected this repository for the Spider source on 2026-10-16 and plans
substantial rework later. This repository is outside the scope of the RAT/CoT
main project. Existing timetable Python files are preserved unchanged.

`spider/` is the full 325-file working-tree snapshot imported from the former
embedded source. MIT notices and local examples/release script are preserved.
See `migration/spider-source-manifest.json` for source hashes, permissions and
provenance. Upstream is https://github.com/spider-rs/spider; this is not a claim
that all imported code was authored by the owner or that the snapshot is build-clean.

The pristine root Cargo.toml has a known syntax error. In a separate build copy,
apply `migration/0001-fix-spider-workspace-manifest-syntax.patch` with `patch -p1`.
This removes a misplaced example registration, preserving its source file. Patch
application and offline Cargo metadata were validated; a fresh full release build
of this imported snapshot remains to be verified. The previously used HTTP CLI
was 2.51.208, with no default CLI features and `status_code,headers` enabled.

This import does not change the existing Python files and does not add a RAT
runtime dependency. Rework, network controls and future publication decisions
belong to this independent repository.
''')
assert all(hashlib.sha256((target/name).read_bytes()).hexdigest()==h for name,h in existing.items())
result={'destination':'https://github.com/Thundercok/tdtu-timetable-compiler','local_checkout':str(target),'destination_base_commit':base,'source_files_copied':len(files),'content_and_modes_verified':True,'existing_files_unchanged':existing,'source_removed':False,'pushed':False}
(out/'prepared_import.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
# Explicitly stage our imported snapshot, including ignored release scripts.
subprocess.run(['git','add','-f','--','spider','migration','SPIDER_IMPORT.md'],cwd=target,check=True)
subprocess.run(['git','commit','-m','Import standalone Spider snapshot for independent rework'],cwd=target,check=True)
result['prepared_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=target,text=True).strip()
(out/'prepared_import.json').write_text(json.dumps(result,indent=2))
