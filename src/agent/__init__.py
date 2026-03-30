"""CellForge Agent agent module."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "SkillRegistry",
    "SkillExecutor",
    "ExecutionResult",
    "CancellationToken",
    "ProjectTerminationError",
    "SkillCritic",
    "CriticResult",
    "ReActAgent",
    "AgentConfig",
    "StepRecord",
    "AgentMemory",
    "ValidationResult",
    "NumericValidator",
    "VisualValidator",
    "ResultValidator",
    "DataConsistencyChecker",
    "AnalysisPlanner",
    "LLMPlanner",
    "DeepResearchEngine",
    "DeepResearchResult",
    "Reporter",
]

_EXPORT_MAP = {
    "SkillRegistry": ("src.agent.registry", "SkillRegistry"),
    "SkillExecutor": ("src.agent.executor", "SkillExecutor"),
    "ExecutionResult": ("src.agent.executor", "ExecutionResult"),
    "CancellationToken": ("src.agent.executor", "CancellationToken"),
    "ProjectTerminationError": ("src.agent.executor", "ProjectTerminationError"),
    "SkillCritic": ("src.agent.critic", "SkillCritic"),
    "CriticResult": ("src.agent.critic", "CriticResult"),
    "ReActAgent": ("src.agent.agent", "ReActAgent"),
    "AgentConfig": ("src.agent.agent", "AgentConfig"),
    "StepRecord": ("src.agent.agent", "StepRecord"),
    "AgentMemory": ("src.agent.memory", "AgentMemory"),
    "ValidationResult": ("src.agent.validator", "ValidationResult"),
    "NumericValidator": ("src.agent.validator", "NumericValidator"),
    "VisualValidator": ("src.agent.validator", "VisualValidator"),
    "ResultValidator": ("src.agent.validator", "ResultValidator"),
    "DataConsistencyChecker": ("src.agent.data_checker", "DataConsistencyChecker"),
    "AnalysisPlanner": ("src.agent.planner", "AnalysisPlanner"),
    "LLMPlanner": ("src.agent.planner", "LLMPlanner"),
    "DeepResearchEngine": ("src.agent.deep_research", "DeepResearchEngine"),
    "DeepResearchResult": ("src.agent.deep_research", "DeepResearchResult"),
    "Reporter": ("src.agent.reporter", "Reporter"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
