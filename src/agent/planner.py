#!/usr/bin/env python3
"""
Analysis Planner - LLM-driven planning for CellForge Agent.

Provides:
- LLMPlanner: Creates plans via LLM, handles failures with retries
- AnalysisPlanner: Fallback fixed-plan planner for when LLM fails

The LLMPlanner:
1. Creates initial plan via LLM using skill registry manifest
2. Supports step-by-step ReAct execution
3. Handles failure with parameter adjustment (max 3 retries)
4. Falls back to fixed plan on LLM failure
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class LLMPlanner:
    """
    LLM-driven planner that:
    1. Creates initial plan via LLM
    2. Supports ReAct loop for step-by-step execution
    3. Handles failure with parameter adjustment (max 3 retries)
    4. Falls back to fixed plan on LLM failure
    """

    SYSTEM_PROMPT = """# Role: CellForge Agent Task Planning Expert

## 1. Core Task
Transform user requirements into executable Skill calls for single-cell RNA-seq analysis.

## 2. Decision Inputs
- **User Background**: Experimental design, sequencing tech (10x, Smart-seq), species, objectives
- **Skill Registry**: Available Skills with descriptions
- **Runtime Context**: Metrics from executed steps, Critic feedback

## 3. Planning Principles
- **Biological Rigor**: QC -> Norm -> DimRed -> Clust -> Annotation (standard pipeline)
- **Tool Selection**: Prefer specialized tools from the registry
- **Parameter Pre-selection**: 
  - 10x data: QC thresholds within standard ranges
  - Large datasets (>50k cells): Consider computational efficiency
- **Visualization**: Enable `make_plot=True` at key milestones (QC, clustering, DEG)

## 4. Output Format (JSON Array)
Each step must include:
- `step_id`: Step number
- `skill_id`: Skill name from the registry
- `reasoning`: Why this Skill was chosen
- `initial_params`: Pre-configured parameters based on background
- `expected_outcome`: Biological metrics for Executor/Critic verification

## 5. Dynamic Re-planning
On failure:
- Consult `parameter_science_guide` from Skill spec
- Apply causal reasoning (not blindly repeat)
- Backtrack if tuning cannot solve the issue

