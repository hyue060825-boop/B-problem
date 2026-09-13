"""Export a portable matched-runtime bundle with the evaluated best weights."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'dist/B-problem-paper-final'
    if out.exists():raise SystemExit('Export directory exists; preserve it and choose a new version')
    out.mkdir(parents=True)
    for rel in ('scripts/run_policy.py','deployment/inference_fixtures.json'):
        dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
    shutil.copytree(ROOT/'deployment/runtime_public_v2',out/'deployment/runtime_public_v2',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(ROOT/'deployment/README_WINDOWS.md',out/'README_WINDOWS.md')
    shutil.copyfile(ROOT/'deployment/requirements-windows.txt',out/'requirements-windows.txt')
    (out/'models').mkdir()
    sources={}
    for q in (3,4):
        p=ROOT / ('runs/q3_legacy_deadline_20260913/best.pt' if q == 3 else 'runs/q4_baseline_8gpu_1h_20260913/train/best.pt')
        shutil.copyfile(p,out/f'models/q{q}_best.pt')
        sources[f'q{q}']=dict(original=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    files={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    (out/'bundle_manifest.json').write_text(json.dumps(dict(checkpoints=sources,files=files,python='3.11',torch_cpu='2.5.1',runtime_version='normalized-public-v2'),indent=2))
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(out.parent))
    print(archive,archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())

if __name__=='__main__':main()
