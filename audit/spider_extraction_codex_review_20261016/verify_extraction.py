"""Read-only source verification; all patching/tests run in disposable copies."""
from pathlib import Path
import hashlib,json,os,shutil,stat,subprocess,sys,tarfile,tempfile,tomllib
root=Path(__file__).resolve().parents[2]
out=Path(__file__).resolve().parent
source=root/'spider';stage=root/'work/spider-extraction-20261016/pristine'
def inventory(base):
 return {str(p.relative_to(base)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(p.stat().st_mode)} for p in base.rglob('*') if p.is_file()}
a,b=inventory(source),inventory(stage)
result={'pristine_files':len(b),'source_files':len(a),'pristine_matches_content_and_modes':a==b}
with tempfile.TemporaryDirectory(prefix='spider-verify-',dir='/private/tmp') as folder:
 temp=Path(folder)
 patched=temp/'standalone';shutil.copytree(stage,patched)
 patch=root/'work/spider-extraction-20261016/patches/0001-fix-workspace-manifest-syntax.patch'
 p=subprocess.run(['patch','-p1','-i',str(patch)],cwd=patched,text=True,capture_output=True)
 result['patch']={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 if p.returncode==0:
  tomllib.loads((patched/'Cargo.toml').read_text())
  result['patched_toml_valid']=True
  p=subprocess.run([str(Path.home()/'.cargo/bin/cargo'),'metadata','--offline','--no-deps','--format-version','1'],cwd=patched,capture_output=True,text=True,timeout=40)
  (out/'cargo_metadata_stdout.json').write_text(p.stdout)
  (out/'cargo_metadata_stderr.txt').write_text(p.stderr)
  result['cargo_metadata']={'returncode':p.returncode,'stderr':p.stderr[:1500]}
 sandbox=temp/'rat_without_spider';sandbox.mkdir()
 shutil.copytree(root/'rat',sandbox/'rat',ignore=shutil.ignore_patterns('__pycache__','bin','.DS_Store'))
 shutil.copytree(root/'document_intake',sandbox/'document_intake',ignore=shutil.ignore_patterns('__pycache__','build','*.egg-info'))
 for p in root.glob('*.py'):shutil.copy2(p,sandbox/p.name)
 (sandbox/'tests').mkdir()
 for name in ['test_spider_adapter.py','test_assistant_runtime.py','test_work_context.py']:shutil.copy2(root/'tests'/name,sandbox/'tests'/name)
 assert not (sandbox/'spider').exists() and not (sandbox/'scratch').exists()
 runner='import sys; sys.path.insert(0,'+repr(str(sandbox))+'); import rat,pytest; assert rat.__file__.startswith('+repr(str(sandbox))+'); raise SystemExit(pytest.main(["tests/test_spider_adapter.py","tests/test_assistant_runtime.py","tests/test_work_context.py","-q"]))'
 p=subprocess.run([sys.executable,'-I','-c',runner],cwd=sandbox,capture_output=True,text=True,timeout=90)
 (out/'without_source_tests.log').write_text(p.stdout+p.stderr)
 result['without_source_tests']={'returncode':p.returncode,'stdout_tail':p.stdout[-800:],'stderr_tail':p.stderr[-400:],'spider_source_present':False,'scratch_build_present':False,'bundled_spider_binary_present':False}
(out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
