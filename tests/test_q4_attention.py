import copy

import numpy as np
import torch

from solution.control.controller import Controller
from solution.rl.model import StructuralCandidatePolicy
from solution.rl.structural_features import structural_features
from solution.rl.structural_training import structural_collate


def row(controller=None):
    controller = controller or Controller(4)
    state = structural_features(controller, controller.legal_actions())
    return {'state': state, 'teacher': 0}


def test_exit_and_unbound_candidate_are_finite_and_ignore_station_zero():
    model = StructuralCandidatePolicy().eval()
    c = Controller(4)
    for state in c.channels.values():
        state.status = 'ABSENT_CERTIFIED'
    batch, mask = structural_collate([row(c)], 'cpu')
    with torch.no_grad():
        logits1, value1 = model(batch, mask)
        batch['stations'][:, 0] += 10000
        logits2, value2 = model(batch, mask)
    assert torch.isfinite(logits1).all() and torch.isfinite(value1).all()
    assert torch.allclose(logits1, logits2, atol=1e-6)


def test_station_binding_selects_the_named_station_and_padding_is_ignored():
    model = StructuralCandidatePolicy().eval()
    batch, mask = structural_collate([row(), row()], 'cpu')
    valid = batch['candidate_station_valid'].bool()
    assert valid.any()
    candidate = int(valid[0].nonzero()[0])
    station = int(batch['candidate_station_index'][0, candidate])
    with torch.no_grad():
        original, _ = model(batch, mask)
        changed = {k:v.clone() for k,v in batch.items()}
        changed['stations'][0, station] += 5
        altered, _ = model(changed, mask)
    assert not torch.allclose(original[0, candidate], altered[0, candidate])


def test_cover_nonfirst_channel_changes_attention_context_and_has_gradient():
    model = StructuralCandidatePolicy()
    sample = row()
    state = sample['state']
    cover = next(i for i,m in enumerate(state['candidate_channel_mask']) if m.sum() > 1)
    target = int(np.flatnonzero(state['candidate_channel_mask'][cover])[1])
    batch, mask = structural_collate([sample], 'cpu')
    batch['channels'].requires_grad_(True)
    logits, _ = model(batch, mask)
    logits[0, cover].backward()
    assert batch['channels'].grad[0, target].abs().sum() > 0


def test_candidate_order_equivariance():
    model = StructuralCandidatePolicy().eval()
    sample = row()
    n = len(sample['state']['candidates'])
    perm = np.arange(n)[::-1].copy()
    other = copy.deepcopy(sample)
    for key in ('candidates','candidate_channel_index','candidate_channel_valid',
                'candidate_station_index','candidate_station_valid','candidate_channel_mask'):
        other['state'][key] = other['state'][key][perm]
    with torch.no_grad():
        a, _ = model(*structural_collate([sample], 'cpu'))
        b, _ = model(*structural_collate([other], 'cpu'))
    assert torch.allclose(a[0, perm], b[0], atol=1e-6)


def test_mixed_station_count_padding_does_not_change_short_example():
    model = StructuralCandidatePolicy().eval()
    short = row()
    long = copy.deepcopy(short)
    long['state']['stations'] = np.concatenate(
        [long['state']['stations'], np.full((3, long['state']['stations'].shape[1]), 999., np.float32)])
    long['state']['station_mask'] = np.ones(len(long['state']['stations']), dtype=np.bool_)
    with torch.no_grad():
        alone, _ = model(*structural_collate([short], 'cpu'))
        together, _ = model(*structural_collate([short,long], 'cpu'))
    assert torch.allclose(alone[0], together[0,:alone.shape[1]], atol=1e-6)
