#!/usr/bin/env python3
"""
SkillExecutor - Executes skills with memory object passing and parameter management.

Handles:
- On-demand skill spec loading
- Code template execution with AnnData objects
- Parameter injection and default handling
- Execution result wrapping with metrics
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scAgent_v2.src.agent.registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Executes skill code templates with proper parameter handling.

    Skills follow a three-layer structure:
    - execution_layer.code_template: The code to run
    - cognitive_layer: Metadata (purpose, parameter_impact)
    - critic_layer: Post-processing and success criteria
    """

    def __init__(self, registry: "SkillRegistry") -> None:
        """
        Initialize executor with a skill registry.

        Args:
            registry: SkillRegistry instance for loading skill specs.
        """
        self._registry = registry

    def execute(
        self,
        skill_id: str,
        input_data: Any = None,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        output_dir: str | Path | None = None,
    ) -> ExecutionResult:
        """
        Execute a skill by skill_id.

        Args:
            skill_id: The skill identifier.
            input_data: Input AnnData object or path to h5ad file.
            params: Agent-specified parameters (override defaults).
            context: Context info for critic layer (e.g., protocol).
            output_dir: Directory for saving output files (figures, etc.).

        Returns:
            ExecutionResult with output, metrics, and success status.
        """
        skill_spec = self._registry.get_skill_spec(skill_id)
        if skill_spec is None:
            return ExecutionResult(
                success=False,
                error=f"Skill not found: {skill_id}",
                output=None,
                metrics={},
            )

        execution_layer = skill_spec.get("execution_layer", {})
        code_template = execution_layer.get("code_template", "")
        default_params = execution_layer.get("default_params", {})

        agent_params = params or {}
        current_params = {**default_params, **agent_params}

        try:
            output = self._execute_code(
                code_template,
                input_data,
                current_params,
                context or {},
                output_dir,
            )

            metrics = self._extract_metrics(output, skill_spec, context)

            return ExecutionResult(
                success=True,
                error=None,
                output=output,
                metrics=metrics,
                skill_spec=skill_spec,
            )

        except Exception as e:
            logger.exception("Skill execution failed: %s", skill_id)
            return ExecutionResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                output=None,
                metrics={},
            )

    def _execute_code(
        self,
        code_template: str,
        input_data: Any,
        params: dict[str, Any],
        context: dict[str, Any],
        output_dir: str | Path | None = None,
    ) -> Any:
        """
        Execute the skill's code template.

        The code template receives:
        - input_data: AnnData object
        - params_dict: merged parameters
        - context: context dict
        - output_dir: directory for saving files

        Returns the output (typically AnnData).
        """
        import anndata as ad
        import scanpy as sc
        import os
        import sys
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        adata = input_data
        if isinstance(input_data, str | Path):
            adata = sc.read(input_data)

        output_dir_str = str(output_dir) if output_dir else None

        local_vars = {
            "input_data": adata,
            "params_dict": params,
            "context": context,
            "output_dir": output_dir_str,
            "result": None,
            "adata": None,
            "output_data": None,
        }

        exec_globals = {
            "anndata": ad,
            "ad": ad,
            "sc": sc,
            "os": os,
            "sys": sys,
            "plt": plt,
            "matplotlib": matplotlib,
        }

        exec(code_template, exec_globals, local_vars)

        if local_vars.get("result") is not None:
            return local_vars["result"]
        if local_vars.get("adata") is not None:
            return local_vars["adata"]
        if local_vars.get("output_data") is not None:
            return local_vars["output_data"]

        for key, value in local_vars.items():
            if key.startswith("run_") and callable(value):
                try:
                    result = value(
                        input_data=adata,
                        params_dict=params,
                        default_params=None,
                        output_dir=output_dir_str,
                    )
                except TypeError as e:
                    if "output_dir" in str(e):
                        result = value(
                            input_data=adata,
                            params_dict=params,
                            default_params=None,
                        )
                    else:
                        raise
                if result is not None:
                    local_vars["result"] = result
                    return result

        return adata

    def _extract_metrics(
        self,
        output: Any,
        skill_spec: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Extract metrics from output using critic_layer logic."""
        if output is None:
            return {}

        critic_layer = skill_spec.get("critic_layer", {})
        metrics_to_extract = critic_layer.get("metrics_to_extract", [])

        extracted = {}
        if hasattr(output, "uns") and "analysis_history" in output.uns:
            last_entry = output.uns["analysis_history"][-1]
            for key in metrics_to_extract:
                if key in last_entry.get("metrics", {}):
                    extracted[key] = last_entry["metrics"][key]

        if hasattr(output, "n_obs"):
            extracted["n_cells"] = output.n_obs
        if hasattr(output, "n_vars"):
            extracted["n_genes"] = output.n_vars

        return extracted


from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result of a skill execution."""
    success: bool
    error: str | None
    output: Any
    metrics: dict[str, Any]
    skill_spec: dict[str, Any] | None = None

    @property
    def feedback(self) -> str | None:
        """Generate feedback message based on execution."""
        if self.success:
            return None
        return self.error
