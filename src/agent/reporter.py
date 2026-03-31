#!/usr/bin/env python3
"""
Reporter - Generates analysis reports and reproducible code.

Provides:
- generate_markdown_report(): Comprehensive analysis report
- generate_reproducible_code(): Exportable Python pipeline script
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Reporter:
    """
    Generates analysis reports and reproducible code.

    Outputs:
    - Markdown reports with data overview, steps, results
    - Python scripts for reproducible analysis
    """

    def __init__(
        self,
        project_name: str = "default_project",
        output_dir: str | Path = "outputs/",
    ) -> None:
        """
        Initialize reporter.

        Args:
            project_name: Name of the project.
            output_dir: Directory for output files.
        """
        self.project_name = project_name
        output_path = Path(output_dir)
        if output_path.name == project_name:
            self.output_dir = output_path
        else:
            self.output_dir = output_path / project_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        adata: Any,
        steps: list[Any],
        plan: list[dict[str, Any]] | None = None,
        background: str = "",
        research: str = "",
        deg_results: dict[str, Any] | None = None,
        trajectory_results: dict[str, Any] | None = None,
        existing_analysis: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate comprehensive markdown report.

        Args:
            adata: AnnData object with analysis results.
            steps: List of StepRecord objects.
            plan: Original analysis plan.
            background: Background description.
            research: Research question.
            deg_results: Differential expression results.
            trajectory_results: Trajectory analysis results.
            existing_analysis: Existing analysis info.

        Returns:
            Markdown report string.
        """
        lines = []

        lines.append(f"# Single-Cell Transcriptomics Analysis Report\n")
        lines.append(f"**Project**: {self.project_name}\n")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if background:
            lines.append("\n## Research Background\n")
            lines.append(f"{background}\n")

        if research:
            lines.append("\n## Research Objective\n")
            lines.append(f"{research}\n")

        lines.append("\n## Data Overview\n")
        if adata is not None:
            lines.append(self._generate_data_overview(adata, existing_analysis))
        else:
            lines.append("*No data*")

        if existing_analysis and existing_analysis.get("has_analysis"):
            lines.append("\n## Existing Analysis\n")
            lines.append("Data already contains the following analysis results:\n")
            for analysis_type in existing_analysis.get("types", []):
                lines.append(f"- {analysis_type}\n")

        lines.append("\n## Analysis Steps\n")
        lines.append(self._generate_steps_table(steps))

        lines.append("\n## Clustering Results\n")
        if adata is not None and "leiden" in adata.obs:
            lines.append(self._generate_clustering_results(adata))
        else:
            lines.append("*No clustering results*")

        lines.append("\n## Differentially Expressed Genes (Top Markers)\n")
        if deg_results:
            lines.append(self._generate_deg_results(deg_results))
        else:
            lines.append("*No DEG results*")

        lines.append("\n## Trajectory Analysis\n")
        if trajectory_results:
            lines.append(self._generate_trajectory_section(trajectory_results))
        else:
            lines.append("*No trajectory analysis results*")

        lines.append("\n## Quality Assessment\n")
        lines.append(self._generate_quality_assessment(steps))

        lines.append("\n## Generated Files\n")
        lines.append(self._generate_files_list())

        return "".join(lines)

    def _generate_data_overview(
        self, adata: Any, existing_analysis: dict[str, Any] | None
    ) -> str:
        """Generate data overview table."""
        lines = []
        lines.append(f"| Metric | Value |\n")
        lines.append(f"|--------|-------|\n")
        lines.append(f"| Cells | {adata.n_obs:,} |\n")
        lines.append(f"| Genes | {adata.n_vars:,} |\n")

        if hasattr(adata, "obs"):
            if "n_genes" in adata.obs:
                mean_genes = adata.obs["n_genes"].mean()
                lines.append(f"| Mean genes per cell | {mean_genes:.0f} |\n")

            if "n_counts" in adata.obs:
                mean_counts = adata.obs["n_counts"].mean()
                lines.append(f"| Mean UMI count | {mean_counts:.0f} |\n")

        if "leiden" in adata.obs:
            n_clusters = adata.obs["leiden"].nunique()
            lines.append(f"| Clusters | {n_clusters} |\n")

        return "".join(lines)

    def _generate_steps_table(self, steps: list[Any]) -> str:
        """Generate analysis steps table."""
        if not steps:
            return "*No analysis steps recorded*"

        lines = []
        lines.append("| Step | Status | Skill | Metrics |\n")
        lines.append("|------|--------|-------|---------|\n")

        for step in steps:
            step_num = step.step if hasattr(step, "step") else "?"
            status = "✓" if step.observation.get("success") else "✗"
            skill = step.skill_id or "N/A"
            metrics = step.observation.get("metrics", {})
            metrics_str = (
                ", ".join(f"{k}={v}" for k, v in list(metrics.items())[:3])
                if metrics
                else "-"
            )
            lines.append(f"| {step_num} | {status} | {skill} | {metrics_str} |\n")

        return "".join(lines)

    def _generate_clustering_results(self, adata: Any) -> str:
        """Generate clustering results table."""
        lines = []

        lines.append("| Cluster | Cells | Percentage |\n")
        lines.append("|---------|-------|------------|\n")

        cluster_counts = adata.obs["leiden"].value_counts().sort_index()
        for cluster, count in cluster_counts.items():
            pct = count / adata.n_obs * 100
            lines.append(f"| Cluster {cluster} | {count:,} | {pct:.1f}% |\n")

        return "".join(lines)

    def _generate_deg_results(self, deg_results: dict[str, Any]) -> str:
        """Generate DEG results tables."""
        lines = []

        for cluster, genes in list(deg_results.items())[:5]:
            lines.append(f"### Cluster {cluster}\n")
            lines.append("| Rank | Gene | Score |\n")
            lines.append("|------|------|-------|\n")

            for i, gene_info in enumerate(genes[:10], 1):
                gene = gene_info.get("gene", "N/A")
                score = gene_info.get("score", "N/A")
                if isinstance(score, float):
                    score_str = f"{score:.4f}"
                else:
                    score_str = str(score)
                lines.append(f"| {i} | {gene} | {score_str} |\n")

            lines.append("\n")

        return "".join(lines)

    def _generate_trajectory_section(
        self, trajectory_results: dict[str, Any]
    ) -> str:
        """Generate trajectory analysis section."""
        lines = []

        for key, value in trajectory_results.items():
            lines.append(f"- **{key}**: {value}\n")

        lines.append("\n")
        return "".join(lines)

    def _generate_quality_assessment(self, steps: list[Any]) -> str:
        """Generate quality assessment section."""
        lines = []

        total_steps = len(steps)
        successful_steps = sum(
            1 for s in steps if s.observation.get("success")
        )
        failed_steps = total_steps - successful_steps

        lines.append(f"- Total steps: {total_steps}\n")
        lines.append(f"- Successful steps: {successful_steps}\n")
        lines.append(f"- Failed steps: {failed_steps}\n")

        if failed_steps > 0:
            lines.append("\n**Failure details:**\n")
            for step in steps:
                if not step.observation.get("success"):
                    skill = step.skill_id or "unknown"
                    lines.append(f"- {skill}: {step.observation.get('error', 'Unknown error')}\n")

        return "".join(lines)

    def _generate_files_list(self) -> str:
        """Generate list of output files."""
        import os

        lines = []

        if not self.output_dir.exists():
            return "*Output directory does not exist*"

        for root, dirs, files in os.walk(self.output_dir):
            root_path = Path(root)
            for f in files:
                path = root_path / f
                try:
                    size = path.stat().st_size
                    size_str = f"{size / 1024:.1f} KB"
                except OSError:
                    size_str = "N/A"

                rel_path = path.relative_to(self.output_dir)
                lines.append(f"- {rel_path} ({size_str})\n")

        if not lines:
            lines.append("*No generated files*\n")

        return "".join(lines)

    def save_report(
        self,
        adata: Any,
        steps: list[Any],
        plan: list[dict[str, Any]] | None = None,
        background: str = "",
        research: str = "",
        deg_results: dict[str, Any] | None = None,
        trajectory_results: dict[str, Any] | None = None,
        existing_analysis: dict[str, Any] | None = None,
    ) -> Path:
        """
        Generate and save markdown report.

        Args:
            Same as generate_markdown_report.

        Returns:
            Path to saved report file.
        """
        report = self.generate_markdown_report(
            adata=adata,
            steps=steps,
            plan=plan,
            background=background,
            research=research,
            deg_results=deg_results,
            trajectory_results=trajectory_results,
            existing_analysis=existing_analysis,
        )

        report_path = self.output_dir / "Report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info("Saved report to %s", report_path)
        return report_path

    def generate_reproducible_code(
        self,
        steps: list[Any],
        plan: list[dict[str, Any]] | None = None,
        data_path: str = "data.h5ad",
    ) -> str:
        """
        Generate reproducible Python script.

        Args:
            steps: List of StepRecord objects.
            plan: Original analysis plan.
            data_path: Path to input data.

        Returns:
            Python script string.
        """
        lines = []

        lines.append("#!/usr/bin/env python3\n")
        lines.append("# -*- coding: utf-8 -*-\n")
        lines.append(f"# Generated by CellForge Agent on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"# Project: {self.project_name}\n")
        lines.append("\n")
        lines.append('"""\n')
        lines.append("Single-cell RNA-seq Analysis Pipeline\n")
        lines.append(f"Data: {data_path}\n")
        lines.append('"""\n')
        lines.append("\n")
        lines.append("import scanpy as sc\n")
        lines.append("import anndata as ad\n")
        lines.append("import numpy as np\n")
        lines.append("import pandas as pd\n")
        lines.append("import matplotlib.pyplot as plt\n")
        lines.append("\n")

        lines.append("# Configuration\n")
        lines.append(f"DATA_PATH = '{data_path}'\n")
        lines.append(f"OUTPUT_DIR = '{self.output_dir}'\n")
        lines.append("\n")

        lines.append("def load_data(path):\n")
        lines.append('    """Load and return AnnData object."""\n')
        lines.append("    return sc.read_h5ad(path)\n")
        lines.append("\n")

        lines.append("def main():\n")
        lines.append('    """Main analysis pipeline."""\n')
        lines.append("    # Load data\n")
        lines.append("    adata = load_data(DATA_PATH)\n")
        lines.append("    print(f'Loaded data: {adata.n_obs} cells, {adata.n_vars} genes')\n")
        lines.append("\n")

        step_num = 0
        for step in steps:
            if not step.observation.get("success"):
                continue

            step_num += 1
            skill_id = step.skill_id or ""
            action = step.action or ""

            lines.append(f"    # Step {step_num}: {skill_id}\n")

            if "filter" in skill_id.lower():
                lines.append("    sc.pp.filter_cells(adata, min_genes=200, min_cells=3)\n")
            elif "normalize" in skill_id.lower():
                lines.append("    sc.pp.normalize_total(adata, target_sum=1e4)\n")
                lines.append("    sc.pp.log1p(adata)\n")
            elif "hvg" in skill_id.lower() or "highly_variable" in skill_id.lower():
                lines.append("    sc.pp.highly_variable_genes(adata, n_top_genes=2000)\n")
            elif "scale" in skill_id.lower():
                lines.append("    sc.pp.scale(adata, max_value=10)\n")
            elif "pca" in skill_id.lower():
                lines.append("    sc.tl.pca(adata, n_comps=50)\n")
            elif "neighbors" in skill_id.lower():
                lines.append("    sc.pp.neighbors(adata, n_neighbors=15)\n")
            elif "cluster" in skill_id.lower() or "leiden" in skill_id.lower():
                lines.append("    sc.tl.leiden(adata, resolution=0.5)\n")
            elif "umap" in skill_id.lower():
                lines.append("    sc.tl.umap(adata, min_dist=0.5)\n")
            elif "rank_genes" in skill_id.lower() or "deg" in skill_id.lower():
                lines.append("    sc.tl.rank_genes_groups(adata, 'leiden', method='t-test')\n")
            elif "paga" in skill_id.lower():
                lines.append("    sc.tl.paga(adata)\n")

            lines.append(f"    print('{skill_id} completed')\n")
            lines.append("\n")

        lines.append("    # Save processed data\n")
        lines.append("    adata.write_h5ad(f'{OUTPUT_DIR}/processed.h5ad')\n")
        lines.append("    print('Saved processed data')\n")
        lines.append("\n")

        lines.append("    # Generate visualizations\n")
        if any("leiden" in s.skill_id.lower() for s in steps if s.observation.get("success")):
            lines.append("    sc.pl.umap(adata, color=['leiden'], save='_leiden.png')\n")
            lines.append("    print('Saved UMAP visualization')\n")

        lines.append("\n")
        lines.append("if __name__ == '__main__':\n")
        lines.append("    main()\n")

        return "".join(lines)

    def save_reproducible_code(
        self,
        steps: list[Any],
        plan: list[dict[str, Any]] | None = None,
        data_path: str = "data.h5ad",
    ) -> Path:
        """
        Generate and save reproducible Python script.

        Args:
            Same as generate_reproducible_code.

        Returns:
            Path to saved script file.
        """
        code = self.generate_reproducible_code(
            steps=steps, plan=plan, data_path=data_path
        )

        code_path = self.output_dir / "reproducible_code.py"
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)

        logger.info("Saved reproducible code to %s", code_path)
        return code_path
