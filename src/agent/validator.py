#!/usr/bin/env python3
"""
Result Validator - Validates analysis results (numeric and visual).

Provides:
- NumericValidator: Cell/gene counts, PCA dimensions, clustering quality
- VisualValidator: Plot quality checking via vision API
- ResultValidator: Combined validation for complete steps
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class NumericValidator:
    """
    Validate numeric aspects of analysis results.

    Checks:
    - Cell count (reasonable range)
    - Gene count (reasonable range)
    - Mitochondrial percentage
    - PCA dimensions
    - Clustering quality
    """

    def __init__(
        self,
        min_cells: int = 100,
        max_cells: int = 5000000,
        min_genes: int = 50,
        max_genes: int = 60000,
        max_mito_pct: float = 25.0,
    ) -> None:
        """
        Initialize validator with thresholds.

        Args:
            min_cells: Minimum acceptable cell count.
            max_cells: Maximum acceptable cell count.
            min_genes: Minimum acceptable gene count.
            max_genes: Maximum acceptable gene count.
            max_mito_pct: Maximum mitochondrial percentage.
        """
        self.min_cells = min_cells
        self.max_cells = max_cells
        self.min_genes = min_genes
        self.max_genes = max_genes
        self.max_mito_pct = max_mito_pct

    def validate(self, adata: Any, step_name: str) -> ValidationResult:
        """
        Validate AnnData after a step.

        Args:
            adata: AnnData object to validate.
            step_name: Name of the analysis step.

        Returns:
            ValidationResult with issues and suggestions.
        """
        issues = []
        suggestions = []

        n_cells = adata.n_obs if adata else 0
        n_genes = adata.n_vars if adata else 0

        if n_cells < self.min_cells:
            issues.append(f"Too few cells: {n_cells} < {self.min_cells}")
        if n_cells > self.max_cells:
            issues.append(f"Too many cells: {n_cells} > {self.max_cells}")

        if n_genes < self.min_genes:
            issues.append(f"Too few genes: {n_genes} < {self.min_genes}")
        if n_genes > self.max_genes:
            issues.append(f"Too many genes: {n_genes} > {self.max_genes}")

        if hasattr(adata, "obs"):
            if "total_counts" in adata.obs:
                total_counts = adata.obs["total_counts"]
                if total_counts.max() > 100000:
                    suggestions.append(
                        "Abnormally high total counts detected, possible doublets"
                    )

            if "pct_counts_mito" in adata.obs:
                mito_pct = adata.obs["pct_counts_mito"]
                if mito_pct.max() > self.max_mito_pct:
                    issues.append(
                        f"Mitochondrial gene percentage too high: max {mito_pct.max():.1f}%"
                    )

        if "X_pca" in adata.obsm:
            n_pcs = adata.obsm["X_pca"].shape[1]
            if n_pcs < 5:
                suggestions.append(f"Too few PCA components: {n_pcs}")

        if "X_umap" in adata.obsm:
            umap_shape = adata.obsm["X_umap"].shape
            if umap_shape[1] != 2:
                issues.append(f"UMAP dimension error: expected 2, got {umap_shape[1]}")

        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            details={
                "n_cells": n_cells,
                "n_genes": n_genes,
                "step": step_name,
            },
        )

    def validate_clustering(
        self, adata: Any, cluster_key: str = "leiden"
    ) -> ValidationResult:
        """
        Validate clustering results.

        Args:
            adata: AnnData object with clustering results.
            cluster_key: Key in obs containing cluster labels.

        Returns:
            ValidationResult with clustering quality metrics.
        """
        issues = []
        suggestions = []

        if cluster_key not in adata.obs:
            issues.append(f"Clustering results not found: {cluster_key}")
            return ValidationResult(
                valid=False, issues=issues, suggestions=[], details={}
            )

        n_clusters = adata.obs[cluster_key].nunique()
        n_cells = adata.n_obs

        if n_clusters < 2:
            issues.append("Only 1 cluster detected, clustering may have failed")
        if n_clusters > n_cells / 2:
            issues.append(f"Too many clusters ({n_clusters}), possible over-clustering")
        if n_clusters > 100:
            suggestions.append("Large number of clusters (>100), consider checking parameters")

        cluster_sizes = adata.obs[cluster_key].value_counts()
        if (cluster_sizes < 5).sum() > n_clusters / 2:
            suggestions.append(
                "Many small clusters (cells<5), consider filtering outlier cells"
            )

        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            details={
                "n_clusters": n_clusters,
                "cluster_sizes": cluster_sizes.to_dict(),
            },
        )

    def validate_degs(
        self, adata: Any, key: str = "rank_genes_groups"
    ) -> ValidationResult:
        """
        Validate differential expression results.

        Args:
            adata: AnnData object with DEG results.
            key: Key in uns containing DEG results.

        Returns:
            ValidationResult with DEG quality metrics.
        """
        issues = []
        suggestions = []

        if key not in adata.uns:
            issues.append("Differential expression results not found")
            return ValidationResult(
                valid=False, issues=issues, suggestions=[], details={}
            )

        deg_result = adata.uns[key]

        if len(deg_result) == 0:
            issues.append("Differential expression results are empty")

        for group in list(deg_result.keys())[:5]:
            if "names" not in deg_result[group]:
                continue
            n_degs = len(deg_result[group]["names"])
            if n_degs == 0:
                suggestions.append(f"Group {group} has no significant DEGs")
            elif n_degs < 10:
                suggestions.append(f"Group {group} has few DEGs ({n_degs})")

        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            details={"n_groups": len(deg_result)},
        )


class VisualValidator:
    """
    Validate visual outputs using vision model.

    Uses API client to analyze plot quality.
    """

    def __init__(self, api_client: Any = None) -> None:
        """
        Initialize visual validator.

        Args:
            api_client: APIClient instance for vision analysis.
        """
        self.api_client = api_client

    def validate(
        self, image_path: str | Path, expected_content: str | None = None
    ) -> ValidationResult:
        """
        Validate image using vision model.

        Args:
            image_path: Path to image file.
            expected_content: Description of expected content.

        Returns:
            ValidationResult from vision analysis.
        """
        if not self.api_client:
            return ValidationResult(
                valid=True,
                issues=[],
                suggestions=["Vision API not configured, skipping visual validation"],
                details={},
            )

        image_path = Path(image_path)
        if not image_path.exists():
            return ValidationResult(
                valid=False,
                issues=[f"Image file not found: {image_path}"],
                suggestions=[],
                details={},
            )

        try:
            with open(image_path, "rb") as f:
                image_data = f.read()

            prompt = self._build_validation_prompt(expected_content)
            response = self.api_client.analyze_image(
                image_data=image_data, prompt=prompt
            )

            return self._parse_vision_response(response)

        except Exception as e:
            logger.exception("Visual validation failed")
            return ValidationResult(
                valid=False,
                issues=[f"Visual validation failed: {e}"],
                suggestions=["Check if the image was generated correctly"],
                details={},
            )

    def _build_validation_prompt(self, expected_content: str | None) -> str:
        """Build prompt for vision model."""
        prompt = """You are a single-cell data analysis expert. Please inspect this image:

