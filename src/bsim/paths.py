"""完整源码仓库中的资源位置；开发时使用可编辑安装。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "simulator"
PROBLEM = ROOT / "problem"
