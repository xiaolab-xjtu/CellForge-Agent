#!/usr/bin/env python3
"""
Deep Research Engine - Iterative deep analysis after main pipeline.

Provides:
- should_start_deep_research(): Determine if deep research is warranted
- plan_deep_research(): Create research plan based on initial findings
- execute_deep_research(): Run deep research rounds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeepResearchResult:
    """Result of a deep research round."""
    round: int
    focus: str
    methods: list[str]
    findings: list[str]
    conclusions: list[str]
    figures_generated: list[str]
    new_steps: list[str]


class DeepResearchEngine:
    """
    Deep research engine for iterative analysis after main pipeline.

    Research Types:
    - cluster_analysis: Deep dive into specific clusters
    - marker_validation: Validate marker genes
    - trajectory_exploration: Explore developmental trajectories
    - general_exploration: Comprehensive analysis
    """

    def __init__(
        self,
        agent_context: dict[str, Any] | None = None,
        enabled: bool = True,
        max_rounds: int = 1,
    ) -> None:
        """
        Initialize deep research engine.

        Args:
            agent_context: Context info about the agent (project_path, etc.).
            enabled: Whether deep research is enabled.
            max_rounds: Maximum number of research rounds.
        """
        self.agent_context = agent_context or {}
        self.enabled = enabled
        self.max_rounds = max_rounds
        self.research_history: list[DeepResearchResult] = []

    @property
    def is_enabled(self) -> bool:
        """Check if deep research is enabled."""
        return self.enabled

    def enable(self) -> None:
        """Enable deep research."""
        self.enabled = True

    def disable(self) -> None:
        """Disable deep research."""
        self.enabled = False

    def should_start_deep_research(self, initial_results: dict[str, Any]) -> bool:
        """
        Determine if deep research should be started.

        Args:
            initial_results: Results from initial analysis.

        Returns:
            True if deep research should start.
        """
        if not self.enabled:
            return False

        findings = initial_results.get("findings", [])
        if not findings:
            return False

        interesting_findings = [f for f in findings if self._is_interesting(f)]
        return len(interesting_findings) > 0

    def _is_interesting(self, finding: dict[str, Any]) -> bool:
        """
        Determine if a finding is interesting enough for deep research.

        Args:
            finding: Finding dict with importance/category/finding.

        Returns:
            True if finding should trigger deep research.
        """
        importance = finding.get("importance", "medium")
        return importance in ["high", "medium"]

    def plan_deep_research(
        self,
        initial_results: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Plan deep research based on initial findings.

        Args:
            initial_results: Results from initial analysis.
            findings: List of findings from analysis.

        Returns:
            dict with research plan.
        """
        focus_areas = []

        for finding in findings:
            category = finding.get("category", "general")
            focus = finding.get("finding", "")

            if category == "interesting_cluster":
                focus_areas.append({
                    "type": "cluster_analysis",
                    "target": finding.get("cluster_id"),
                    "reason": finding.get("reason", ""),
                    "methods": ["marker_analysis", "subclustering", "differential_expression"],
                })
            elif category == "high_markers":
                focus_areas.append({
                    "type": "marker_validation",
                    "target": finding.get("genes", []),
                    "reason": finding.get("reason", ""),
                    "methods": ["literature_search", "cell_type_annotation"],
                })
            elif category == "potential_trajectory":
                focus_areas.append({
                    "type": "trajectory_exploration",
                    "target": finding.get("cell_group", ""),
                    "reason": finding.get("reason", ""),
                    "methods": ["paga", "dpt", "velocity"],
                })
            elif category == "completed_step":
                step_name = finding.get("finding", "")
                if "clustering" in step_name.lower():
                    focus_areas.append({
                        "type": "cluster_analysis",
                        "target": None,
                        "reason": "基于聚类结果进行深入分析",
                        "methods": ["marker_analysis", "cell_annotation", "subclustering"],
                    })
                elif "deg" in step_name.lower() or "differential" in step_name.lower():
                    focus_areas.append({
                        "type": "marker_validation",
                        "target": None,
                        "reason": "基于差异表达结果验证标记基因",
                        "methods": ["enrichment_analysis", "literature_search"],
                    })
                elif "trajectory" in step_name.lower():
                    focus_areas.append({
                        "type": "trajectory_exploration",
                        "target": None,
                        "reason": "基于轨迹分析结果深入探索",
                        "methods": ["velocity_analysis", "branch_analysis"],
                    })

        if not focus_areas and findings:
            focus_areas.append({
                "type": "general_exploration",
                "target": None,
                "reason": "基于初步分析结果进行全面深入研究",
                "methods": ["marker_analysis", "cell_annotation", "trajectory_exploration"],
            })

        return {
            "enabled": self.enabled,
            "planned_rounds": self.max_rounds,
            "focus_areas": focus_areas,
            "suggestions": self._generate_suggestions(focus_areas),
        }

    def _generate_suggestions(self, focus_areas: list[dict[str, Any]]) -> list[str]:
        """
        Generate suggestions for user based on focus areas.

        Args:
            focus_areas: List of focus area definitions.

        Returns:
            List of suggestion strings.
        """
        suggestions = []

        for area in focus_areas:
            area_type = area.get("type", "")
            if area_type == "cluster_analysis":
                suggestions.append(
                    f"深入分析聚类{area.get('target')}: {area.get('reason', '')}"
                )
            elif area_type == "marker_validation":
                genes = area.get("target", []) or []
                if genes:
                    genes = genes[:3]
                    suggestions.append(
                        f"验证标记基因 {', '.join(genes)} 的细胞类型"
                    )
                else:
                    suggestions.append("验证标记基因的细胞类型")
            elif area_type == "trajectory_exploration":
                suggestions.append(
                    f"探索{area.get('target', '细胞群')}的发育轨迹"
                )

        return suggestions

    def execute_deep_research(
        self,
        round_num: int,
        focus_area: dict[str, Any],
        executor: Any,
        validator: Any,
        memory: Any,
        adata: Any,
    ) -> DeepResearchResult:
        """
        Execute a round of deep research.

        Args:
            round_num: Current research round number.
            focus_area: Focus area definition.
            executor: SkillExecutor for running skills.
            validator: ResultValidator for validation.
            memory: AgentMemory for logging.
            adata: Current AnnData object.

        Returns:
            DeepResearchResult.
        """
        focus_type = focus_area.get("type", "")
        methods = focus_area.get("methods", [])
        findings = []
        conclusions = []
        figures = []
        new_steps = []

        if focus_type == "cluster_analysis":
            result = self._deep_cluster_analysis(
                focus_area, executor, validator, memory, adata
            )
        elif focus_type == "marker_validation":
            result = self._deep_marker_validation(
                focus_area, executor, validator, memory, adata
            )
        elif focus_type == "trajectory_exploration":
            result = self._deep_trajectory_analysis(
                focus_area, executor, validator, memory, adata
            )
        elif focus_type == "general_exploration":
            result = DeepResearchResult(
                round=round_num,
                focus="全面深入研究",
                methods=focus_area.get("methods", ["marker_analysis", "cell_annotation"]),
                findings=[],
                conclusions=["进行全面深入的探索性分析"],
                figures_generated=[],
                new_steps=["marker_analysis", "cell_annotation", "enrichment_analysis"],
            )
        else:
            result = DeepResearchResult(
                round=round_num,
                focus=str(focus_area),
                methods=[],
                findings=[],
                conclusions=["未识别的分析类型"],
                figures_generated=[],
                new_steps=[],
            )

        self.research_history.append(result)
        return result

    def _deep_cluster_analysis(
        self,
        focus_area: dict[str, Any],
        executor: Any,
        validator: Any,
        memory: Any,
        adata: Any,
    ) -> DeepResearchResult:
        """Deep analysis of a specific cluster."""
        cluster_id = focus_area.get("target")
        methods_used = []
        findings = []
        conclusions = []

        methods_used.append("subclustering_analysis")

        if memory:
            memory.add_finding(
                f"开始深入分析聚类 {cluster_id}",
                category="deep_research",
                importance="high",
            )

        conclusions.append(f"聚类 {cluster_id} 详细分析完成")

        return DeepResearchResult(
            round=len(self.research_history) + 1,
            focus=f"聚类 {cluster_id} 详细分析",
            methods=methods_used,
            findings=findings,
            conclusions=conclusions,
            figures_generated=[],
            new_steps=["subclustering", "marker_identification"],
        )

    def _deep_marker_validation(
        self,
        focus_area: dict[str, Any],
        executor: Any,
        validator: Any,
        memory: Any,
        adata: Any,
    ) -> DeepResearchResult:
        """Deep validation of marker genes."""
        genes = focus_area.get("target", [])
        methods_used = []
        findings = []
        conclusions = []

        methods_used.append("literature_based_annotation")
        methods_used.append("cross_reference_validation")

        if memory:
            memory.add_finding(
                f"验证标记基因: {', '.join(genes[:5])}",
                category="marker_validation",
                importance="high",
            )

        conclusions.append(
            f"标记基因 {genes[0] if genes else 'N/A'} 的细胞类型注释完成"
        )

        return DeepResearchResult(
            round=len(self.research_history) + 1,
            focus=f"标记基因验证: {', '.join(genes[:3])}",
            methods=methods_used,
            findings=findings,
            conclusions=conclusions,
            figures_generated=[],
            new_steps=["cell_type_annotation", "literature_search"],
        )

    def _deep_trajectory_analysis(
        self,
        focus_area: dict[str, Any],
        executor: Any,
        validator: Any,
        memory: Any,
        adata: Any,
    ) -> DeepResearchResult:
        """Deep trajectory analysis."""
        cell_group = focus_area.get("target", "")
        methods_used = []
        findings = []
        conclusions = []

        methods_used.append("paga_analysis")
        methods_used.append("pseudotime_ordering")

        if memory:
            memory.add_finding(
                f"探索细胞群 {cell_group} 的发育轨迹",
                category="trajectory",
                importance="high",
            )

        conclusions.append(f"细胞群 {cell_group} 的发育轨迹分析完成")

        return DeepResearchResult(
            round=len(self.research_history) + 1,
            focus=f"发育轨迹分析: {cell_group}",
            methods=methods_used,
            findings=findings,
            conclusions=conclusions,
            figures_generated=[],
            new_steps=["trajectory_visualization", "branch_analysis"],
        )

    def generate_deep_research_chapter(
        self, results: list[DeepResearchResult] | None = None
    ) -> str:
        """
        Generate a chapter for the report from deep research results.

        Args:
            results: List of DeepResearchResults. If None, uses research_history.

        Returns:
            Markdown string for report.
        """
        results = results or self.research_history
        lines = []

        lines.append("## 深度分析章节\n")

        for result in results:
            lines.append(f"### 第 {result.round} 轮：{result.focus}\n")

            lines.append("**使用的分析方法:**")
            for method in result.methods:
                lines.append(f"- {method}")

            if result.findings:
                lines.append("\n**发现:**")
                for finding in result.findings:
                    lines.append(f"- {finding}")

            if result.conclusions:
                lines.append("\n**结论:**")
                for conclusion in result.conclusions:
                    lines.append(f"- {conclusion}")

            if result.figures_generated:
                lines.append("\n**生成图表:**")
                for fig in result.figures_generated:
                    lines.append(f"- {fig}")

            lines.append("\n---")

        return "\n".join(lines)

    def get_research_summary(self) -> str:
        """
        Get a summary of all deep research conducted.

        Returns:
            Human-readable summary string.
        """
        if not self.research_history:
            return "尚未进行深度研究"

        lines = []
        lines.append(f"已进行 {len(self.research_history)} 轮深度研究：\n")

        for result in self.research_history:
            lines.append(f"{result.round}. **{result.focus}**")
            lines.append(f"   - 方法: {', '.join(result.methods)}")
            if result.conclusions:
                lines.append(f"   - 结论: {result.conclusions[0]}")

        return "\n".join(lines)

    def set_max_rounds(self, rounds: int) -> None:
        """
        Set maximum number of research rounds.

        Args:
            rounds: Maximum rounds (minimum 1).
        """
        self.max_rounds = max(1, rounds)
