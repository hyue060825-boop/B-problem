"""BC/DAgger/PPO entry points with honest NOT_RUN behavior."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class TrainingStatus:
    status: str
    reason: str
    checkpoint: str | None = None


def require_authorized_research(config):
    if config.get("profile") != "compatible_research" or not config.get("authorized", False):
        return TrainingStatus("BLOCKED", "研究profile未获用户明确授权；官方联合分布和误差场仍未决")
    if not config.get("env_ready", False):
        return TrainingStatus("BLOCKED", "训练环境/算力未就绪")
    return None


def train_bc(config_path):
    config = json.loads(Path(config_path).read_text())
    blocked = require_authorized_research(config)
    return blocked or TrainingStatus("NOT_RUN", "本实现提供训练接口；本次没有启动研究训练")


def train_dagger(config_path):
    return train_bc(config_path)


def train_ppo(config_path):
    return train_bc(config_path)
