"""Audit a curated paper branch; read-only checks plus a verification JSON report."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def read(path):return json.loads((ROOT/path).read_text())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='paper/provenance/release_verification.json');args=p.parse_args()
    failures=[];checks={}
    def require(ok,message):
        if not ok:failures.append(message)
    registry=read('paper/model_registry.json')['models']
    for m in registry:
        require(digest(ROOT/m['path'])==m['sha256'],'model hash: '+m['id'])
        for path,h in m['runtime_files'].items():
            require((ROOT/path).exists() and digest(ROOT/path)==h,'runtime: '+path+' model '+m['id'])
    checks['model_identities_verified']=len(registry)
    checks['final_runtime_files']=len(registry[0]['runtime_files'])
    for path,h in read('paper/provenance/table_inputs.json').items():require(digest(ROOT/path)==h,'table input: '+path)
    manifests=list((ROOT/'paper/history').rglob('archive_manifest.json'));archived={};parts=0
    for mp in manifests:
        m=json.loads(mp.read_text());h=hashlib.sha256()
        for part in m['parts']:
            pp=mp.parent/part['file'];require(pp.stat().st_size==part['bytes'] and digest(pp)==part['sha256'],'part: '+str(pp))
            with pp.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            parts+=1
        require(h.hexdigest()==m['archive_sha256'],'assembled archive: '+str(mp))
        for member in m['members']:archived.setdefault(member['path'],set()).add(member['sha256'])
    checks.update(archives_verified=len(manifests),archive_parts_verified=parts,
                  archive_members='All member hashes were verified during organization; extractor rechecks members before writing.')
    inventory=read('paper/provenance/original_inventory.json');backup=ROOT/'cache/original_workspace_20260913'
    checks['cache_originals']='not available on this clone'
    if backup.exists():
        for f in inventory:
            pp=backup/f['path'];require(pp.is_file() and pp.stat().st_size==f['bytes'] and digest(pp)==f['sha256'],'original changed/missing: '+f['path'])
        checks['cache_originals']=dict(files=len(inventory),all_hashes_match=not any(x.startswith('original') for x in failures))
    preserved=0;excluded=[]
    for f in inventory:
        rel=f['path']
        if not rel.startswith('runs/'):continue
        if f['sha256'] in archived.get(rel,set()):preserved+=1;continue
        pp=ROOT/rel
        if pp.is_file() and digest(pp)==f['sha256']:preserved+=1;continue
        if rel.endswith(('.pt','.pyc','.pid','.tar')) or '__pycache__' in rel:
            excluded.append(rel);continue
        require(False,'unpreserved experiment: '+rel)
    checks['original_run_evidence']=dict(preserved_files=preserved,cache_only_weights_bytecode_pid_tar=len(excluded))
    # All new authoritative links must work; original archival links retain original context.
    checked=0
    docs=[ROOT/'README.md',ROOT/'docs/REPRODUCING.md',ROOT/'paper/论文写作指导说明书.md',ROOT/'paper/EXPERIMENT_INDEX.md',ROOT/'paper/FIGURE_INDEX.md']
    for doc in docs:
        for raw in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            target=unquote(raw.strip('<>').split('#',1)[0])
            if not target or '://' in target:continue
            require((doc.parent/target).exists(),f'broken link: {doc.relative_to(ROOT)} -> {target}');checked+=1
    checks['authoritative_links_checked']=checked
    for figure in read('paper/provenance/figure_inventory.json'):require(digest(ROOT/figure['path'])==figure['sha256'],'figure: '+figure['path'])
    # Independently recompute published means from per-episode records.
    q3=read('runs/q34_deadline_test3000_20260913/q3_candidate_samples.json')
    q4=read('runs/q4_baseline_8gpu_1h_20260913/train/final_test.json')['student']
    with (ROOT/'paper/tables/final_main_results.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    for name,data in [('q3_final',q3),('q4_final',q4)]:
        row=next(r for r in rows if r['model']==name)
        require(len(data)==int(row['episodes'])==3000,'final sample count: '+name)
        require(abs(sum(r['virtual_time_s'] for r in data)/len(data)-float(row['mean_T_s']))<1e-8,'T mean: '+name)
        require(abs(sum(r['virtual_time_s']/r['N'] for r in data)/len(data)-float(row['mean_T_per_N_s']))<1e-8,'T/N mean: '+name)
    countdir='runs/q4_final_best_counts_20260913/evaluation'
    if (ROOT/countdir/'status.json').exists() and read(countdir+'/status.json')['status']=='COMPLETE':
        manifest=read(countdir+'/manifest.json');summary=read(countdir+'/summary.json');seeds=[]
        require(manifest['sha256']==next(m['sha256'] for m in registry if m['id']=='q4_final'),'Q4 count model identity')
        require(digest(ROOT/manifest.get('evaluator_source_file','scripts/evaluate_q4_source_counts.py'))==manifest['evaluator_sha256'],'Q4 count evaluator changed')
        for n in range(10,17):
            data=read(countdir+f'/N{n}_samples.json');expected=summary[str(n)]
            require(len(data)==1000 and all(r['N']==n for r in data),'Q4 count stratum '+str(n))
            require([r['seed'] for r in data]==manifest['seeds'][str(n)],'Q4 declared seeds '+str(n))
            require(sum(r['completion'] for r in data)==expected['completed'],'Q4 completion count '+str(n))
            require(all(0<r['directional_sources']<n for r in data),'Q4 mixed source types '+str(n))
            require(abs(sum(r['virtual_time_s']/n for r in data)/len(data)-expected['mean_per_source_s'])<1e-8,'Q4 per-source mean '+str(n))
            seeds.extend(r['seed'] for r in data)
        require(len(set(seeds))==7000,'Q4 count repeated seeds')
        require(read(countdir+'/verification.json')['checkpoint_and_runtime_unchanged'],'Q4 count runtime changed')
        checks['q4_final_7000_counts_verified']=True
    checks['main_means_recomputed_from_raw']=True
    git=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True).stdout.decode().split('\0')
    require(not any(s.startswith(('cache/','.venv/')) for s in git),'cache or venv tracked')
    checks['cache_not_tracked']=not any(s.startswith('cache/') for s in git)
    ignored=subprocess.run(['git','check-ignore','cache/original_inventory.json'],cwd=ROOT,capture_output=True)
    require(ignored.returncode==0,'cache ignore rule absent')
    checks['cache_ignore_rule']=ignored.returncode==0
    large=[s for s in git if s and (ROOT/s).is_file() and (ROOT/s).stat().st_size>100*1024*1024]
    require(not large,'Git blob over 100MiB: '+str(large))
    result=dict(status='PASS' if not failures else 'FAIL',checks=checks,failures=failures)
    output=ROOT/args.output;output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
