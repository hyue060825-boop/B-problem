"""最终资产路径与分析输出检查。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require_report_workspace(path):
    """旧报告入口在输入目录输出；先复制到新工作目录再运行。"""
    target = Path(path).resolve()
    for name in ('final-20260913', 'final-8ef9ef8', 'history', 'formal'):
        if target.is_relative_to(ROOT / 'results' / name):
            raise ValueError('归档目录只读。请复制所需实验到新工作目录，再通过 --input 指定。')
    return target
