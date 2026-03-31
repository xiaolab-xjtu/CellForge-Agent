#!/usr/bin/env python3
"""
ReAct Agent - Main agent brain implementing the ReAct+Skill loop.

Implements the enhanced loop:
Thought -> Act -> Observe -> Critic -> Adjust

The agent:
1. Maintains working memory with AnnData objects
2. Uses SkillRegistry for tool selection
3. Executes skills via SkillExecutor
4. Evaluates results via SkillCritic
5. Self-corrects based on critic feedback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agent.executor import CancellationToken, ProjectTerminationError

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for the agent."""
    skills_root: str | Path = "skills/"
    max_iterations: int = 10
    max_retries: int = 3
    checkpoint_dir: str | Path = "checkpoints/"
    output_dir: str | Path = "outputs/"
    project_name: str = "default_project"
    deep_research_enabled: bool = True
    numeric_validation: bool = True
    visual_validation: bool = True


@dataclass
class StepRecord:
    """Record of a single ReAct step."""
    step: int
    thought: str
    skill_id: str | None
    action: str
    observation: dict[str, Any]
    critic_result: "CriticResult | None" = None
    adjustment: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ReActAgent:
    """
    ReAct+Skill agent for single-cell analysis.

    The agent loop:
    1. PLANNING: Decide next skill based on manifest and context
    2. ACTION: Execute skill via SkillExecutor
    3. OBSERVATION: Extract metrics and output
    4. CRITIC: Evaluate via SkillCritic
    5. ADJUST: If critic fails, get parameter adjustments
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """
        Initialize the agent.

        Args:
            config: Agent configuration. Uses defaults if None.
        """
        from src.agent.registry import SkillRegistry
        from src.agent.executor import SkillExecutor
        from src.agent.critic import SkillCritic
        from src.agent.memory import AgentMemory
        from src.agent.validator import ResultValidator
        from src.agent.data_checker import DataConsistencyChecker
        from src.agent.planner import AnalysisPlanner, LLMPlanner
        from src.agent.capability_router import CapabilityRouter
        from src.core.api_client import APIClient
        from src.core.config import LIBRARY_ROOT

        self.config = config or AgentConfig()

        self._registry = SkillRegistry(LIBRARY_ROOT)
        self._registry.scan()

        self._capability_router = CapabilityRouter(LIBRARY_ROOT)
        self._capability_router.scan()

        self._executor = SkillExecutor(self._registry)
        self._critic = SkillCritic()
        self._memory = AgentMemory(
            output_dir=Path(self.config.output_dir),
            project_name=self.config.project_name,
            checkpoint_dir=Path(self.config.checkpoint_dir),
        )

        self._api_client = APIClient()
        self._validator = ResultValidator(api_client=self._api_client)
        self._data_checker = DataConsistencyChecker()
        self._planner = AnalysisPlanner()
        self._llm_planner = LLMPlanner(
            api_client=self._api_client,
            registry=self._registry,
            max_retries=self.config.max_retries,
            capability_router=self._capability_router,
        )

        self._adata: Any = None
        self._steps: list[StepRecord] = []
        self._iteration = 0
        self._background: str = ""
        self._research: str = ""
        self._plan: list[dict[str, Any]] = []

    @property
    def manifest(self) -> list[dict[str, str]]:
        """Get tool manifest for planning."""
        return self._registry.get_tool_manifest()

    @property
    def capabilities(self) -> list[dict]:
        """Get capability manifest with skills grouped under each capability."""
        cap_manifest = self._capability_router.get_capability_manifest()
        skills_by_cap = {}
        for entry in self._registry.get_tool_manifest():
            cap = entry.get("capability", "")
            skills_by_cap.setdefault(cap, []).append(entry)

        result = []
        for cap in cap_manifest:
            result.append({
                **cap,
                "skills": skills_by_cap.get(cap["id"], []),
            })
        return result

    @property
    def adata(self) -> Any:
        """Get current AnnData object."""
        return self._adata

    @property
    def steps(self) -> list[StepRecord]:
        """Get execution history."""
        return self._steps

    @property
    def plan(self) -> list[dict[str, Any]]:
        """Get current analysis plan."""
        return self._plan

    def initialize(
        self,
        project_path: str | Path | None = None,
        background: str = "",
        research: str = "",
    ) -> dict[str, Any]:
        """
        Initialize the agent with project data.

        Args:
            project_path: Path to project directory.
            background: Background description text.
            research: Research question text.

        Returns:
            dict with initialization results.
        """
        results: dict[str, Any] = {
            "status": "initialized",
            "data_loaded": False,
            "background_loaded": bool(background),
            "research_loaded": bool(research),
            "issues": [],
            "warnings": [],
        }

        self._background = background
        self._research = research

        if project_path:
            project_path = Path(project_path)
            input_dir = self._find_input_dir(project_path)

            if input_dir:
                results["input_dir"] = str(input_dir)

                h5ad_files = list(input_dir.glob("*.h5ad"))
                if not h5ad_files:
                    h5ad_files = list(input_dir.glob("**/*.h5ad"))

                if h5ad_files:
                    self._adata = self._load_h5ad(h5ad_files[0])
                    results["data_loaded"] = True
                    results["data_summary"] = {
                        "n_cells": self._adata.n_obs,
                        "n_genes": self._adata.n_vars,
                        "file": str(h5ad_files[0]),
                    }

                bg_file = input_dir / "background.txt"
                if not bg_file.exists():
                    bg_file = input_dir / "Background.txt"
                if bg_file.exists():
                    with open(bg_file, "r", encoding="utf-8") as f:
                        self._background = f.read()
                    results["background_loaded"] = True

                research_file = input_dir / "Research.txt"
                if not research_file.exists():
                    research_file = input_dir / "research.txt"
                if research_file.exists():
                    with open(research_file, "r", encoding="utf-8") as f:
                        self._research = f.read()
                    results["research_loaded"] = True

        if self._adata is not None:
            consistency_check = self._data_checker.check(
                self._adata, self._background, self._research
            )
            results["consistency_check"] = consistency_check

            if not consistency_check["consistent"]:
                results["warnings"].extend(consistency_check["issues"])

            existing_analysis = self._data_checker.check_existing_analysis(
                self._adata
            )
            results["existing_analysis"] = existing_analysis

        self._memory.initialize(
            project_name=self.config.project_name,
            background=self._background,
            research=self._research,
        )

        logger.info("Agent initialized: %s", results)
        return results

    def _find_input_dir(self, project_path: Path) -> Path | None:
        """Find input directory with h5ad files."""
        candidates = [
            project_path / "inputs",
            project_path / f"{project_path.name}",
            project_path,
        ]

        for candidate in candidates:
            if candidate.exists():
                if (candidate / "inputs").exists():
                    return candidate / "inputs"
                if list(candidate.glob("*.h5ad")):
                    return candidate
                if list(candidate.glob("**/*.h5ad")):
                    return candidate

        return None

    def _load_h5ad(self, path: Path) -> Any:
        """Load h5ad file."""
        import scanpy as sc
        return sc.read_h5ad(str(path))

    def plan_analysis(
        self,
        existing_analysis: dict[str, Any] | None = None,
        user_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Create analysis plan based on context using LLM.

        Args:
            existing_analysis: Types of existing analysis in data.
            user_config: User-specified configuration.

        Returns:
            List of step dicts.
        """
        obs_columns = list(self._adata.obs.columns) if self._adata is not None else []
        data_state = {
            "n_cells": self._adata.n_obs if self._adata is not None else 0,
            "n_genes": self._adata.n_vars if self._adata is not None else 0,
            "existing_types": existing_analysis.get("types", []) if existing_analysis else [],
            "obs_columns": obs_columns,
        }

        self._plan = self._llm_planner.create_initial_plan(
            background=self._background,
            research=self._research,
            data_state=data_state,
        )

        logger.info("Created plan with %d steps", len(self._plan))
        return self._plan

    def load_data(self, adata_or_path: Any) -> None:
        """
        Load input data into working memory.

        Args:
            adata_or_path: AnnData object or path to h5ad file.
        """
        if isinstance(adata_or_path, str | Path):
            self._adata = self._load_h5ad(Path(adata_or_path))
        else:
            self._adata = adata_or_path

        logger.info(
            "Loaded data: %d cells x %d genes",
            self._adata.n_obs,
            self._adata.n_vars,
        )

    def execute_skill(
        self,
        skill_id: str,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> StepRecord:
        """
        Execute a single skill with the ReAct loop.

        Args:
            skill_id: Skill to execute.
            params: Skill parameters.
            context: Context for critic evaluation.

        Returns:
            StepRecord with execution details.
        """
        self._iteration += 1
        thought = f"Select {skill_id} for analysis step"

        logger.info("Step %d: Executing %s", self._iteration, skill_id)

        execution_result = self._executor.execute(
            skill_id=skill_id,
            input_data=self._adata,
            params=params,
            context=context,
        )

        observation: dict[str, Any] = {
            "success": execution_result.success,
            "metrics": execution_result.metrics,
            "output_available": execution_result.output is not None,
        }

        step = StepRecord(
            step=self._iteration,
            thought=thought,
            skill_id=skill_id,
            action=f"Executed {skill_id}",
            observation=observation,
        )

        if execution_result.output is not None:
            self._adata = execution_result.output

        critic_result = self._critic.evaluate(execution_result, context)
        step.critic_result = critic_result

        if not critic_result.success and critic_result.has_adjustments():
            step.adjustment = {
                "reason": critic_result.feedback,
                "suggestions": critic_result.adjustments,
            }

        if self.config.numeric_validation and self._adata is not None:
            validation = self._validator.validate_step(self._adata, skill_id)
            step.validation = validation
            observation["validation"] = validation

        self._steps.append(step)
        return step

    def execute_step(
        self,
        step: dict[str, Any],
    ) -> StepRecord:
        """
        Execute an analysis step from the plan.

        Args:
            step: Step dict with name, skill_id, parameters, etc.

        Returns:
            StepRecord with execution details.
        """
        step_name = step.get("name", "unknown")
        skill_id = step.get("skill_id") or step.get("tool", "")
        params = step.get("parameters", {})
        context = step.get("context", {})

        self._iteration += 1
        thought = f"Execute {step_name}: {self._planner.get_step_purpose(step_name)}"

        logger.info(
            "Step %d: Executing %s (skill: %s)",
            self._iteration,
            step_name,
            skill_id,
        )

        if not skill_id:
            return StepRecord(
                step=self._iteration,
                thought=thought,
                skill_id=None,
                action=f"Skipped {step_name} - no skill_id",
                observation={"success": False, "error": "No skill_id"},
            )

        if self._registry.get_skill_spec(skill_id) is None:
            logger.warning(f"Skill {skill_id} not found, trying fuzzy match for '{step_name}'")
            matched = self._registry.fuzzy_match_skill(step_name)
            if matched:
                logger.info(f"Fuzzy matched '{step_name}' to '{matched}'")
                skill_id = matched
            else:
                logger.error(f"No skill found for step: {step_name}")
                return StepRecord(
                    step=self._iteration,
                    thought=thought,
                    skill_id=None,
                    action=f"Skipped {step_name} - skill not found",
                    observation={"success": False, "error": f"Skill not found for step: {step_name}"},
                )

        execution_result = self._executor.execute(
            skill_id=skill_id,
            input_data=self._adata,
            params=params,
            context=context,
            output_dir=self._memory.output_dir / "Figures",
        )

        observation: dict[str, Any] = {
            "success": execution_result.success,
            "metrics": execution_result.metrics,
            "output_available": execution_result.output is not None,
        }

        step_record = StepRecord(
            step=self._iteration,
            thought=thought,
            skill_id=skill_id,
            action=f"Executed {step_name} via {skill_id}",
            observation=observation,
        )

        if execution_result.output is not None:
            self._adata = execution_result.output

        critic_result = self._critic.evaluate(execution_result, context, self._adata)
        step_record.critic_result = critic_result

        if not critic_result.success and critic_result.has_adjustments():
            step_record.adjustment = {
                "reason": critic_result.feedback,
                "suggestions": critic_result.adjustments,
            }

        if self.config.numeric_validation and self._adata is not None:
            validation = self._validator.validate_step(self._adata, step_name)
            step_record.validation = validation
            observation["validation"] = validation

        self._steps.append(step_record)
        return step_record

    def execute_step_with_retry(
        self,
        step: dict[str, Any],
        cancellation_token: CancellationToken | None = None,
    ) -> StepRecord:
        """
        Execute a step with retry logic on failure.

        Args:
            step: Step dict with skill_id, initial_params, etc.
            cancellation_token: Token to signal cancellation.

        Returns:
            StepRecord with final execution result.

        Raises:
            ProjectTerminationError: If step fails unrecoverably or cancellation requested.
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        cancellation_token.check_and_raise()

        current_step = step.copy()
        attempt = 0
        last_error = None
        termination_raised = False

        while attempt < self._llm_planner.max_retries:
            cancellation_token.check_and_raise()

            step_record = self.execute_step(current_step)

            if step_record.observation.get("success"):
                return step_record

            last_error = step_record.observation.get("error", "Unknown error")
            logger.warning(
                "Step %d failed (attempt %d/%d): %s",
                step["step_id"],
                attempt + 1,
                self._llm_planner.max_retries,
                last_error,
            )

            skill_spec = self._registry.get_skill_spec(current_step.get("skill_id", ""))
            if not skill_spec:
                logger.error("Could not get skill spec for %s", current_step.get("skill_id"))
                break

            adjusted = self._llm_planner.adjust_on_failure(
                current_step, last_error, skill_spec, attempt
            )

            if adjusted is None:
                logger.info("Cannot adjust step %d after %d attempts", step["step_id"], attempt + 1)

                should_terminate = self._should_terminate_project(
                    step, last_error, skill_spec
                )

                if should_terminate:
                    termination_raised = True
                    suggestion = self._get_termination_suggestion(step, last_error, skill_spec)
                    raise ProjectTerminationError(
                        f"Step {step['step_id']} ({step.get('skill_id', 'unknown')}) failed unrecoverably: {last_error}",
                        step_id=step["step_id"],
                        suggestion=suggestion,
                    )
                break

            current_step = adjusted
            attempt += 1

        step_record.observation["retry_attempts"] = attempt
        step_record.observation["final_error"] = last_error
        step_record.observation["termination_raised"] = termination_raised
        return step_record

    def _should_terminate_project(
        self,
        step: dict[str, Any],
        error: str,
        skill_spec: dict[str, Any],
    ) -> bool:
        """
        Determine if a step failure should terminate the entire project.

        Args:
            step: The failed step.
            error: Error message.
            skill_spec: Skill specification.

        Returns:
            True if project should be terminated.
        """
        error_lower = error.lower()
        skill_id = step.get("skill_id", "").lower()

        critical_steps = ["scanpy_qc", "scanpy_normalize"]
        critical_errors = [
            "data is empty",
            "cannot read",
            "file not found",
            "permission denied",
            "out of memory",
            "data too large",
        ]

        if skill_id in critical_steps:
            for crit_err in critical_errors:
                if crit_err in error_lower:
                    return True

        if "qc" in skill_id:
            if "too few cells" in error_lower or "insufficient cells" in error_lower:
                return True

        if "normalize" in skill_id:
            if "invalid value" in error_lower or "divide by zero" in error_lower:
                return True

        return False

    def _get_termination_suggestion(
        self,
        step: dict[str, Any],
        error: str,
        skill_spec: dict[str, Any],
    ) -> str:
        """
        Get user-friendly suggestion when project is terminated.

        Args:
            step: The failed step.
            error: Error message.
            skill_spec: Skill specification.

        Returns:
            Suggestion string for the user.
        """
        skill_id = step.get("skill_id", "")
        error_lower = error.lower()

        suggestions = {
            "scanpy_qc": "Your data may need pre-filtering or may be of insufficient quality. "
                        "Try: (1) Check if cells were properly preserved, (2) Adjust QC thresholds, "
                        "(3) Use pre-filtered data if available.",
            "scanpy_normalize": "Normalization failed. Check if your data contains valid expression values. "
                               "Try: (1) Ensure no negative values, (2) Check for NaN/Inf values.",
            "default": "The analysis could not proceed due to an unrecoverable error. "
                      "Please check your input data and parameters, then try again.",
        }

        if skill_id in suggestions:
            return suggestions[skill_id]
        return suggestions["default"]

    def run_pipeline(
        self,
        skill_sequence: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]]
        | None = None,
    ) -> list[StepRecord]:
        """
        Run a pipeline of skills.

        Args:
            skill_sequence: List of (skill_id, params, context) tuples.
                           If None, uses self._plan.

        Returns:
            List of StepRecords.
        """
        if skill_sequence:
            for skill_id, params, context in skill_sequence:
                self.execute_skill(skill_id, params, context)

                if self._iteration >= self.config.max_iterations:
                    logger.warning(
                        "Max iterations (%d) reached", self.config.max_iterations
                    )
                    break
        elif self._plan:
            for step in self._plan:
                self.execute_step_with_retry(step)

                if self._iteration >= self.config.max_iterations:
                    logger.warning(
                        "Max iterations (%d) reached", self.config.max_iterations
                    )
                    break

        return self._steps

    def run(
        self,
        project_path: str | Path | None = None,
        background: str = "",
        research: str = "",
    ) -> dict[str, Any]:
        """
        Run the complete analysis pipeline.

        Args:
            project_path: Path to project directory.
            background: Background description.
            research: Research question.

        Returns:
            dict with results.
        """
        results: dict[str, Any] = {
            "status": "running",
            "steps_completed": 0,
            "steps_failed": 0,
            "report": None,
        }

        init_result = self.initialize(project_path, background, research)
        results["initialization"] = init_result

        if not init_result.get("data_loaded"):
            results["status"] = "failed"
            results["error"] = "Failed to load data"
            return results

        existing = init_result.get("existing_analysis", {})
        self.plan_analysis(existing_analysis=existing)
        results["plan"] = self._plan

        cancellation_token = CancellationToken()

        for step in self._plan:
            if step.get("status") == "skipped":
                continue

            try:
                step_result = self.execute_step_with_retry(step, cancellation_token)

                if step_result.observation.get("success"):
                    results["steps_completed"] += 1
                else:
                    results["steps_failed"] += 1

                    if results["steps_failed"] >= self.config.max_retries:
                        results["status"] = "stopped"
                        results["error"] = "Too many failures, stopping"
                        break

            except ProjectTerminationError as e:
                results["status"] = "terminated"
                results["termination_error"] = str(e)
                results["termination_step_id"] = e.step_id
                results["suggestion"] = e.suggestion
                results["report"] = self.generate_report()
                logger.error("Project terminated: %s", e)
                return results

        if results["status"] == "running":
            results["status"] = "completed"

        results["report"] = self.generate_report()

        return results

    def save_checkpoint(self, name: str | None = None) -> Path | None:
        """Save current AnnData state to checkpoint."""
        if self._adata is None:
            return None
        return self._memory.save_adata_checkpoint(self._adata, name)

    def save_memory(self) -> Path:
        """Save execution history to memory.json."""
        return self._memory.save_execution_log(self._steps)

    def get_available_skills(self) -> list[dict[str, str]]:
        """Get all available skills."""
        return self._registry.get_tool_manifest()

    def search_skills(self, query: str) -> list[dict[str, str]]:
        """Search skills by keyword."""
        return self._registry.search(query)

    def generate_report(self) -> str:
        """Generate markdown report."""
        lines = []

        lines.append(f"# Single-Cell Transcriptomics Analysis Report\n")
        lines.append(f"**Project**: {self.config.project_name}\n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        lines.append("\n## Data Overview\n")
        if self._adata is not None:
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Cells | {self._adata.n_obs:,} |")
            lines.append(f"| Genes | {self._adata.n_vars:,} |")

            if "leiden" in self._adata.obs:
                n_clusters = self._adata.obs["leiden"].nunique()
                lines.append(f"| Clusters | {n_clusters} |")

        lines.append("\n## Analysis Steps\n")
        lines.append("| Step | Status | Skill | Params |")
        lines.append("|------|--------|-------|--------|")
        for step in self._steps:
            status = "✓" if step.observation.get("success") else "✗"
            skill = step.skill_id or "N/A"
            params = (
                str(step.observation.get("metrics", {}))[:50]
                if step.observation.get("metrics")
                else "-"
            )
            lines.append(f"| {step.step} | {status} | {skill} | {params} |")

        return "\n".join(lines)
