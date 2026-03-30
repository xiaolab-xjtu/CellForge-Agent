#!/usr/bin/env python3
"""
SkillCritic - Evaluates skill execution results and provides self-correction feedback.

Implements the Critic phase of the ReAct+Skill loop:
- Evaluates metrics against success thresholds
- Calculates clustering quality metrics (silhouette score, etc.)
- Extracts context-aware parameter adjustment suggestions
- Provides biology-informed guidance via parameter_science_guide
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agent.executor import ExecutionResult

logger = logging.getLogger(__name__)


class SkillCritic:
    """
    Critic for evaluating skill execution and providing self-correction guidance.

    Uses the critic_layer from skill specs to:
    1. Check success thresholds
    2. Generate actionable feedback for parameter adjustments
    3. Provide biology-informed guidance via parameter_science_guide
    4. Calculate comprehensive quality metrics
    """

    def __init__(self) -> None:
        """Initialize critic with metrics library."""
        self._metrics_lib = None

    def _get_metrics_lib(self):
        """Lazy load metrics library."""
        if self._metrics_lib is None:
            try:
                from src.agent.metrics import (
                    silhouette_score,
                    silhouette_score_batch,
                    mitochondrial_percentage,
                    calculate_clustering_quality,
                    calculate_batch_effect_metrics,
                )
                self._metrics_lib = {
                    "silhouette_score": silhouette_score,
                    "silhouette_score_batch": silhouette_score_batch,
                    "mt_percentage": mitochondrial_percentage,
                    "clustering_quality": calculate_clustering_quality,
                    "batch_effect_metrics": calculate_batch_effect_metrics,
                }
            except ImportError as e:
                logger.warning(f"Metrics library not available: {e}")
                self._metrics_lib = {}
        return self._metrics_lib

    def evaluate(
        self,
        execution_result: "ExecutionResult",
        context: dict[str, Any] | None = None,
        adata: Any = None,
    ) -> CriticResult:
        """
        Evaluate execution result against success criteria.

        Args:
            execution_result: Result from SkillExecutor.
            context: Context info (protocol, species, etc.)
            adata: AnnData object for computing additional metrics.

        Returns:
            CriticResult with success status and feedback.
        """
        if not execution_result.success:
            return CriticResult(
                success=False,
                feedback=f"Execution failed: {execution_result.error}",
                adjustments=[],
            )

        skill_spec = execution_result.skill_spec
        if not skill_spec:
            return CriticResult(success=True, feedback=None, adjustments=[])

        skill_id = skill_spec.get("skill_id", "")
        critic_layer = skill_spec.get("critic_layer", {})
        parameter_guide = skill_spec.get("parameter_science_guide", {})
        metrics = execution_result.metrics.copy() if execution_result.metrics else {}

        warnings = []
        adjustments = []
        computed_metrics = {}

        if skill_id == "scanpy_leiden" and adata is not None:
            quality = self._evaluate_clustering(adata, parameter_guide)
            warnings.extend(quality.get("warnings", []))
            adjustments.extend(quality.get("adjustments", []))
            computed_metrics.update(quality.get("metrics", {}))

        elif skill_id == "scanpy_qc" and adata is not None:
            qc_result = self._evaluate_qc(adata, parameter_guide)
            warnings.extend(qc_result.get("warnings", []))
            adjustments.extend(qc_result.get("adjustments", []))
            computed_metrics.update(qc_result.get("metrics", {}))

        elif skill_id == "scanpy_pca" and adata is not None:
            pca_result = self._evaluate_pca(adata, parameter_guide)
            warnings.extend(pca_result.get("warnings", []))
            adjustments.extend(pca_result.get("adjustments", []))
            computed_metrics.update(pca_result.get("metrics", {}))

        metrics.update(computed_metrics)
        success = len([w for w in warnings if "CRITICAL" in w or "UNDER" in w or "OVER" in w]) == 0

        return CriticResult(
            success=success,
            feedback="; ".join(warnings) if warnings else None,
            adjustments=adjustments,
            metrics=metrics,
        )

    def _evaluate_clustering(
        self, adata: Any, parameter_guide: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate clustering quality and suggest adjustments."""
        warnings = []
        adjustments = []
        metrics = {}

        metrics_lib = self._get_metrics_lib()
        if not metrics_lib:
            return {"warnings": warnings, "adjustments": adjustments, "metrics": metrics}

        quality_fn = metrics_lib.get("clustering_quality")
        if quality_fn and "leiden" in adata.obs:
            quality = quality_fn(adata, "leiden")
            metrics.update(quality)

            n_clusters = quality.get("n_clusters", 0)
            sil_score = quality.get("silhouette_score")

            if sil_score is not None:
                metrics["silhouette_score"] = round(sil_score, 3)
                if sil_score < 0.3:
                    warnings.append(f"LOW SILHOUETTE: Score {sil_score:.2f} indicates poor cluster separation")
                    adjustments.extend(self._get_adjustments_for_param("silhouette_low", parameter_guide))
                elif sil_score > 0.7:
                    warnings.append(f"EXCELLENT SILHOUETTE: Score {sil_score:.2f}")

            if n_clusters < 3:
                warnings.append(f"UNDER-SEGMENTATION: Only {n_clusters} clusters found")
                adjustments.extend(self._get_adjustments_for_param("too_few_clusters", parameter_guide))
            elif n_clusters > 150:
                warnings.append(f"OVER-SEGMENTATION: {n_clusters} clusters - may be over-clustering")
                adjustments.extend(self._get_adjustments_for_param("too_many_clusters", parameter_guide))

            min_size = quality.get("min_cluster_size", 0)
            if min_size < 5:
                warnings.append(f"SMALL CLUSTERS: Minimum cluster has only {min_size} cells")
                adjustments.extend(self._get_adjustments_for_param("small_clusters", parameter_guide))

        return {"warnings": warnings, "adjustments": adjustments, "metrics": metrics}

    def _evaluate_qc(
        self, adata: Any, parameter_guide: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate QC results."""
        warnings = []
        adjustments = []
        metrics = {}

        metrics_lib = self._get_metrics_lib()
        if not metrics_lib:
            return {"warnings": warnings, "adjustments": adjustments, "metrics": metrics}

        mt_fn = metrics_lib.get("mt_percentage")
        if mt_fn:
            mt_metrics = mt_fn(adata)
            metrics.update({f"mt_{k}": v for k, v in mt_metrics.items()})

            high_mt_pct = mt_metrics.get("high_mt_cells_pct", 0)
            if high_mt_pct > 30:
                warnings.append(f"HIGH MT CONTENT: {high_mt_pct:.1f}% cells have high mitochondrial percentage")
                adjustments.extend(self._get_adjustments_for_param("high_mt", parameter_guide))
            elif high_mt_pct < 5:
                warnings.append(f"LOW MT CONTENT: {high_mt_pct:.1f}% - may indicate viable cells")

        n_cells = adata.n_obs
        if n_cells < 100:
            warnings.append(f"LOW CELL COUNT: Only {n_cells} cells remain after QC")

        return {"warnings": warnings, "adjustments": adjustments, "metrics": metrics}

    def _evaluate_pca(
        self, adata: Any, parameter_guide: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate PCA results."""
        warnings = []
        adjustments = []
        metrics = {}

        if "X_pca" in adata.obsm:
            pca_shape = adata.obsm["X_pca"].shape
            metrics["pca_components"] = pca_shape[1]

            if pca_shape[1] < 10:
                warnings.append(f"LOW PCA COMPONENTS: Only {pca_shape[1]} components retained")
                adjustments.extend(self._get_adjustments_for_param("low_pca_comps", parameter_guide))

        return {"warnings": warnings, "adjustments": adjustments, "metrics": metrics}

    def _get_adjustments_for_param(
        self, issue: str, parameter_guide: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Get parameter adjustment suggestions from guide based on issue."""
        suggestions = []

        issue_mapping = {
            "too_few_clusters": ["resolution", "n_neighbors"],
            "too_many_clusters": ["resolution", "n_neighbors"],
            "small_clusters": ["resolution"],
            "silhouette_low": ["resolution", "n_neighbors", "n_pcs"],
            "high_mt": ["max_mito_pct", "min_genes"],
            "low_pca_comps": ["n_comps"],
        }

        relevant_params = issue_mapping.get(issue, [])

        for param in parameter_guide:
            if param in relevant_params:
                for issue_key, guide in parameter_guide[param].items():
                    if issue_key in issue or issue in issue_key:
                        suggestions.append({
                            "parameter": param,
                            "action": guide.get("adjust", ""),
                            "causal_chain": guide.get("causal_chain", ""),
                            "expected_effect": guide.get("expected_effect", ""),
                        })

        return suggestions

    def _get_protocol_thresholds(self, context: dict[str, Any] | None) -> dict[str, Any]:
        """Get context-aware thresholds."""
        protocol = context.get("protocol", "10x Genomics") if context else "10x Genomics"

        thresholds = {
            "10x Genomics": {"max_removal_rate": 0.5, "min_cells": 100, "min_genes": 200},
            "Smart-seq2": {"max_removal_rate": 0.3, "min_cells": 50, "min_genes": 500},
            "Drop-seq": {"max_removal_rate": 0.4, "min_cells": 100, "min_genes": 100},
            "inDrop": {"max_removal_rate": 0.45, "min_cells": 100, "min_genes": 150},
        }
        return thresholds.get(protocol, thresholds["10x Genomics"])


from dataclasses import dataclass, field


@dataclass
class CriticResult:
    """Result of critic evaluation."""
    success: bool
    feedback: str | None
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] | None = None

    def has_adjustments(self) -> bool:
        return len(self.adjustments) > 0