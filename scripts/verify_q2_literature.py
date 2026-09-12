#!/usr/bin/env python3
"""独立核对LIT-Q2-01数据配对、物理计费、GEOS包围圆及来源哈希。"""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from collections import Counter
import numpy as np
from shapely import minimum_bounding_radius
from shapely.geometry import MultiPoint, Point

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from experiment_q2_literature import summarize


def main():
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    raw=ROOT/'results/validation/LIT-Q2-01'
    seeds={};records_checked=0;steps=0
    for phase,n in [('pilot',32),('evaluation',480),('sensitivity',108)]:
        folder=raw/phase
        manifest=json.loads((folder/'manifest.json').read_text())
        for p,h in manifest['source_sha256'].items():assert sha(ROOT/p)==h,p
        for p,h in json.loads((folder/'outputs.sha256.json').read_text()).items():assert sha(folder/p)==h,p
        cases=json.loads((folder/'cases.json').read_text());seeds[phase]={c['seed'] for c in cases}
        records=json.loads((folder/'records.json').read_text());assert len(records)==n
        rows=list(csv.DictReader((folder/'samples.csv').open(encoding='utf-8-sig')))
        assert len(rows)==n
        first={}
        for record,row in zip(records,rows):
            m=record['metrics'];case=record['case'];trace=record['trace']
            for key,value in m.items():
                expected='' if value is None else str(value)
                assert row[key]==expected,(phase,key)
            key=case['seed']
            if key in first:assert first[key]==trace[0]
            first[key]=trace[0]
            pos=case['start'];cost=0.;cleared=False
            for step in trace:
                cost+=math.dist(pos,step['position'])/5
                if step['path']=='/measure':cost+=5.
                else:
                    success=math.dist(case['source'],step['position'])<=20 and not cleared
                    assert success==(step['response']['clear_result']=='success')
                    cost+=5. if success else 3.;cleared|=success
                pos=step['position'];steps+=1
            assert abs(cost-m['total_virtual_s'])<=len(trace)*1e-6
            assert cleared==m['completed']
            if record['posterior'] is not None:
                geom=MultiPoint(record['posterior']).convex_hull
                assert geom.buffer(1e-6).covers(Point(case['source']))
                independent=minimum_bounding_radius(geom)
                assert abs(independent-m['posterior_radius_m'])<1e-4
                v=np.array(record['posterior'])
                d=float(np.linalg.norm(v[:,None]-v[None,:],axis=2).max())
                assert abs(d-m['posterior_diameter_m'])<1e-5
            records_checked+=1
        report=json.loads((folder/'summary.json').read_text())
        summary,paired=summarize(records)
        assert report['methods']==summary and report['paired']==paired
    assert not(seeds['pilot']&seeds['evaluation'] or seeds['evaluation']&seeds['sensitivity'] or seeds['pilot']&seeds['sensitivity'])
    eval_cases=json.loads((raw/'evaluation/cases.json').read_text())
    counts={key:dict(Counter(c[key] for c in eval_cases)) for key in ['group','field','radius']}
    assert set(counts['group'].values())=={24}
    assert set(counts['field'].values())=={30}
    assert set(counts['radius'].values())=={40}
    manifest=json.loads((ROOT/'handoff/tables/LIT-Q2-01/provenance.json').read_text())
    for mapping in ('inputs','outputs'):
        for p,h in manifest[mapping].items():assert sha(ROOT/p)==h,p
    print(json.dumps(dict(status='PASS',records=records_checked,steps=steps,independent_geos_radius='PASS',
                          independent_diameter_and_time='PASS',source_and_output_hashes='PASS',
                          split_overlap=False,evaluation_strata=counts),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