## 6. Important Constraints
- Only use skills that exist in the registry
- Ensure proper pipeline order: QC before Norm, Norm before HVG, etc.
- Set `make_plot=True` for QC, clustering, and DEG steps"""

    def __init__(self, api_client: Any, registry: Any, max_retries: int = 3) -> None:
        """
        Initialize LLM planner.

        Args:
            api_client: APIClient instance for LLM calls
            registry: SkillRegistry instance for tool manifest
            max_retries: Maximum retry attempts for failed steps
        """
        self._api_client = api_client
        self._registry = registry
        self.max_retries = max_retries

    def create_initial_plan(
        self,
        background: str,
        research: str,
        data_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate complete plan via LLM.

        Args:
            background: User background description
            research: Research question/goals
            data_state: Current data state (n_cells, n_genes, existing analysis)

        Returns:
            List of step dicts with step_id, skill_id, reasoning, initial_params, expected_outcome
        """
        manifest = self._registry.get_tool_manifest()
        data_state = data_state or {}

        user_prompt = self._build_user_prompt(background, research, data_state, manifest)

        response = self._api_client.generate_text(
            prompt=user_prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.3,
        )

        try:
            if not response or response == "API key not configured":
                logger.warning("LLM response empty or API not configured, using fallback")
                return self._fallback_fixed_plan()

            plan = self._parse_json_response(response)
            if plan is None:
                logger.warning("Could not parse LLM response as JSON, using fallback")
                return self._fallback_fixed_plan()

            validated_plan = self._validate_and_enrich_plan(plan)

            if validated_plan:
                logger.info("LLM generated plan with %d steps", len(validated_plan))
                return validated_plan
            else:
                logger.warning("LLM plan validation failed, using fallback")
                return self._fallback_fixed_plan()

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse LLM response: %s, using fallback", e)
            return self._fallback_fixed_plan()

    def _parse_json_response(self, response: str) -> list | None:
        """Parse JSON from LLM response, handling common issues."""
        if not response:
            return None

        response = response.strip()

        json_start = response.find('[')
        json_end = response.rfind(']')

        if json_start == -1 or json_end == -1 or json_end < json_start:
            logger.warning("No JSON array found in response")
            return None

        json_str = response[json_start:json_end + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("Initial JSON parse failed: %s, attempting repair", e)

        try:
            repaired = self._repair_json(json_str)
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None

    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair malformed JSON."""
        repaired = json_str

        lines = repaired.split('\n')
        repaired_lines = []
        for line in lines:
            stripped = line.rstrip()
            if stripped.endswith(',') or stripped.endswith(';'):
                repaired_lines.append(stripped[:-1])
            else:
                repaired_lines.append(stripped)

        repaired = '\n'.join(repaired_lines)

        if repaired.startswith('[') and not repaired.endswith(']'):
            repaired = repaired + ']'

        return repaired

    def _build_user_prompt(
        self,
        background: str,
        research: str,
        data_state: dict[str, Any],
        manifest: list[dict[str, str]],
    ) -> str:
        """Build user prompt for planning."""
        skills_text = "\n".join(
            f"- {s['id']}: {s['purpose']}" for s in manifest
        )

        obs_columns = data_state.get('obs_columns', [])
        obs_cols_str = ", ".join(obs_columns) if obs_columns else "None"
        data_info = f"""- n_cells: {data_state.get('n_cells', 'unknown')}
- n_genes: {data_state.get('n_genes', 'unknown')}
- existing_analysis: {data_state.get('existing_types', [])}
- obs_columns (available metadata): {obs_cols_str}"""

        prompt = f"""# Planning Request

## User Background
{background or 'Not provided'}

## Research Goal
{research or 'Not provided'}

## Current Data State
{data_info}

## Available Skills
{skills_text}

# Task
Generate a JSON analysis plan as an array of steps. Each step must have:
- step_id (integer)
- name (string, human-readable step name like "QC Filtering")
- skill_id (must be from the Available Skills list above)
- reasoning (string explaining why this skill, max 50 chars)
- initial_params (object with parameters, include make_plot=True for QC/clustering/DEG)
- expected_outcome (string with biological metrics for verification, max 50 chars)

CRITICAL PIPELINE ORDER: You MUST follow this exact order:
1. QC (scanpy_qc)
2. Normalization (scanpy_normalize)
3. HVG Selection (scanpy_hvg)
4. Scaling (scanpy_scale)
5. PCA (scanpy_pca)
6. Neighbors (scanpy_neighbors) - if clustering needed
7. Clustering (scanpy_leiden) - if cell types needed
8. UMAP (scanpy_umap) - for visualization
9. DEG Analysis (scanpy_rank_genes) - if marker genes needed

CRITICAL - Parameter Selection:
- For DEG groupby: Use existing columns from obs_columns. If user has cluster labels (e.g., "cluster", "cell_type"), use that instead of "leiden"
- For method: Use "wilcoxon" if user mentions non-parametric or robust to outliers
- Use columns that EXIST in the data - check obs_columns above

IMPORTANT: 
- Do NOT skip steps in the pipeline order above
- Do NOT include batch correction unless user explicitly mentions batch effects
- "IFNB stimulation" is a treatment condition, NOT a batch factor
- Keep reasoning and expected_outcome under 50 characters each
- Output ALL steps in the pipeline (typically 7-9 steps)

Example format:
[
  {{"step_id": 1, "name": "QC Filtering", "skill_id": "scanpy_qc", "reasoning": "Filter low-quality cells", "initial_params": {{"min_genes": 200, "make_plot": true}}, "expected_outcome": "cell_removal_rate < 30%"}}
]

Respond ONLY with valid JSON array, no other text. Start with step 1."""
        return prompt

    def _validate_and_enrich_plan(self, plan: Any) -> list[dict[str, Any]] | None:
        """Validate and enrich LLM-generated plan."""
        if not isinstance(plan, list):
            logger.warning("Plan is not a list: %s", type(plan))
            return None

        validated = []
        for i, step in enumerate(plan):
            if not isinstance(step, dict):
                logger.warning("Step %d is not a dict: %s", i, type(step))
                continue

            skill_id = step.get("skill_id", "")
            step_id = step.get("step_id", i + 1)
            name = step.get("name") or skill_id.replace("_", " ").title() or f"Step {step_id}"

            validated_step = {
                "step_id": step_id,
                "name": name,
                "skill_id": skill_id,
                "reasoning": step.get("reasoning", ""),
                "initial_params": step.get("initial_params", {}),
                "expected_outcome": step.get("expected_outcome", ""),
            }

            if not validated_step["skill_id"]:
                logger.warning("Step %d missing skill_id, skipping", i)
                continue

            validated.append(validated_step)

        if not validated:
            return None

        return sorted(validated, key=lambda x: x["step_id"])

    def _fallback_fixed_plan(self) -> list[dict[str, Any]]:
        """Generate fixed fallback plan when LLM fails."""
        return [
            {
                "step_id": 1,
                "name": "QC Filtering",
                "skill_id": "scanpy_qc",
                "reasoning": "Filter low-quality cells",
                "initial_params": {"min_genes": 200, "min_cells": 3, "max_mito_pct": 20.0, "make_plot": True},
                "expected_outcome": "cell_removal_rate < 30%",
            },
            {
                "step_id": 2,
                "name": "Normalization",
                "skill_id": "scanpy_normalize",
                "reasoning": "Normalize for comparability",
                "initial_params": {"target_sum": 10000, "make_plot": False},
                "expected_outcome": "total_counts normalized",
            },
            {
                "step_id": 3,
                "name": "HVG Selection",
                "skill_id": "scanpy_hvg",
                "reasoning": "Select variable genes",
                "initial_params": {"n_top_genes": 2000, "make_plot": False},
                "expected_outcome": "2000 HVGs selected",
            },
            {
                "step_id": 4,
                "name": "Scaling",
                "skill_id": "scanpy_scale",
                "reasoning": "Scale to prevent dominance",
                "initial_params": {"max_value": 10, "make_plot": False},
                "expected_outcome": "Data scaled",
            },
            {
                "step_id": 5,
                "name": "PCA",
                "skill_id": "scanpy_pca",
                "reasoning": "Reduce dimensionality",
                "initial_params": {"n_comps": 50, "make_plot": True},
                "expected_outcome": "X_pca in adata.obsm",
            },
            {
                "step_id": 6,
                "name": "Neighbors",
                "skill_id": "scanpy_neighbors",
                "reasoning": "Build neighbor graph",
                "initial_params": {"n_neighbors": 15, "make_plot": False},
                "expected_outcome": "neighbors graph built",
            },
            {
                "step_id": 7,
                "name": "Leiden Clustering",
                "skill_id": "scanpy_leiden",
                "reasoning": "Cluster cells",
                "initial_params": {"resolution": 0.5, "make_plot": True},
                "expected_outcome": "leiden in adata.obs",
            },
            {
                "step_id": 8,
                "name": "UMAP",
                "skill_id": "scanpy_umap",
                "reasoning": "2D visualization",
                "initial_params": {"min_dist": 0.5, "make_plot": True},
                "expected_outcome": "X_umap in adata.obsm",
            },
            {
                "step_id": 9,
                "name": "DEG Analysis",
                "skill_id": "scanpy_rank_genes",
                "reasoning": "Find marker genes",
                "initial_params": {"groupby": "leiden", "method": "t-test", "make_plot": True},
                "expected_outcome": "marker genes identified",
            },
        ]

    def plan_next_step(
        self,
        current_plan: list[dict[str, Any]],
        executed_step_ids: list[int],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        For ReAct loop: return next step to execute.

        Args:
            current_plan: Full plan list
            executed_step_ids: List of already executed step IDs
            context: Current execution context

        Returns:
            Next step dict or None if plan complete
        """
        for step in current_plan:
            if step["step_id"] not in executed_step_ids:
                return step
        return None

    def adjust_on_failure(
        self,
        failed_step: dict[str, Any],
        error: str,
        skill_spec: dict[str, Any],
        attempt: int,
    ) -> dict[str, Any] | None:
        """
        Adjust parameters based on failure and parameter_science_guide.

        Args:
            failed_step: The step that failed
            error: Error message
            skill_spec: Full skill specification
            attempt: Current attempt number (0-indexed)

        Returns:
            Adjusted step dict, or None if should backtrack
        """
        if attempt >= self.max_retries - 1:
            logger.warning("Max retries reached for step %d, will backtrack", failed_step["step_id"])
            return None

        guide = skill_spec.get("parameter_science_guide", {})
        error_lower = error.lower()

        current_params = failed_step.get("initial_params", {}).copy()

        if "removal rate" in error_lower and ("high" in error_lower or "too" in error_lower):
            adjusted = self._adjust_by_guide(guide, current_params, "removal_high")
            if adjusted:
                return {**failed_step, "initial_params": adjusted, "reasoning": f"Adjusted due to high removal rate"}

        if "too few" in error_lower or "too many" in error_lower:
            if "pca" in error_lower or "n_comps" in str(failed_step):
                current_params["n_comps"] = max(10, current_params.get("n_comps", 50) - 10)
                return {**failed_step, "initial_params": current_params, "reasoning": "Adjusted PCA components"}

        if "resolution" in error_lower:
            if "cluster" in str(failed_step.get("skill_id", "")):
                current_params["resolution"] = max(0.1, current_params.get("resolution", 0.5) - 0.1)
                return {**failed_step, "initial_params": current_params, "reasoning": "Adjusted clustering resolution"}

        for param_name, guides in guide.items():
            if not isinstance(guides, dict):
                continue
            for condition_key, adjustment in guides.items():
                if not isinstance(adjustment, dict):
                    continue
                if "too_strict" in condition_key or "high" in condition_key:
                    parsed = self._parse_adjustment(adjustment.get("adjust", ""), current_params)
                    if parsed:
                        current_params.update(parsed)
                        return {
                            **failed_step,
                            "initial_params": current_params,
                            "reasoning": f"Adjusted: {adjustment.get('causal_chain', '')}",
                        }

        logger.warning("Could not find adjustment for error: %s", error)
        return None

    def _adjust_by_guide(
        self, guide: dict, current_params: dict, issue_type: str
    ) -> dict | None:
        """Find and apply adjustment from guide based on issue type."""
        for param_name, guides in guide.items():
            if not isinstance(guides, dict):
                continue
            for condition_key, adjustment in guides.items():
                if not isinstance(adjustment, dict):
                    continue
                if issue_type in condition_key.lower():
                    parsed = self._parse_adjustment(adjustment.get("adjust", ""), current_params)
                    if parsed:
                        return parsed
        return None

    def _parse_adjustment(self, adjustment_str: str, current_params: dict) -> dict | None:
        """Parse adjustment string like 'reduce min_genes by 50-100' into parameter changes."""
        if not adjustment_str:
            return None

        adjustment_str = adjustment_str.lower()

        patterns = [
            (r"reduce\s+(\w+)\s+by\s+(\d+)-(\d+)", "reduce"),
            (r"increase\s+(\w+)\s+by\s+(\d+)-(\d+)", "increase"),
            (r"set\s+(\w+)\s+to\s+(\d+)", "set"),
        ]

        for pattern, action in patterns:
            match = re.search(pattern, adjustment_str)
            if match:
                param_name = match.group(1)
                if action in ("reduce", "increase"):
                    low, high = int(match.group(2)), int(match.group(3))
                    delta = (low + high) // 2
                    current_val = current_params.get(param_name, 0)
                    if action == "reduce":
                        new_val = max(0, current_val - delta)
                    else:
                        new_val = current_val + delta
                    return {param_name: new_val}
                elif action == "set":
                    return {param_name: int(match.group(2))}

        return None


class AnalysisPlanner:
    """
    Fixed-plan planner for when LLM is unavailable.

    Standard Pipeline Steps:
    1. QC (scanpy_qc)
    2. Normalization (scanpy_normalize)
    3. HVG Selection (scanpy_hvg)
    4. Scaling (scanpy_scale)
    5. PCA (scanpy_pca)
    6. [Optional] Batch Correction (harmony_batch)
    7. Neighbors (scanpy_neighbors)
    8. Clustering (scanpy_leiden)
    9. UMAP (scanpy_umap)
    10. Cell Annotation (celltypist_annotate)
    11. DEG Analysis (scanpy_rank_genes)
    """

    SKILL_MAPPING = {
        "QC": "scanpy_qc",
        "filter_cells": "scanpy_qc",
        "filter_genes": "scanpy_qc",
        "normalization": "scanpy_normalize",
        "normalize_total": "scanpy_normalize",
        "log1p": "scanpy_normalize",
        "HVG_selection": "scanpy_hvg",
        "highly_variable_genes": "scanpy_hvg",
        "scaling": "scanpy_scale",
        "scale": "scanpy_scale",
        "PCA": "scanpy_pca",
        "pca": "scanpy_pca",
        "batch_correction": "harmony_batch",
        "neighbors": "scanpy_neighbors",
        "clustering": "scanpy_leiden",
        "leiden": "scanpy_leiden",
        "louvain": "scanpy_leiden",
        "UMAP": "scanpy_umap",
        "umap": "scanpy_umap",
        "cell_annotation": "celltypist_annotate",
        "DEG_analysis": "scanpy_rank_genes",
        "rank_genes_groups": "scanpy_rank_genes",
        "trajectory_analysis": None,
    }

    def __init__(self) -> None:
        """Initialize planner with default parameters."""
        self._default_params = {
            "QC": {"min_genes": 200, "min_cells": 3, "make_plot": True},
            "normalization": {"target_sum": 1e4, "make_plot": False},
            "HVG_selection": {"n_top_genes": 2000, "make_plot": False},
            "scaling": {"max_value": 10, "make_plot": False},
            "PCA": {"n_comps": 50, "make_plot": True},
            "batch_correction": {"key": "batch", "make_plot": False},
            "neighbors": {"n_neighbors": 15, "make_plot": False},
            "clustering": {"resolution": 0.5, "make_plot": True},
            "UMAP": {"min_dist": 0.5, "make_plot": True},
        }

    def create_plan(
        self,
        background: str = "",
        research: str = "",
        existing_analysis: dict[str, Any] | None = None,
        user_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Create analysis plan based on background and research goals.

        Args:
            background: Background description (species, tissue, disease).
            research: Research question or goals.
            existing_analysis: Dict with types of existing analysis in data.
            user_config: User-specified configuration overrides.

        Returns:
            List of step dicts.
        """
        existing = existing_analysis or {}
        existing_types = existing.get("types", [])
        user_cfg = user_config or {}

        plan = []
        step_id = 1

        has_existing_pca = any("PCA" in t for t in existing_types)
        has_existing_clustering = any("clustering" in t.lower() or "Clustering" in t for t in existing_types)

        if not has_existing_pca:
            for step in self._create_preprocessing_steps(user_cfg):
                step["step_id"] = step_id
                plan.append(step)
                step_id += 1

            if self._should_include_batch_correction(background, research, existing):
                step = self._create_batch_correction_step(user_cfg)
                step["step_id"] = step_id
                plan.append(step)
                step_id += 1

            for step in self._create_dimension_reduction_steps(user_cfg):
                step["step_id"] = step_id
                plan.append(step)
                step_id += 1
        else:
            logger.info("Skipping preprocessing - PCA already exists")
            if not has_existing_clustering:
                for step in self._create_clustering_steps(user_cfg):
                    step["step_id"] = step_id
                    plan.append(step)
                    step_id += 1

        for step in self._create_annotation_steps(user_cfg):
            step["step_id"] = step_id
            plan.append(step)
            step_id += 1

        for step in self._create_deg_steps(user_cfg):
            step["step_id"] = step_id
            plan.append(step)
            step_id += 1

        if self._should_include_trajectory(research):
            step = self._create_trajectory_steps(user_cfg)
            step["step_id"] = step_id
            plan.append(step)

        return plan

    def _create_preprocessing_steps(self, user_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Create preprocessing steps: QC, normalization, HVG, scaling."""
        return [
            {
                "skill_id": "scanpy_qc",
                "reasoning": "Filter low-quality cells",
                "initial_params": user_config.get("qc", self._default_params["QC"]),
                "expected_outcome": "cell_removal_rate < 30%",
            },
            {
                "skill_id": "scanpy_normalize",
                "reasoning": "Normalize expression values",
                "initial_params": user_config.get("normalization", self._default_params["normalization"]),
                "expected_outcome": "total_counts normalized",
            },
            {
                "skill_id": "scanpy_hvg",
                "reasoning": "Select highly variable genes",
                "initial_params": user_config.get("hvg", self._default_params["HVG_selection"]),
                "expected_outcome": "HVGs selected",
            },
            {
                "skill_id": "scanpy_scale",
                "reasoning": "Scale expression values",
                "initial_params": user_config.get("scale", self._default_params["scaling"]),
                "expected_outcome": "Data scaled",
            },
        ]

    def _create_batch_correction_step(self, user_config: dict[str, Any]) -> dict[str, Any]:
        """Create batch correction step if needed."""
        return {
            "skill_id": "harmony_batch",
            "reasoning": "Correct batch effects",
            "initial_params": user_config.get("batch_correction", self._default_params["batch_correction"]),
            "expected_outcome": "Batch effects corrected",
        }

    def _create_dimension_reduction_steps(self, user_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Create dimension reduction steps: PCA, neighbors, clustering, UMAP."""
        return [
            {
                "skill_id": "scanpy_pca",
                "reasoning": "Principal component analysis",
                "initial_params": user_config.get("pca", self._default_params["PCA"]),
                "expected_outcome": "X_pca in adata.obsm",
            },
            {
                "skill_id": "scanpy_neighbors",
                "reasoning": "Compute neighbor graph",
                "initial_params": user_config.get("neighbors", self._default_params["neighbors"]),
                "expected_outcome": "neighbors graph built",
            },
            {
                "skill_id": "scanpy_leiden",
                "reasoning": "Cluster cells using Leiden algorithm",
                "initial_params": user_config.get("clustering", self._default_params["clustering"]),
                "expected_outcome": "leiden clusters in adata.obs",
            },
            {
                "skill_id": "scanpy_umap",
                "reasoning": "UMAP dimensionality reduction",
                "initial_params": user_config.get("umap", self._default_params["UMAP"]),
                "expected_outcome": "X_umap in adata.obsm",
            },
        ]

    def _create_clustering_steps(self, user_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Create clustering-related steps when PCA exists."""
        return [
            {
                "skill_id": "scanpy_neighbors",
                "reasoning": "Compute neighbor graph",
                "initial_params": user_config.get("neighbors", self._default_params["neighbors"]),
                "expected_outcome": "neighbors graph built",
            },
            {
                "skill_id": "scanpy_leiden",
                "reasoning": "Cluster cells using Leiden algorithm",
                "initial_params": user_config.get("clustering", self._default_params["clustering"]),
                "expected_outcome": "leiden clusters in adata.obs",
            },
            {
                "skill_id": "scanpy_umap",
                "reasoning": "UMAP dimensionality reduction",
                "initial_params": user_config.get("umap", self._default_params["UMAP"]),
                "expected_outcome": "X_umap in adata.obsm",
            },
        ]

    def _create_annotation_steps(self, user_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Create cell annotation steps."""
        return [
            {
                "skill_id": "celltypist_annotate",
                "reasoning": "Annotate cell types using markers",
                "initial_params": {},
                "expected_outcome": "cell types predicted",
            }
        ]

    def _create_deg_steps(self, user_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Create differential expression analysis steps."""
        return [
            {
                "skill_id": "scanpy_rank_genes",
                "reasoning": "Find differentially expressed genes",
                "initial_params": {"method": "t-test", "make_plot": True},
                "expected_outcome": "marker genes identified",
            }
        ]

    def _create_trajectory_steps(self, user_config: dict[str, Any]) -> dict[str, Any]:
        """Create trajectory analysis steps."""
        return {
            "skill_id": "scanpy_trajectory",
            "reasoning": "Infer developmental trajectories",
            "initial_params": {},
            "expected_outcome": "trajectory inferred",
        }

    def _should_include_batch_correction(self, background: str, research: str, existing: dict[str, Any]) -> bool:
        """Determine if batch correction should be included."""
        background_lower = background.lower()
        research_lower = research.lower()
        batch_indicators = ["batch", "multiple", "different donors", "samples", "patient", "treatment", "control"]
        for indicator in batch_indicators:
            if indicator in background_lower or indicator in research_lower:
                return True
        return False

    def _should_include_trajectory(self, research: str) -> bool:
        """Determine if trajectory analysis should be included."""
        research_lower = research.lower()
        trajectory_keywords = ["trajectory", "pseudotime", "development", "differentiation"]
        for keyword in trajectory_keywords:
            if keyword in research_lower:
                return True
        return False

    def get_step_purpose(self, step_name: str) -> str:
        """Get the purpose description of a step."""
        purposes = {
            "QC": "Assess data quality, identify low-quality cells and outlier genes",
            "normalization": "Remove sequencing depth differences, enable cell-to-cell comparison",
            "HVG_selection": "Select highly variable genes, reduce noise",
            "scaling": "Standardize data range, prevent high-expression genes from dominating",
            "PCA": "Dimensionality reduction and denoising, find major sources of variation",
            "batch_correction": "Remove batch effects, integrate data from different sources",
            "neighbors": "Build cell neighbor graph, discover local structure",
            "clustering": "Group similar cells, identify cell types",
            "UMAP": "2D visualization, display cell population structure",
            "cell_annotation": "Identify cell types for each cluster",
            "DEG_analysis": "Find differentially expressed genes between cell types",
            "trajectory_analysis": "Infer cell developmental trajectories and pseudotime",
        }
        return purposes.get(step_name, "Execute analysis step")