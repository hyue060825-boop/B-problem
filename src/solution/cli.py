import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description='几何证书约束的搜索定位清除系统')
    sub=p.add_subparsers(dest='command',required=True)
    for command in ['solve-q1','solve-q2']:
        q=sub.add_parser(command);q.add_argument('--input',required=True);q.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='solve-q1':
        from solution.evaluation.artifacts import q1_artifacts
        result=q1_artifacts(args.input,args.output)
    elif args.command=='solve-q2':
        from solution.planning.q2 import q2_artifacts
        result=q2_artifacts(args.input,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
