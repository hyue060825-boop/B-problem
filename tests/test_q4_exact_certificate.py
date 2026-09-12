import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT=Path(__file__).resolve().parents[1]
PROOF=ROOT/'runs/q4_optimization_20260912/layout31_proof.json'
VERIFY=ROOT/'scripts/verify_q4_certificate_exact.py'


def verify(path):
    result=subprocess.run([sys.executable,str(VERIFY),str(path)],cwd=ROOT,text=True,capture_output=True)
    return result.returncode,json.loads(result.stdout)


def test_exact_baseline_proof_passes():
    code,result=verify(PROOF)
    assert code==0 and result['status']=='PROVED_MATH'
    assert result['leaf_count']==2224 and result['radius_cert']=='999'


@pytest.mark.parametrize('mutation',('delete_leaf','false_outside','bad_witness','missing_guard','unknown'))
def test_mutated_proof_is_rejected(tmp_path,mutation):
    data=json.loads(PROOF.read_text())
    if mutation=='delete_leaf':data['leaves'].pop()
    elif mutation=='false_outside':
        leaf=next(x for x in data['leaves'] if x['status']=='WITNESS');leaf.pop('witness');leaf['status']='OUTSIDE'
    elif mutation=='bad_witness':
        leaf=next(x for x in data['leaves'] if x['status']=='WITNESS');leaf['witness']=[0,0,0]
    elif mutation=='missing_guard':data['overlap_guards'].pop()
    else:data['unknown']=[{'depth':1,'ix':0,'iy':0}]
    path=tmp_path/'mutated.json';path.write_text(json.dumps(data))
    code,result=verify(path)
    assert code!=0 and result['status']=='INVALID_ARTIFACT'
