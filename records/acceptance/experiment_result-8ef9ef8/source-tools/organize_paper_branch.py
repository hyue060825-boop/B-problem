"""One-time reversible paper-branch curation; original workspace is never deleted."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BACKUP=ROOT/'cache/original_workspace_20260913'
PAPER=ROOT/'paper'


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)


def usable(p):return p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'


def dataset_pt(p):
    return p.name in ('data.pt','tasks.pt','anchors.pt','rows.pt') or p.name.startswith(('case_','bc_collected_','replay_'))


def evidence_file(p):
    return usable(p) and p.suffix not in ('.pid',) and (p.suffix!='.pt' or dataset_pt(p)) and p.name!='frozen_source.tar'


def archive(name,files,base):
    dest=PAPER/'history'/name;dest.mkdir(parents=True,exist_ok=True)
    tmp=ROOT/'cache'/('archive_'+name.replace('/','_')+'.tar.gz')
    records=[]
    with tarfile.open(tmp,'w:gz',compresslevel=5) as tar:
        for p in sorted(files):
            rel=str(p.relative_to(base));tar.add(p,arcname=rel,recursive=False)
            records.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
    # Keep each Git blob below 40 MiB, even for the multi-GB training evidence.
    pieces=[]
    with tmp.open('rb') as stream:
        index=0
        while chunk:=stream.read(40*1024**2):
            p=dest/f'data.tar.gz.part{index:03d}';p.write_bytes(chunk)
            pieces.append(dict(file=p.name,bytes=len(chunk),sha256=sha(p)));index+=1
    write(dest/'archive_manifest.json',dict(archive_sha256=sha(tmp),parts=pieces,members=records,
          note='Concatenate parts in order to obtain tar.gz. Paths preserve the original workspace. Original files retained in local cache.'))
    # Verify the archive contents against source hashes before it is considered preserved.
    with tarfile.open(tmp,'r:gz') as tar:
        got=[]
        for member in tar:
            data=tar.extractfile(member)
            h=hashlib.sha256()
            for chunk in iter(lambda:data.read(4*1024**2),b''):h.update(chunk)
            got.append((member.name,h.hexdigest()))
    assert got==[(r['path'],r['sha256']) for r in records]
    return dict(id=name,files=len(files),compressed_bytes=tmp.stat().st_size,parts=len(pieces))


def main():
    assert subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='experiment_result'
    if BACKUP.exists():raise RuntimeError('Backup exists; do not rerun destructive reorganizations')
    BACKUP.mkdir(parents=True)
    inventory=[]
    children=[p for p in ROOT.iterdir() if p.name not in ('.git','.venv','cache')]
    for child in children:
        for p in ([child] if child.is_file() else child.rglob('*')):
            if p.is_file():inventory.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)))
    write(ROOT/'cache/original_inventory.json',inventory)
    (ROOT/'cache/original_git_status.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True))
    (ROOT/'cache/original_working_diff.patch').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=ROOT))
    for child in children:shutil.move(str(child),str(BACKUP/child.name))
    for r in inventory:
        assert sha(BACKUP/r['path'])==r['sha256'],r['path']
    print(json.dumps(dict(stage='BACKUP_VERIFIED',files=len(inventory))),flush=True)
    (ROOT/'.gitignore').write_text('/cache/\n/.venv/\n/.local/\n__pycache__/\n*.pyc\n.pytest_cache/\n')
    for name in ('problem','fixtures','rules','artifacts','deployment','experiments'):
        shutil.copytree(BACKUP/name,ROOT/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('solution','bsim'):
        shutil.copytree(BACKUP/'deployment/runtime_public_v2'/name,ROOT/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('pyproject.toml',):copy(BACKUP/name,ROOT/name)
    # Final-runtime compatible scripts are from the actual matching source revision.
    old_scripts=subprocess.check_output(['git','ls-tree','-r','--name-only','3ddb2d9','scripts'],cwd=ROOT,text=True).splitlines()
    for rel in old_scripts:
        p=ROOT/rel;p.parent.mkdir(exist_ok=True,parents=True)
        p.write_bytes(subprocess.check_output(['git','show','3ddb2d9:'+rel],cwd=ROOT))
    recent=[
        'run_policy.py','run_python.sh','build_windows_policy_bundle.py',
        'analyze_q4_absence_tail.py','report_q4_absence_tail.py','evaluate_q4_empty_arena.py',
        'evaluate_q4_planning_ablation.py','report_q4_planning_ablation.py','plot_q4_last_clear_comparison.py',
        'search_q3_layout_extremes.py','report_q3_layout_extremes.py',
        'search_q4_layout_extremes.py','report_q4_layout_extremes.py',
        'evaluate_deadline_pair.py','report_deadline_pair.py','report_q4_hour_pair.py',
        'train_legacy_deadline_ddp.py','launch_q4_baseline_8gpu_hour.py','organize_paper_branch.py',
        'verify_q4_certificate_exact.py','build_q4_witness_certificate.py']
    for name in recent:copy(BACKUP/'scripts'/name,ROOT/'scripts'/name)
    for p in (ROOT/'scripts').glob('*.sh'):p.chmod(0o755)
    for rel in subprocess.check_output(['git','ls-tree','-r','--name-only','3ddb2d9','tests'],cwd=ROOT,text=True).splitlines():
        p=ROOT/rel;p.parent.mkdir(exist_ok=True,parents=True)
        p.write_bytes(subprocess.check_output(['git','show','3ddb2d9:'+rel],cwd=ROOT))
    for name in ('test_q4_planning_ablation.py','test_run_policy_deployment.py'):
        copy(BACKUP/'tests'/name,ROOT/'tests'/name)
    for p in (BACKUP/'configs').glob('*legacy*'):copy(p,ROOT/'configs'/p.name)
    # Expose completed evaluation datasets and selected training runs at original paths.
    visible={
        'q34_deadline_test3000_20260913','q3_legacy_deadline_20260913','q4_legacy_deadline_20260913',
        'q4_baseline_8gpu_1h_20260913','q3_layout_extremes_20260913_v2',
        'q4_layout_extremes_20260913','q4_empty_arena_20260913','q4_absence_tail_analysis_20260913_v2',
        'q4_planning_ablation_20260913','q3_final_best_counts_20260912','q4_certificate_search_20260912',
        'q4_optimization_20260912'}
    weights={
        'q3_legacy_deadline_20260913/best.pt','q4_baseline_8gpu_1h_20260913/train/best.pt',
        'q4_baseline_8gpu_1h_20260913/parent/best.pt','q4_legacy_deadline_20260913/best.pt',
        'q3_gpu8_extended_20260912/ppo/best.pt','q4_budget_20260912/train/best.pt'}
    for run in sorted((BACKUP/'runs').iterdir()):
        if run.is_file():continue
        if run.name in visible:
            for p in run.rglob('*'):
                if not evidence_file(p) or p.suffix=='.pt':continue
                # Raw per-training-episode data remain losslessly archived below.
                training=run.name in {'q3_legacy_deadline_20260913','q4_legacy_deadline_20260913','q4_baseline_8gpu_1h_20260913'}
                if training and p.name.startswith('episodes_'):continue
                copy(p,ROOT/p.relative_to(BACKUP))
        if run.name=='q3_gpu8_extended_20260912':
            for p in (run/'final_evaluation').rglob('*'):
                if usable(p):copy(p,ROOT/p.relative_to(BACKUP))
    for rel in weights:copy(BACKUP/'runs'/rel,ROOT/'runs'/rel)
    # Every historical result, label dataset and experimental script remains on branch.
    archives=[]
    for run in sorted((BACKUP/'runs').iterdir()):
        if run.is_dir():
            files=[p for p in run.rglob('*') if evidence_file(p)]
            if not files:continue
            archives.append(archive('runs/'+run.name,files,BACKUP))
            readable=PAPER/'history/runs'/run.name/'readable'
            for p in files:
                name=p.name.lower()
                # Human-facing reports/figures and compact metadata are directly browsable.
                if p.suffix.lower() in ('.md','.png','.pdf') or (p.stat().st_size<2*1024**2 and any(w in name for w in ('summary','manifest','selection','status','config','proof'))):
                    copy(p,readable/p.relative_to(run))
            print(json.dumps(dict(stage='ARCHIVED',**archives[-1])),flush=True)
    for name in ('scripts','tests','solution','bsim','configs','reports','docs','logs','experiments'):
        files=[p for p in (BACKUP/name).rglob('*') if usable(p)]
        if files:archives.append(archive('workspace/'+name,files,BACKUP))
    loose=[p for p in (BACKUP/'runs').iterdir() if p.is_file()]
    if loose:archives.append(archive('workspace/run_logs',loose,BACKUP))
    shutil.copytree(BACKUP/'reports',ROOT/'reports')
    shutil.copytree(BACKUP/'docs',ROOT/'docs')
    # Planning prompts are source material, not claims that all requested stages succeeded.
    for p in ROOT.parent.glob('*.MD'):copy(p,PAPER/'protocols'/p.name)
    for p in ROOT.parent.glob('*.jsonl'):
        if p.name=='logQ4.jsonl':copy(p,PAPER/'official_logs'/p.name)
    logs=[p for p in ROOT.parent.glob('*.log') if p.is_file()]
    if logs:archives.append(archive('workspace/external_logs',logs,ROOT.parent))
    write(PAPER/'provenance/archive_index.json',archives)
    write(PAPER/'provenance/original_inventory.json',inventory)
    write(PAPER/'provenance/reorganization.json',dict(backup=str(BACKUP),original_files=len(inventory),
          original_bytes=sum(r['bytes'] for r in inventory),all_original_hashes_verified_after_move=True,
          preserved_runtime_revision='3ddb2d9',excluded_from_git='cache/',
          raw_results='all non-checkpoint experimental artifacts archived, including tensor label datasets',
          old_model_weights_and_large_redundant_source_tar='kept in cache; original paths and SHA256 available in inventory',
          previous_branch='hy_branch/b45c0d2',previous_commit='660e63f',branch='experiment_result'))
    # Preserve manifest for excluded file locations without publishing obsolete model blobs.
    omitted=[r for r in inventory if r['path'].startswith('runs/') and
             ((Path(r['path']).suffix=='.pt' and not dataset_pt(Path(r['path']))) or Path(r['path']).name=='frozen_source.tar')
             and r['path'][5:] not in weights]
    write(PAPER/'provenance/cache_only_model_inventory.json',omitted)
    print(json.dumps(dict(stage='CURATED',archives=len(archives))),flush=True)


if __name__=='__main__':main()
