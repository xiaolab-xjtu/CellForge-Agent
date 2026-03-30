"""CellForge Agent - Single-cell Analysis Agent with ReAct+Skill architecture."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "SkillRegistry",
    "SkillExecutor",
    "ExecutionResult",
    "SkillCritic",
    "CriticResult",
    "ReActAgent",
    "AgentConfig",
    "StepRecord",
    "AgentMemory",
]

_EXPORT_MAP = {
    "SkillRegistry": ("src.agent.registry", "SkillRegistry"),
    "SkillExecutor": ("src.agent.executor", "SkillExecutor"),
    "ExecutionResult": ("src.agent.executor", "ExecutionResult"),
    "SkillCritic": ("src.agent.critic", "SkillCritic"),
    "CriticResult": ("src.agent.critic", "CriticResult"),
    "ReActAgent": ("src.agent.agent", "ReActAgent"),
    "AgentConfig": ("src.agent.agent", "AgentConfig"),
    "StepRecord": ("src.agent.agent", "StepRecord"),
    "AgentMemory": ("src.agent.memory", "AgentMemory"),
}


def __getattr__(name: str) -> Any:
    """Lazily load exports to avoid hard dependency imports at package import time."""
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
