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

        lines.append(f"# 单细胞转录组分析报告\n")
        lines.append(f"**项目**: {self.project_name}\n")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        if background:
            lines.append("\n## 研究背景\n")
            lines.append(f"{background}\n")

        if research:
            lines.append("\n## 研究目的\n")
            lines.append(f"{research}\n")

        lines.append("\n## 数据概况\n")
        if adata is not None:
            lines.append(self._generate_data_overview(adata, existing_analysis))
        else:
            lines.append("*无数据*")

        if existing_analysis and existing_analysis.get("has_analysis"):
            lines.append("\n## 已有分析\n")
            lines.append("数据已包含以下分析结果：\n")
            for analysis_type in existing_analysis.get("types", []):
                lines.append(f"- {analysis_type}\n")

        lines.append("\n## 分析步骤详情\n")
        lines.append(self._generate_steps_table(steps))

        lines.append("\n## 聚类结果\n")
        if adata is not None and "leiden" in adata.obs:
            lines.append(self._generate_clustering_results(adata))
        else:
            lines.append("*无聚类结果*")

        lines.append("\n## 差异表达基因 (Top Markers)\n")
        if deg_results:
            lines.append(self._generate_deg_results(deg_results))
        else:
            lines.append("*无差异表达基因结果*")

        lines.append("\n## 轨迹分析\n")
        if trajectory_results:
            lines.append(self._generate_trajectory_section(trajectory_results))
        else:
            lines.append("*无轨迹分析结果*")

        lines.append("\n## 质量评估\n")
        lines.append(self._generate_quality_assessment(steps))

        lines.append("\n## 生成的文件\n")
        lines.append(self._generate_files_list())

        return "".join(lines)

    def _generate_data_overview(
        self, adata: Any, existing_analysis: dict[str, Any] | None
    ) -> str:
        """Generate data overview table."""
        lines = []
        lines.append(f"| 指标 | 值 |\n")
        lines.append(f"|------|-----|\n")
        lines.append(f"| 细胞数 | {adata.n_obs:,} |\n")
        lines.append(f"| 基因数 | {adata.n_vars:,} |\n")

        if hasattr(adata, "obs"):
            if "n_genes" in adata.obs:
                mean_genes = adata.obs["n_genes"].mean()
                lines.append(f"| 平均基因数 | {mean_genes:.0f} |\n")

            if "n_counts" in adata.obs:
                mean_counts = adata.obs["n_counts"].mean()
                lines.append(f"| 平均UMI计数 | {mean_counts:.0f} |\n")

        if "leiden" in adata.obs:
            n_clusters = adata.obs["leiden"].nunique()
            lines.append(f"| 聚类数 | {n_clusters} |\n")

        return "".join(lines)

    def _generate_steps_table(self, steps: list[Any]) -> str:
        """Generate analysis steps table."""
        if not steps:
            return "*无分析步骤记录*"

        lines = []
        lines.append("| 步骤 | 状态 | Skill | 指标 |\n")
        lines.append("|------|------|-------|------|\n")

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

        lines.append("| Cluster | 细胞数 | 百分比 |\n")
        lines.append("|--------|--------|--------|\n")

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

        lines.append(f"- 总步骤数: {total_steps}\n")
        lines.append(f"- 成功步骤: {successful_steps}\n")
        lines.append(f"- 失败步骤: {failed_steps}\n")

        if failed_steps > 0:
            lines.append("\n**失败详情:**\n")
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
            return "*输出目录不存在*"

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
            lines.append("*无生成文件*\n")

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
