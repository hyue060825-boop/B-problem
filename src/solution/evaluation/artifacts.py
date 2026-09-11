"""结果数据和独立图件；使用显式输入，不伪造官方数值。"""
import json
import hashlib
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from solution.geometry.core import solve_q1


def dump(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def hash_files(paths):
    return {str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def plot_polygon(ax,vertices,label,**kwargs):
    v=np.asarray(vertices)
    if len(v):
        v=np.vstack([v,v[0]])
        ax.plot(v[:,0],v[:,1],label=label,**kwargs)
    ax.set_aspect('equal'); ax.set_xlabel('East x (m)');ax.set_ylabel('North y (m)')
    ax.grid(alpha=.2)


def q1_artifacts(input_path,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    inp=json.loads(Path(input_path).read_text())
    result=solve_q1(inp['observations'])
    dump(output/'input.json',inp);dump(output/'result.json',result)
    dump(output/'provenance.json',dict(source_hashes=hash_files(['src/solution/geometry/core.py']),input_sha256=hash_files([input_path])))
    if result['vertices']:
        fig,ax=plt.subplots(figsize=(6,5))
        plot_polygon(ax,result['vertices'],'Bearing intersection',color='#176D9C')
        ax.add_patch(Circle(result['diameter_circle_center'],result['diameter_m']/2,fill=False,color='#D65A31',label='Diameter circle'))
        ax.add_patch(Circle(result['mec']['center'],result['mec']['radius_m'],fill=False,color='#3C8D62',ls='--',label='Minimum enclosing circle'))
        ax.set_title('Explicit fixture; angular error ±1 degree')
        ax.legend();fig.tight_layout();fig.savefig(output/'geometry.png',dpi=180);fig.savefig(output/'geometry.pdf');plt.close(fig)
    return result
