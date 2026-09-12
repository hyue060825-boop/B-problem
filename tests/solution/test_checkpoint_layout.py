"""目录迁移兼容旧权重，同时保留严格的源码一致性校验。"""
from copy import deepcopy

import pytest

from solution.rl.training import provenance, verify_checkpoint_code


def test_checkpoint_accepts_both_layouts_and_rejects_mismatch(monkeypatch, tmp_path):
    # 从其他目录调用也应记录仓库实际源码，不能生成空 provenance。
    monkeypatch.chdir(tmp_path)
    current = provenance()
    assert 'src/solution/control/controller.py' in current['files']
    assert 'scripts/run_policy.py' in current['files']
    verify_checkpoint_code({'provenance': current})
    legacy = deepcopy(current)
    legacy['files'] = {key.removeprefix('src/'): value for key, value in current['files'].items()}
    verify_checkpoint_code({'provenance': legacy})
    for record in (current, legacy):
        broken = deepcopy(record)
        key = next(k for k in broken['files'] if k.endswith('solution/control/controller.py'))
        broken['files'][key] = '0' * 64
        with pytest.raises(ValueError, match='checkpoint/code mismatch'):
            verify_checkpoint_code({'provenance': broken})
    both = deepcopy(current)
    both['files']['solution/control/controller.py'] = '0' * 64
    with pytest.raises(ValueError, match='checkpoint/code mismatch'):
        verify_checkpoint_code({'provenance': both})
    with pytest.raises(ValueError, match='checkpoint/code mismatch'):
        verify_checkpoint_code({'provenance': {'files': {}}})
