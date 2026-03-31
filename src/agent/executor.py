#!/usr/bin/env python3
"""
SkillExecutor - Executes skills with memory object passing and parameter management.

Handles:
- On-demand skill spec loading
- Code template execution with AnnData objects
- Parameter injection and default handling
- Execution result wrapping with metrics
- Async execution with cancellation support
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agent.registry import SkillRegistry

logger = logging.getLogger(__name__)


class ProjectTerminationError(Exception):
    """Raised when a project should be terminated due to unrecoverable failure."""
    
    def __init__(self, message: str, step_id: int | None = None, suggestion: str | None = None):
        super().__init__(message)
        self.step_id = step_id
        self.suggestion = suggestion or "Please check your data quality or adjust parameters."


class CancellationToken:
    """Thread-safe cancellation token for aborting long-running operations."""
    
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
    
    def cancel(self):
        """Request cancellation."""
        with self._lock:
            self._cancelled = True
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        with self._lock:
            return self._cancelled
    
    def check_and_raise(self):
        """Check cancellation and raise if requested."""
        if self.is_cancelled:
            raise ProjectTerminationError("Operation cancelled by user", step_id=None)


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
        default_params = execution_layer.get("default_params", {})

        # Prefer external script file (e.g. run.py) over inline code_template
        script_name = execution_layer.get("script")
        if script_name:
            skill_dir = self._registry.get_skill_dir(skill_id)
            if skill_dir is None:
                return ExecutionResult(
                    success=False,
                    error=f"Cannot resolve skill directory for: {skill_id}",
                    output=None,
                    metrics={},
                )
            script_path = skill_dir / script_name
            if not script_path.exists():
                return ExecutionResult(
                    success=False,
                    error=f"Script not found: {script_path}",
                    output=None,
                    metrics={},
                )
            code_template = script_path.read_text(encoding="utf-8")
        else:
            _raw_code = execution_layer.get("code_template", "")
            # code_template may be stored as a list of lines or a plain string
            code_template = "\n".join(_raw_code) if isinstance(_raw_code, list) else _raw_code

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

    def execute_async(
        self,
        skill_id: str,
        input_data: Any = None,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        output_dir: str | Path | None = None,
        cancellation_token: CancellationToken | None = None,
        max_workers: int = 4,
    ) -> tuple[Future, CancellationToken]:
        """
        Execute a skill asynchronously in a thread pool.

        Args:
            skill_id: The skill identifier.
            input_data: Input AnnData object or path to h5ad file.
            params: Agent-specified parameters (override defaults).
            context: Context info for critic layer.
            output_dir: Directory for saving output files.
            cancellation_token: Token to signal cancellation.
            max_workers: Max threads in pool (default 4).

        Returns:
            Tuple of (Future, CancellationToken) where Future can be used to
            retrieve result later via future.result().
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        def _execute_with_cancellation():
            if cancellation_token.is_cancelled:
                return ExecutionResult(
                    success=False,
                    error="Operation cancelled before start",
                    output=None,
                    metrics={},
                )
            try:
                return self.execute(skill_id, input_data, params, context, output_dir)
            except ProjectTerminationError:
                raise
            except Exception as e:
                logger.exception("Async execution failed for %s", skill_id)
                return ExecutionResult(
                    success=False,
                    error=f"{type(e).__name__}: {e}",
                    output=None,
                    metrics={},
                )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future = executor.submit(_execute_with_cancellation)
        return future, cancellation_token

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
        import pandas as pd
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

        import datetime as dt
        import numpy as np

        exec_globals = {
            "anndata": ad,
            "ad": ad,
            "sc": sc,
            "os": os,
            "sys": sys,
            "plt": plt,
            "matplotlib": matplotlib,
            "pd": pd,
            "datetime": dt,
            "np": np,
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
