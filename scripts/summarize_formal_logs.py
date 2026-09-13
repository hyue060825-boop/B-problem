"""核验正式运行客户端原日志；缺失案例编码不以机器人编号替代。"""
from pathlib import Path
import json,hashlib,math,csv
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'results/formal/20260913';rows=[]
for p in sorted((D/'raw').glob('q[34]_[123].jsonl')):
 records=[json.loads(l) for l in p.read_text().splitlines() if l.strip()];ready=records[0];pending=None;ids=set();cleared=set();pos=(0.,0.);channel=1;vt=0.;errors=[];responses=[];deltas=[]
 for r in records:
  if r['status']=='REQUEST':
   assert pending is None
   pending=r
  elif r['status']=='RESPONSE':
   assert pending is not None and pending['path']==r['path'];req=pending['request'];pending=None;resp=r['response'];assert r['http_status']==200 and resp.get('accepted') is True
   assert req['request_id'] not in ids;ids.add(req['request_id']);responses.append(r)
   path=r['path'];expected=0.
   if path in ['/measure','/clear']:
    np=(req['position']['x'],req['position']['y']);expected=math.dist(pos,np)/5;pos=np
    if path=='/measure':
     expected+=5+(req['channel']!=channel);channel=req['channel']
    elif resp['clear_result']=='success':
     expected+=5;assert req['channel'] not in cleared;cleared.add(req['channel'])
    else:expected+=3
   actual=resp['virtual_time_s']-vt;deltas.append(abs(actual-expected));vt=resp['virtual_time_s']
 assert pending is None and records[-1]['status']=='EXITED' and max(deltas)<.001,(p,max(deltas))
 enter=next(r['response'] for r in responses if r['path']=='/enter');ex=next(r['response'] for r in responses if r['path']=='/exit')
 C=len(cleared);T=ex['virtual_time_s'];runtime=(ex['real_timestamp_ms']-enter['real_timestamp_ms'])/1000
 row={'log':p.name,'problem':ready['problem'],'test':int(p.stem[-1]),'case_code':None,'cleared_sources':C,'total_virtual_s':T,'mean_location_clear_s':T/C,'program_runtime_timestamp_s':runtime,'cleared_channels':sorted(cleared),'checkpoint_sha256':ready['checkpoint_sha256'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'exit_accepted':True,'max_action_cost_error_s':max(deltas),'request_count':len(ids),'enter_timestamp_ms':enter['real_timestamp_ms'],'exit_timestamp_ms':ex['real_timestamp_ms'],'source_count':None}
 assert ready['checkpoint_sha256'].startswith('51397bc8' if ready['problem']==3 else 'c8812ced');rows.append(row)
assert len(rows)==6
(D/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with (D/'summary.csv').open('w') as f:
 keys=['log','problem','test','case_code','cleared_sources','total_virtual_s','mean_location_clear_s','program_runtime_timestamp_s'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
for r in rows: print(r['log'],r['cleared_sources'],round(r['total_virtual_s'],6),round(r['mean_location_clear_s'],6),r['program_runtime_timestamp_s'])
