#!/usr/bin/env python3
"""
MultimodalFeedback - Analyzes generated figures and provides visual feedback.

Uses vision model to analyze UMAP, clustering, and other visualization plots
to provide qualitative assessment of analysis results.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MultimodalFeedback:
    """
    Provides multimodal feedback by analyzing generated figures.

    Can analyze:
    - UMAP plots for cluster separation quality
    - Clustering results for cell population clarity
    - Quality control plots
    """

    def __init__(self, api_client: Any | None = None) -> None:
        """
        Initialize multimodal feedback analyzer.

        Args:
            api_client: Optional API client for vision model calls.
        """
        self._api_client = api_client
        self._vision_available = api_client is not None

    def analyze_figure(
        self,
        figure_path: str | Path,
        analysis_type: str = "general",
    ) -> dict[str, Any]:
        """
        Analyze a figure and provide feedback.

        Args:
            figure_path: Path to the figure file.
            analysis_type: Type of analysis ('umap', 'clustering', 'qc', etc.).

        Returns:
            Dict with analysis results and feedback.
        """
        figure_path = Path(figure_path)

        if not figure_path.exists():
            return {
                "success": False,
                "error": f"Figure not found: {figure_path}",
                "feedback": None,
            }

        result = {
            "success": True,
            "figure_path": str(figure_path),
            "analysis_type": analysis_type,
            "feedback": None,
            "quality_score": None,
        }

        if self._vision_available:
            try:
                feedback = self._call_vision_model(figure_path, analysis_type)
                result["feedback"] = feedback
            except Exception as e:
                logger.warning(f"Vision analysis failed: {e}")
                result["feedback"] = self._rule_based_analysis(figure_path, analysis_type)
        else:
            result["feedback"] = self._rule_based_analysis(figure_path, analysis_type)

        return result

    def _call_vision_model(
        self,
        figure_path: Path,
        analysis_type: str,
    ) -> str:
        """Call vision model to analyze figure."""
        if not self._api_client:
            return "Vision model not available"

        prompt = self._get_analysis_prompt(analysis_type)

        try:
            response = self._api_client.analyze_image(
                image_path=str(figure_path),
                prompt=prompt,
            )
            return response
        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            return f"Could not analyze image: {e}"

    def _get_analysis_prompt(self, analysis_type: str) -> str:
        """Get the appropriate prompt for the analysis type."""
        prompts = {
            "umap": """Analyze this single-cell UMAP visualization. Assess:
1. Cluster separation quality (are distinct clusters well-separated?)
2. Cluster density and size uniformity
3. Presence of outliers or dispersed cells
4. Overall structure (continuous trajectory vs discrete clusters)
Provide a brief qualitative assessment (1-2 sentences).""",
            "clustering": """Analyze this cell clustering visualization. Assess:
1. Are clusters visually distinct?
2. Is there overlap between clusters?
3. Are cluster sizes balanced?
4. Any apparent batch effects or confounders?
Provide a brief qualitative assessment (1-2 sentences).""",
            "qc": """Analyze this quality control plot. Assess:
1. Cell quality distribution
2. Any obvious quality issues
3. Mitochondrial or other contamination patterns
Provide a brief qualitative assessment (1-2 sentences).""",
            "general": """Describe this single-cell analysis figure. What does it show and what are the key observations?""",
        }
        return prompts.get(analysis_type, prompts["general"])

    def _rule_based_analysis(
        self,
        figure_path: Path,
        analysis_type: str,
    ) -> str:
        """Perform rule-based analysis when vision model is unavailable."""
        try:
            import matplotlib.image as mpimg
            img = mpimg.imread(figure_path)
            height, width = img.shape[:2]

            feedback_parts = []

            if analysis_type in ("umap", "clustering"):
                feedback_parts.append(f"Image resolution: {width}x{height}")
                feedback_parts.append("Visual assessment not available without vision model")
                feedback_parts.append(f"Figure saved at: {figure_path}")

            return " | ".join(feedback_parts)

        except Exception as e:
            logger.warning(f"Rule-based analysis failed: {e}")
            return f"Could not analyze figure: {e}"

    def batch_analyze_figures(
        self,
        figure_dir: str | Path,
        pattern: str = "*.png",
    ) -> dict[str, dict[str, Any]]:
        """
        Analyze all figures in a directory matching a pattern.

        Args:
            figure_dir: Directory containing figures.
            pattern: Glob pattern for figure files.

        Returns:
            Dict mapping figure names to analysis results.
        """
        figure_dir = Path(figure_dir)

        if not figure_dir.exists():
            return {}

        results = {}

        for figure_path in figure_dir.glob(pattern):
            analysis_type = self._infer_analysis_type(figure_path.name)
            results[figure_path.name] = self.analyze_figure(figure_path, analysis_type)

        return results

    def _infer_analysis_type(self, filename: str) -> str:
        """Infer analysis type from filename."""
        filename_lower = filename.lower()

        if "umap" in filename_lower:
            return "umap"
        elif "leiden" in filename_lower or "cluster" in filename_lower:
            return "clustering"
        elif "qc" in filename_lower or "quality" in filename_lower:
            return "qc"
        else:
            return "general"