1. Was the image generated correctly (not blank or an error image)?
2. Is the single-cell analysis plot clear and readable?
3. Are there any obvious anomalies (e.g., axis errors, label overlap, color issues)?
4. Does it meet the standards for single-cell data analysis plots?

Please provide a brief assessment: Acceptable / Needs revision, with reasoning.
"""
        if expected_content:
            prompt += f"\nExpected content: {expected_content}"

        return prompt

    def _parse_vision_response(self, response: str) -> ValidationResult:
        """Parse vision model response."""
        issues = []
        suggestions = []

        response_lower = response.lower()

        if "empty" in response_lower or "blank" in response_lower:
            issues.append("Image is blank or not generated correctly")

        if "error" in response_lower:
            issues.append("Image generation error detected")

        if "overlap" in response_lower:
            suggestions.append("Plot has label overlap issues")

        if "axis error" in response_lower or "axis problem" in response_lower:
            issues.append("Axis issues detected")

        valid = len(issues) == 0

        return ValidationResult(
            valid=valid,
            issues=issues,
            suggestions=suggestions,
            details={"raw_response": response},
        )

    def validate_umap(self, image_path: str | Path) -> ValidationResult:
        """Validate UMAP plot."""
        expected = "Single-cell UMAP plot showing clear separation of cell populations"
        return self.validate(image_path, expected)

    def validate_heatmap(self, image_path: str | Path) -> ValidationResult:
        """Validate heatmap plot."""
        expected = "Differentially expressed genes heatmap showing clear expression patterns"
        return self.validate(image_path, expected)

    def validate_dotplot(self, image_path: str | Path) -> ValidationResult:
        """Validate dotplot."""
        expected = "Gene expression dotplot showing marker genes for each cluster"
        return self.validate(image_path, expected)


class ResultValidator:
    """
    Combined validator for all results.

    Integrates numeric and visual validation.
    """

    def __init__(
        self,
        numeric_config: dict[str, Any] | None = None,
        api_client: Any = None,
    ) -> None:
        """
        Initialize combined validator.

        Args:
            numeric_config: Configuration for NumericValidator.
            api_client: APIClient instance for VisualValidator.
        """
        if numeric_config:
            self.numeric = NumericValidator(
                min_cells=numeric_config.get("min_cells", 100),
                max_cells=numeric_config.get("max_cells", 5000000),
                min_genes=numeric_config.get("min_genes", 50),
                max_genes=numeric_config.get("max_genes", 60000),
                max_mito_pct=numeric_config.get("max_mito_pct", 25.0),
            )
        else:
            self.numeric = NumericValidator()

        self.visual = VisualValidator(api_client)

    def validate_numeric(self, adata: Any, step_name: str) -> ValidationResult:
        """Validate numeric results."""
        return self.numeric.validate(adata, step_name)

    def validate_clustering(
        self, adata: Any, cluster_key: str = "leiden"
    ) -> ValidationResult:
        """Validate clustering results."""
        return self.numeric.validate_clustering(adata, cluster_key)

    def validate_degs(
        self, adata: Any, key: str = "rank_genes_groups"
    ) -> ValidationResult:
        """Validate DEG results."""
        return self.numeric.validate_degs(adata, key)

    def validate_visual(
        self, image_path: str | Path, plot_type: str | None = None
    ) -> ValidationResult:
        """
        Validate visual output.

        Args:
            image_path: Path to image.
            plot_type: Type of plot (umap/heatmap/dotplot).

        Returns:
            ValidationResult for the image.
        """
        if plot_type == "umap":
            return self.visual.validate_umap(image_path)
        elif plot_type == "heatmap":
            return self.visual.validate_heatmap(image_path)
        elif plot_type == "dotplot":
            return self.visual.validate_dotplot(image_path)
        return self.visual.validate(image_path)

    def validate_step(
        self, adata: Any, step_name: str, image_path: str | Path | None = None
    ) -> dict[str, Any]:
        """
        Validate a complete step.

        Args:
            adata: AnnData object.
            step_name: Name of the step.
            image_path: Optional path to visualization image.

        Returns:
            dict with 'valid', 'numeric_result', 'visual_result', etc.
        """
        result: dict[str, Any] = {
            "valid": True,
            "numeric_result": None,
            "visual_result": None,
            "issues": [],
            "suggestions": [],
        }

        if adata is not None:
            numeric_result = self.numeric.validate(adata, step_name)
            result["numeric_result"] = numeric_result
            if not numeric_result.valid:
                result["valid"] = False
            result["issues"].extend(numeric_result.issues)
            result["suggestions"].extend(numeric_result.suggestions)

        if image_path is not None:
            visual_result = self.visual.validate(image_path)
            result["visual_result"] = visual_result
            if not visual_result.valid:
                result["valid"] = False
            result["issues"].extend(visual_result.issues)
            result["suggestions"].extend(visual_result.suggestions)

        return result
