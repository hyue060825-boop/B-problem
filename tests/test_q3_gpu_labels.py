from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from q3_gpu_search import label
from q3_gpu_labels import export_labels


def fixture():
    task=dict(root_id='root',current=0,probabilities=[.8,.2],candidate_ids=['a','b'],selected=[0,1],reason=None,
              state={'global':np.zeros(10)},config=dict(worlds=2,min_gain_s=5,confidence_z=1,temperature_s=40))
    branches=[dict(branch_id=('root',c,j,0),completion=True,cost_s=cost,reason='certified_exit')
              for c,cost in [('a',100.),('b',70.)] for j in range(2)]
    return task,branches


def test_timeout_never_becomes_fast_label():
    task,branches=fixture();branches[0].update(cost_s=None,completion=False,reason='search_timeout')
    rec=label(task,branches)
    assert not rec['accepted'] and rec['reason']=='incomplete_search'
    json.dumps(rec,allow_nan=False)


def test_gpu_export_preserves_targets_and_rejects_wrong_policy_or_partial_roots(tmp_path):
    task,branches=fixture();rec=label(task,branches)
    assert rec['accepted']
    rec.update(policy_sha256='policy',full_branches=branches)
    path=tmp_path/'root.json';path.write_text(json.dumps(rec))
    anchor=dict(state=task['state'],target=np.array([.8,.2]),anchor=np.array([.8,.2]),kind='retention',weight=1.)
    rows,summary=export_labels([task],tmp_path,[anchor],'policy')
    assert summary['search_labels']==summary['retention_rows']==1
    np.testing.assert_allclose(rows[0]['target'],rec['target'])
    assert rows[0]['state'] is task['state'] and rows[1] is anchor
    with pytest.raises(ValueError,match='version mismatch'):export_labels([task],tmp_path,[anchor],'wrong')
    rec['full_branches'].pop();path.write_text(json.dumps(rec))
    with pytest.raises(ValueError,match='partial'):export_labels([task],tmp_path,[anchor],'policy')
