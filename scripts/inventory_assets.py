#!/usr/bin/env python3
"""清点 paper 之外的工作资产；不加载权重、不修改原始实验数据。"""
from pathlib import Path
import csv
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'records/inventory'


def dump_csv(name,rows,fields):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    new=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    files=[]
    for rel in sorted(set(tracked+new)):
        if not rel or rel.startswith(('paper/','records/inventory/')):continue
        p=ROOT/rel
        if not p.is_file():continue
        category=rel.split('/')[0] if '/' in rel else 'root'
        files.append(dict(path=rel,category=category,bytes=p.stat().st_size,
                          sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    dump_csv('files.csv',files,['path','category','bytes','sha256'])
    current={
        'results/training/import-3ddb2d9/runs/q3_joint_20260912/baseline.pt':'最新 Q3 对照；原稳健推荐',
        'results/training/import-3ddb2d9/runs/q3_joint_20260912/ppo_candidate.pt':'最新 Q3 候选；未替代原推荐',
        'results/training/import-3ddb2d9/runs/q4_repaired_20260912/train/best.pt':'最新 Q4 配对对照；修复后训练 best',
        'results/training/import-3ddb2d9/runs/q4_budget_20260912/train/best.pt':'最新 Q4 预算训练 best',
    }
    checkpoints=[];figures=[]
    for row in files:
        path=row['path'];p=Path(path)
        if p.suffix=='.pt':
            checkpoints.append(dict(path=path,bytes=row['bytes'],sha256=row['sha256'],
                                     role=current.get(path,'其他阶段或历史归档；按原批次使用')))
        if p.suffix.lower() in {'.png','.pdf','.svg','.eps'} and path.startswith(('results/','handoff/figures/')):
            figures.append(dict(path=path,format=p.suffix[1:],bytes=row['bytes'],sha256=row['sha256'],
                                role='本批中文写作图件' if path.startswith('handoff/') else '历史原始图件'))
    dump_csv('checkpoints.csv',checkpoints,['path','bytes','sha256','role'])
    dump_csv('figures.csv',figures,['path','format','bytes','sha256','role'])
    parts={}
    for r in files:
        part=parts.setdefault(r['category'],dict(files=0,bytes=0))
        part['files']+=1;part['bytes']+=r['bytes']
    summary=dict(source_git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 scope='当前工作区中受跟踪及未忽略的新文件；排除 paper 与清单自身，含尚未提交的整理成果',
                 files=len(files),bytes=sum(r['bytes'] for r in files),parts=parts,
                 checkpoints=len(checkpoints),checkpoint_bytes=sum(r['bytes'] for r in checkpoints),
                 figure_files=len(figures),latest_checkpoint_roles=current)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'checkpoints':len(checkpoints),'figure_files':len(figures)},ensure_ascii=False))


if __name__=='__main__':main()
