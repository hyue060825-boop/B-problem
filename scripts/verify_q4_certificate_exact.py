#!/usr/bin/env python3
"""Independent exact verifier for a rational Q4 quadtree proof artifact."""
import argparse,hashlib,json
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solution.coverage.q4_exact import (cell_outside_disk,cell_vertices,
    overlap_guard_valid,point,q,witness_valid)


def fail(reason,**extra):
    print(json.dumps(dict(status='INVALID_ARTIFACT',reason=reason,**extra)));return 2


def code(depth,ix,iy):
    if not (0<=ix<2**depth and 0<=iy<2**depth):raise ValueError('cell index out of range')
    return tuple(((ix>>bit)&1, (iy>>bit)&1) for bit in reversed(range(depth)))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('artifact');a=ap.parse_args()
    path=Path(a.artifact)
    try:d=json.loads(path.read_text())
    except Exception as exc:return fail('invalid JSON',detail=str(exc))
    if d.get('schema')!='q4-rational-quadtree-proof-v1':return fail('unsupported schema')
    try:
        domain=q(d['source_domain_radius']);radius=q(d['radius_cert'])
        if not 0<radius<1000:return fail('radius_cert must be strictly below 1000')
        raw=d['stations'];stations=[point((s['x'],s['y'])) for s in raw]
        if len(stations)<3 or len(set(stations))!=len(stations):return fail('station set is degenerate or duplicated')
        if [s.get('id') for s in raw]!=list(range(len(raw))):return fail('station IDs are not stable contiguous IDs')
        if d.get('unknown'):return fail('UNKNOWN cells remain',unknown_count=len(d['unknown']))
        leaves=d['leaves'];seen={};area=Fraction(0)
        for index,leaf in enumerate(leaves):
            depth,ix,iy=(leaf[k] for k in ('depth','ix','iy'))
            if type(depth) is not int or type(ix) is not int or type(iy) is not int:return fail('non-integer cell index',cell=index)
            key=code(depth,ix,iy)
            if key in seen:return fail('duplicate leaf',cell=index)
            if any(key[:n] in seen for n in range(len(key))):return fail('leaf overlaps ancestor',cell=index)
            if any(old[:len(key)]==key for old in seen):return fail('leaf overlaps descendant',cell=index)
            vertices=cell_vertices(depth,ix,iy,domain);status=leaf.get('status')
            if status=='OUTSIDE':
                if not cell_outside_disk(vertices,domain):return fail('OUTSIDE cell intersects source disk',cell=index)
            elif status=='WITNESS':
                if not witness_valid(vertices,stations,leaf.get('witness',[]),radius):return fail('invalid witness',cell=index)
            else:return fail('leaf has illegal status',cell=index,status=status)
            seen[key]=index;area+=Fraction(1,4**depth)
        if area!=1:return fail('leaves do not partition the complete root',normalized_area=str(area))
        expected={i for i,p in enumerate(stations) if p[0]*p[0]+p[1]*p[1]<=domain*domain}
        guards=d.get('overlap_guards',[]);actual={g.get('station_id') for g in guards}
        if actual!=expected:return fail('overlap guard set is incomplete',missing=sorted(expected-actual),extra=sorted(actual-expected))
        for g in guards:
            if not overlap_guard_valid(g['station_id'],stations,g.get('witness',[]),radius,domain):
                return fail('invalid overlap guard',station_id=g['station_id'])
    except (KeyError,TypeError,ValueError,ZeroDivisionError) as exc:return fail('malformed exact value',detail=str(exc))
    payload=path.read_bytes();out=dict(status='PROVED_MATH',station_count=len(stations),leaf_count=len(leaves),
        witness_cells=sum(x['status']=='WITNESS' for x in leaves),outside_cells=sum(x['status']=='OUTSIDE' for x in leaves),
        overlap_guards=len(guards),source_domain_radius=str(domain),radius_cert=str(radius),
        artifact_sha256=hashlib.sha256(payload).hexdigest(),arithmetic='fractions.Fraction; no float predicates')
    print(json.dumps(out));return 0
if __name__=='__main__':raise SystemExit(main())
