#!/usr/bin/env python3
"""
Analysis Planner - Creates analysis plans based on research goals and data context.

Provides:
- create_plan(): Generate standard pipeline based on background/research
- revise_plan(): Adjust plan based on validation results
- skill selection based on available skills
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AnalysisPlanner:
    """
    Planner for creating analysis plans based on research context.

    Standard Pipeline Steps:
    1. QC (filter_cells, filter_genes)
    2. Normalization (normalize_total, log1p)
    3. HVG Selection (highly_variable_genes)
    4. Scaling (scale)
    5. PCA (pca)
    6. [Optional] Batch Correction
    7. Neighbors (neighbors)
    8. Clustering (leiden)
    9. UMAP (umap)
    10. Cell Annotation
    11. DEG Analysis
    12. [Optional] Trajectory Analysis
    """

    STANDARD_STEPS = [
        "QC",
        "normalization",
        "HVG_selection",
        "scaling",
        "PCA",
        "batch_correction",
        "neighbors",
        "clustering",
        "UMAP",
        "cell_annotation",
        "DEG_analysis",
        "trajectory_analysis",
    ]

    SKILL_MAPPING = {
        "QC": "scanpy_filter_cells",
        "filter_cells": "scanpy_filter_cells",
        "filter_genes": "scanpy_filter_genes",
        "normalization": "scanpy_normalize",
        "normalize_total": "scanpy_normalize",
        "log1p": "scanpy_normalize",
        "HVG_selection": "scanpy_hvg",
        "highly_variable_genes": "scanpy_hvg",
        "scaling": "scanpy_scale",
        "scale": "scanpy_scale",
        "PCA": "scanpy_pca",
        "pca": "scanpy_pca",
        "batch_correction": "sc_batch_correction",
        "neighbors": "scanpy_neighbors",
        "neighbors": "scanpy_neighbors",
        "clustering": "scanpy_cluster",
        "leiden": "scanpy_cluster",
        "louvain": "scanpy_cluster",
        "UMAP": "scanpy_umap",
        "umap": "scanpy_umap",
        "cell_annotation": "sc_cell_annotation",
        "DEG_analysis": "scanpy_deg",
        "rank_genes_groups": "scanpy_deg",
        "trajectory_analysis": "scanpy_trajectory",
        "paga": "scanpy_trajectory",
        "dpt": "scanpy_trajectory",
    }

    def __init__(self) -> None:
        """Initialize planner."""
        self._default_params = {
            "QC": {"min_genes": 200, "min_cells": 3},
            "normalization": {"target_sum": 1e4},
            "HVG_selection": {"n_top_genes": 2000},
            "scaling": {"max_value": 10},
            "PCA": {"n_comps": 50},
            "batch_correction": {"key": "batch"},
            "neighbors": {"n_neighbors": 15},
            "clustering": {"resolution": 0.5},
            "UMAP": {"min_dist": 0.5},
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
            List of step dicts with name, skill_id, parameters, etc.
        """
        existing = existing_analysis or {}
        existing_types = existing.get("types", [])
        user_cfg = user_config or {}

        plan = []

        has_existing_pca = any("PCA" in t for t in existing_types)
        has_existing_clustering = any("聚类" in t for t in existing_types)

        if not has_existing_pca:
            plan.extend(self._create_preprocessing_steps(user_cfg))
            if self._should_include_batch_correction(background, research, existing):
                plan.extend(self._create_batch_correction_step(user_cfg))
            plan.extend(self._create_dimension_reduction_steps(user_cfg))
        else:
            logger.info("Skipping preprocessing steps - PCA already exists")

            if not has_existing_clustering:
                plan.extend(self._create_clustering_steps(user_cfg))
            else:
                logger.info("Skipping clustering steps - clustering already exists")

        plan.extend(self._create_annotation_steps(user_cfg))
        plan.extend(self._create_deg_steps(user_cfg))

        if self._should_include_trajectory(research):
            plan.extend(self._create_trajectory_steps(user_cfg))

        return plan

    def _create_preprocessing_steps(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create preprocessing steps: QC, normalization, HVG, scaling."""
        return [
            {
                "name": "QC",
                "skill_id": "scanpy_filter_cells",
                "tool": "scanpy.filter_cells",
                "parameters": user_config.get("qc", self._default_params["QC"]),
                "purpose": "Filter low-quality cells",
            },
            {
                "name": "normalization",
                "skill_id": "scanpy_normalize",
                "tool": "scanpy.normalize_total",
                "parameters": user_config.get(
                    "normalization", self._default_params["normalization"]
                ),
                "purpose": "Normalize expression values",
            },
            {
                "name": "HVG_selection",
                "skill_id": "scanpy_hvg",
                "tool": "scanpy.highly_variable_genes",
                "parameters": user_config.get(
                    "hvg", self._default_params["HVG_selection"]
                ),
                "purpose": "Select highly variable genes",
            },
            {
                "name": "scaling",
                "skill_id": "scanpy_scale",
                "tool": "scanpy.scale",
                "parameters": user_config.get("scale", self._default_params["scaling"]),
                "purpose": "Scale expression values",
            },
        ]

    def _create_batch_correction_step(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create batch correction step if needed."""
        return [
            {
                "name": "batch_correction",
                "skill_id": "sc_batch_correction",
                "tool": "harmony.integrate",
                "parameters": user_config.get(
                    "batch_correction", self._default_params["batch_correction"]
                ),
                "purpose": "Correct batch effects",
            }
        ]

    def _create_dimension_reduction_steps(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create dimension reduction steps: PCA, neighbors, clustering, UMAP."""
        return [
            {
                "name": "PCA",
                "skill_id": "scanpy_pca",
                "tool": "scanpy.pca",
                "parameters": user_config.get("pca", self._default_params["PCA"]),
                "purpose": "Principal component analysis",
            },
            {
                "name": "neighbors",
                "skill_id": "scanpy_neighbors",
                "tool": "scanpy.neighbors",
                "parameters": user_config.get(
                    "neighbors", self._default_params["neighbors"]
                ),
                "purpose": "Compute neighbor graph",
            },
            {
                "name": "clustering",
                "skill_id": "scanpy_cluster",
                "tool": "scanpy.leiden",
                "parameters": user_config.get(
                    "clustering", self._default_params["clustering"]
                ),
                "purpose": "Cluster cells using Leiden algorithm",
            },
            {
                "name": "UMAP",
                "skill_id": "scanpy_umap",
                "tool": "scanpy.umap",
                "parameters": user_config.get("umap", self._default_params["UMAP"]),
                "purpose": "UMAP dimensionality reduction",
            },
        ]

    def _create_clustering_steps(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create clustering-related steps."""
        return [
            {
                "name": "neighbors",
                "skill_id": "scanpy_neighbors",
                "tool": "scanpy.neighbors",
                "parameters": user_config.get(
                    "neighbors", self._default_params["neighbors"]
                ),
                "purpose": "Compute neighbor graph",
            },
            {
                "name": "clustering",
                "skill_id": "scanpy_cluster",
                "tool": "scanpy.leiden",
                "parameters": user_config.get(
                    "clustering", self._default_params["clustering"]
                ),
                "purpose": "Cluster cells using Leiden algorithm",
            },
            {
                "name": "UMAP",
                "skill_id": "scanpy_umap",
                "tool": "scanpy.umap",
                "parameters": user_config.get("umap", self._default_params["UMAP"]),
                "purpose": "UMAP dimensionality reduction",
            },
        ]

    def _create_annotation_steps(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create cell annotation steps."""
        return [
            {
                "name": "cell_annotation",
                "skill_id": "sc_cell_annotation",
                "tool": "cell_annotation",
                "parameters": {},
                "purpose": "Annotate cell types using markers",
            }
        ]

    def _create_deg_steps(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create differential expression analysis steps."""
        return [
            {
                "name": "DEG_analysis",
                "skill_id": "scanpy_deg",
                "tool": "scanpy.rank_genes_groups",
                "parameters": {"method": "t-test"},
                "purpose": "Find differentially expressed genes",
            }
        ]

    def _create_trajectory_steps(
        self, user_config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Create trajectory analysis steps."""
        return [
            {
                "name": "trajectory_analysis",
                "skill_id": "scanpy_trajectory",
                "tool": "scanpy.paga",
                "parameters": {},
                "purpose": "Infer developmental trajectories",
            }
        ]

    def _should_include_batch_correction(
        self, background: str, research: str, existing: dict[str, Any]
    ) -> bool:
        """
        Determine if batch correction should be included.

        Args:
            background: Background description.
            research: Research question.
            existing: Existing analysis info.

        Returns:
            True if batch correction should be included.
        """
        background_lower = background.lower()
        research_lower = research.lower()

        batch_indicators = [
            "batch",
            "multiple",
            "different",
            " donors",
            "samples",
            "patient",
            "treatment",
            "control",
        ]

        for indicator in batch_indicators:
            if indicator in background_lower or indicator in research_lower:
                return True

        return False

    def _should_include_trajectory(self, research: str) -> bool:
        """
        Determine if trajectory analysis should be included.

        Args:
            research: Research question.

        Returns:
            True if trajectory analysis should be included.
        """
        research_lower = research.lower()

        trajectory_keywords = [
            "trajectory",
            "pseudotime",
            "development",
            "differentiation",
            "发育",
            "分化",
            "轨迹",
        ]

        for keyword in trajectory_keywords:
            if keyword in research_lower:
                return True

        return False

    def revise_plan(
        self,
        plan: list[dict[str, Any]],
        validation_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Revise plan based on validation results.

        Args:
            plan: Original plan.
            validation_results: List of validation results for each step.

        Returns:
            Revised plan.
        """
        revised = []

        for i, step in enumerate(plan):
            step_copy = step.copy()

            if i < len(validation_results):
                result = validation_results[i]
                if not result.get("valid", True):
                    issues = result.get("issues", [])
                    for issue in issues:
                        if "resolution" in issue.lower():
                            if "clustering" in step_copy["name"].lower():
                                step_copy["parameters"]["resolution"] = 0.3
                        elif "too few" in issue.lower() or "too many" in issue.lower():
                            if "pca" in step_copy["name"].lower():
                                n_comps = step_copy["parameters"].get("n_comps", 50)
                                step_copy["parameters"]["n_comps"] = max(
                                    10, n_comps - 10
                                )

            revised.append(step_copy)

        return revised

    def get_step_purpose(self, step_name: str) -> str:
        """Get the purpose description of a step."""
        purposes = {
            "QC": "评估数据质量，识别低质量细胞和异常基因",
            "normalization": "消除测序深度差异，使细胞间可比较",
            "HVG_selection": "筛选变异大的基因，减少噪音",
            "scaling": "标准化数据范围，防止高表达基因主导",
            "PCA": "降维去噪，发现数据主要变异方向",
            "batch_correction": "消除批次效应，整合不同来源的数据",
            "neighbors": "构建细胞间邻居图，发现局部结构",
            "clustering": "将相似细胞分组，发现细胞类型",
            "UMAP": "二维可视化，高清展示细胞群体结构",
            "cell_annotation": "鉴定每个cluster的细胞类型",
            "DEG_analysis": "找出不同细胞类型间的差异表达基因",
            "trajectory_analysis": "推断细胞发育轨迹和伪时间",
        }
        return purposes.get(step_name, "执行分析步骤")

    def map_step_to_skill(self, step_name: str, available_skills: list[str]) -> str | None:
        """
        Map a step name to an available skill.

        Args:
            step_name: Name of the analysis step.
            available_skills: List of available skill IDs.

        Returns:
            Matching skill_id or None.
        """
        preferred = self.SKILL_MAPPING.get(step_name)
        if preferred and preferred in available_skills:
            return preferred

        for skill in available_skills:
            skill_lower = skill.lower()
            if step_name.lower().replace("_", "") in skill_lower:
                return skill
            if step_name.lower() in skill_lower:
                return skill

        return None
