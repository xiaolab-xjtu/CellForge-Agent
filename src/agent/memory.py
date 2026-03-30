#!/usr/bin/env python3
"""
AgentMemory - Memory and checkpoint management for CellForge Agent.

Handles:
- Decision trail and parameter adjustment logs
- Critical intermediate adata states
- Project-level memory.json persistence
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _clean_for_hdf5(obj: Any) -> Any:
    """
    Recursively clean an object for HDF5 serialization.

    Converts numpy types, datetime objects, None, and other non-standard types
    to JSON-serializable formats that HDF5/h5py can handle.
    """
    if obj is None:
        return "None"
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _clean_for_hdf5(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_hdf5(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


class AgentMemory:
    """
    Manages memory persistence and checkpoints for agent executions.

    Key files:
    - memory.json: All decisions, critic feedback, parameter adjustments
    - checkpoints/: Intermediate adata states at key analysis nodes
    """

    def __init__(
        self,
        output_dir: Path | str = "outputs/",
        project_name: str = "default_project",
        checkpoint_dir: Path | str = "checkpoints/",
    ) -> None:
        """
        Initialize memory manager.

        Args:
            output_dir: Root directory for outputs (may include project name).
            project_name: Project subdirectory name.
            checkpoint_dir: Directory for adata checkpoints.
        """
        output_path = Path(output_dir)
        checkpoint_path = Path(checkpoint_dir)
        
        if output_path.name == project_name:
            self._output_dir = output_path
        else:
            self._output_dir = output_path / project_name
        
        if checkpoint_path.name == project_name:
            self._checkpoint_dir = checkpoint_path
        else:
            self._checkpoint_dir = checkpoint_path / project_name

        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self._memory_file = self._output_dir / "memory.json"
        self._load_existing_memory()

    def _load_existing_memory(self) -> None:
        """Load existing memory.json if present."""
        if self._memory_file.exists():
            try:
                with open(self._memory_file, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Corrupted memory.json, starting fresh")
                self._memory = self._init_memory()
        else:
            self._memory = self._init_memory()

    def _init_memory(self) -> dict[str, Any]:
        """Initialize new memory structure."""
        return {
            "project_name": self._output_dir.name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "decisions": [],
            "critic_feedback": [],
            "parameter_adjustments": [],
            "checkpoints": [],
        }

    def log_decision(
        self,
        skill_id: str,
        thought: str,
        action: str,
        reasoning: str | None = None,
    ) -> None:
        """
        Log a decision made during planning.

        Args:
            skill_id: Skill that was selected.
            thought: The reasoning behind the choice.
            action: What action was taken.
            reasoning: Optional deeper reasoning.
        """
        self._memory["decisions"].append({
            "skill_id": skill_id,
            "thought": thought,
            "action": action,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
        })
        self._memory["updated_at"] = datetime.now().isoformat()

    def log_critic_feedback(
        self,
        skill_id: str,
        success: bool,
        feedback: str | None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """
        Log critic evaluation result.

        Args:
            skill_id: Skill that was evaluated.
            success: Whether execution was successful.
            feedback: Feedback message.
            metrics: Extracted metrics.
        """
        self._memory["critic_feedback"].append({
            "skill_id": skill_id,
            "success": success,
            "feedback": feedback,
            "metrics": metrics or {},
            "timestamp": datetime.now().isoformat(),
        })
        self._memory["updated_at"] = datetime.now().isoformat()

    def log_parameter_adjustment(
        self,
        skill_id: str,
        parameter: str,
        previous_value: Any,
        new_value: Any,
        reason: str,
        causal_chain: str | None = None,
    ) -> None:
        """
        Log a parameter adjustment based on critic feedback.

        Args:
            skill_id: Skill with parameter adjusted.
            parameter: Parameter name.
            previous_value: Original value.
            new_value: Adjusted value.
            reason: Why adjustment was made.
            causal_chain: Causal explanation from guide.
        """
        self._memory["parameter_adjustments"].append({
            "skill_id": skill_id,
            "parameter": parameter,
            "previous_value": previous_value,
            "new_value": new_value,
            "reason": reason,
            "causal_chain": causal_chain,
            "timestamp": datetime.now().isoformat(),
        })
        self._memory["updated_at"] = datetime.now().isoformat()

    def save_adata_checkpoint(
        self,
        adata: Any,
        name: str | None = None,
    ) -> Path:
        """
        Save intermediate AnnData state.

        Args:
            adata: AnnData object to save.
            name: Optional checkpoint name.

        Returns:
            Path to saved checkpoint file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_name = name or f"checkpoint_{timestamp}"
        checkpoint_path = self._checkpoint_dir / f"{checkpoint_name}.h5ad"
        history_path = self._checkpoint_dir / f"{checkpoint_name}_history.json"

        analysis_history = adata.uns.pop("analysis_history", None)

        adata.write_h5ad(checkpoint_path)

        if analysis_history is not None:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(analysis_history, f, ensure_ascii=False, indent=2)

        if analysis_history is not None:
            adata.uns["analysis_history"] = analysis_history

        self._memory["checkpoints"].append({
            "name": checkpoint_name,
            "path": str(checkpoint_path),
            "n_cells": adata.n_obs,
            "n_genes": adata.n_vars,
            "timestamp": datetime.now().isoformat(),
        })
        self._memory["updated_at"] = datetime.now().isoformat()

        logger.info("Saved checkpoint: %s", checkpoint_path)
        return checkpoint_path

    def save_execution_log(self, steps: list[Any]) -> Path:
        """
        Save complete execution history to memory.json.

        Args:
            steps: List of StepRecord objects.

        Returns:
            Path to saved memory file.
        """
        for step in steps:
            self.log_decision(
                skill_id=step.skill_id or "unknown",
                thought=step.thought,
                action=step.action,
            )

            if step.critic_result:
                self.log_critic_feedback(
                    skill_id=step.skill_id or "unknown",
                    success=step.critic_result.success,
                    feedback=step.critic_result.feedback,
                    metrics=step.critic_result.metrics,
                )

            if step.adjustment:
                for sugg in step.adjustment.get("suggestions", []):
                    self.log_parameter_adjustment(
                        skill_id=step.skill_id or "unknown",
                        parameter=sugg.get("parameter", ""),
                        previous_value="auto",
                        new_value=sugg.get("action", ""),
                        reason=step.adjustment.get("reason", ""),
                        causal_chain=sugg.get("causal_chain", ""),
                    )

        with open(self._memory_file, "w", encoding="utf-8") as f:
            json.dump(self._memory, f, indent=2, ensure_ascii=False)

        logger.info("Saved memory: %s", self._memory_file)
        return self._memory_file

    def initialize(
        self,
        project_name: str | None = None,
        background: str = "",
        research: str = "",
    ) -> None:
        """
        Initialize memory with project context.

        Args:
            project_name: Project name override.
            background: Background description.
            research: Research question.
        """
        if project_name:
            self._memory["project_name"] = project_name

        self._memory["background"] = background
        self._memory["research"] = research
        self._memory["initialized_at"] = datetime.now().isoformat()
        self._memory["updated_at"] = datetime.now().isoformat()

    @property
    def memory(self) -> dict[str, Any]:
        """Get current memory dict."""
        return self._memory

    @property
    def checkpoint_dir(self) -> Path:
        """Get checkpoint directory."""
        return self._checkpoint_dir

    @property
    def output_dir(self) -> Path:
        """Get output directory."""
        return self._output_dir
