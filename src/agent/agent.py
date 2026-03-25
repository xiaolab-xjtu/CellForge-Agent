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
        from scAgent_v2.src.agent.registry import SkillRegistry
        from scAgent_v2.src.agent.executor import SkillExecutor
        from scAgent_v2.src.agent.critic import SkillCritic
        from scAgent_v2.src.agent.memory import AgentMemory
        from scAgent_v2.src.agent.validator import ResultValidator
        from scAgent_v2.src.agent.data_checker import DataConsistencyChecker
        from scAgent_v2.src.agent.planner import AnalysisPlanner
        from scAgent_v2.src.core.api_client import APIClient

        self.config = config or AgentConfig()

        self._registry = SkillRegistry(self.config.skills_root)
        self._registry.scan()

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
        Create analysis plan based on context.

        Args:
            existing_analysis: Types of existing analysis in data.
            user_config: User-specified configuration.

        Returns:
            List of step dicts.
        """
        self._plan = self._planner.create_plan(
            background=self._background,
            research=self._research,
            existing_analysis=existing_analysis,
            user_config=user_config,
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
                self.execute_step(step)

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

        for step in self._plan:
            if step.get("status") == "skipped":
                continue

            step_result = self.execute_step(step)

            if step_result.observation.get("success"):
                results["steps_completed"] += 1
            else:
                results["steps_failed"] += 1

                if results["steps_failed"] >= self.config.max_retries:
                    results["status"] = "stopped"
                    results["error"] = "Too many failures, stopping"
                    break

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

        lines.append(f"# 单细胞转录组分析报告\n")
        lines.append(f"**项目**: {self.config.project_name}\n")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        lines.append("\n## 数据概况\n")
        if self._adata is not None:
            lines.append(f"| 指标 | 值 |")
            lines.append(f"|------|-----|")
            lines.append(f"| 细胞数 | {self._adata.n_obs:,} |")
            lines.append(f"| 基因数 | {self._adata.n_vars:,} |")

            if "leiden" in self._adata.obs:
                n_clusters = self._adata.obs["leiden"].nunique()
                lines.append(f"| 聚类数 | {n_clusters} |")

        lines.append("\n## 分析步骤详情\n")
        lines.append("| 步骤 | 状态 | Skill | 参数 |")
        lines.append("|------|------|-------|------|")
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
