#!/usr/bin/env python3
"""
Data Consistency Checker - Validates data against background description.

Checks:
- Species consistency (human/mouse/rat) via gene markers
- Tissue type inference from marker genes
- Cell count reasonableness (100 - 1,000,000)
- Gene count reasonableness (500 - 60,000)
- Existing analysis detection
- Research keyword extraction
"""

from __future__ import annotations

import re
from typing import Any

import scanpy as sc


class DataConsistencyChecker:
    """
    Check consistency between background description and actual data.
    """

    def __init__(self) -> None:
        """Initialize checker with species and tissue patterns."""
        self.species_patterns = {
            "human": ["human", "homo sapiens", "humanized", "人"],
            "mouse": ["mouse", "mus musculus", "murine", "小鼠"],
            "rat": ["rat", "rattus", "大鼠"],
            "both": ["human mouse", "xenograft", "异种", "cross-species"],
        }

        self.tissue_patterns = {
            "PBMC": [
                "pbmc",
                "peripheral blood mononuclear",
                "外周血",
                "blood",
                "血液",
            ],
            "tumor": ["tumor", "cancer", "carcinoma", "肿瘤", "恶性"],
            "brain": [
                "brain",
                "neuron",
                "cortex",
                "脑",
                "神经",
                "hippocampus",
            ],
            "lung": ["lung", "pulmonary", "肺", "alveolar"],
            "liver": ["liver", "hepatic", "肝", "hepatocyte"],
            "kidney": ["kidney", "renal", "肾", "nephron"],
            "heart": ["heart", "cardiac", "心肌", "心"],
            "spleen": ["spleen", "splenic", "脾脏"],
            "bone_marrow": ["bone marrow", "bmc", "骨髓"],
            "breast": ["breast", "mammary", "乳腺"],
            "skin": ["skin", "dermal", "皮肤"],
            "intestinal": ["intestine", "intestinal", "gut", "肠", "colon"],
        }

        self.disease_patterns = {
            "cancer": [
                "cancer",
                "tumor",
                "carcinoma",
                "malignant",
                "肿瘤",
                "恶性",
                "melanoma",
            ],
            "COVID": ["covid", "sars-cov-2", "新冠", "coronavirus"],
            "autoimmune": [
                "autoimmune",
                "lupus",
                "rheumatoid",
                "风湿",
                "类风湿",
            ],
            "diabetes": ["diabetes", "diabetic", "糖尿病"],
            "neurodegenerative": [
                "alzheimer",
                "parkinson",
                "neurodegenerative",
                "神经退行",
            ],
            "fibrosis": ["fibrosis", "fibrotic", "纤维化"],
        }

    def check(
        self, adata: Any, background: str, research: str
    ) -> dict[str, Any]:
        """
        Perform all consistency checks.

        Args:
            adata: AnnData object to check.
            background: Background description text.
            research: Research question text.

        Returns:
            dict with keys: consistent (bool), issues (list), warnings (list),
                           suggestions (list), details (dict)
        """
        issues = []
        warnings = []
        suggestions = []

        species_check = self.check_species(adata, background)
        if not species_check["consistent"]:
            issues.append(species_check["issue"])

        tissue_check = self.check_tissue_type(adata, background)
        if not tissue_check["consistent"]:
            warnings.append(tissue_check["warning"])

        cell_count_check = self.check_cell_count(adata)
        if not cell_count_check["acceptable"]:
            warnings.append(cell_count_check["warning"])

        gene_count_check = self.check_gene_count(adata)
        if not gene_count_check["acceptable"]:
            warnings.append(gene_count_check["warning"])

        existing_analysis = self.check_existing_analysis(adata)
        if existing_analysis["has_analysis"]:
            suggestions.append(
                f"数据已包含分析结果: {', '.join(existing_analysis['types'])}"
            )

        research_keywords = self.extract_research_keywords(research)
        if research_keywords:
            suggestions.append(f"研究关键词: {', '.join(research_keywords)}")

        all_consistent = len(issues) == 0

        return {
            "consistent": all_consistent,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
            "details": {
                "species": species_check,
                "tissue": tissue_check,
                "cell_count": cell_count_check,
                "gene_count": gene_count_check,
                "existing_analysis": existing_analysis,
            },
        }

    def check_species(self, adata: Any, background: str) -> dict[str, Any]:
        """
        Check if species in background matches data.

        Args:
            adata: AnnData object.
            background: Background description.

        Returns:
            dict with consistent, issue, background_species, data_species.
        """
        background_lower = background.lower()

        bg_species = None
        for species, patterns in self.species_patterns.items():
            for pattern in patterns:
                if pattern in background_lower:
                    bg_species = species
                    break
            if bg_species:
                break

        data_species = self.infer_species_from_data(adata)

        if bg_species and data_species:
            if bg_species != data_species and not (
                bg_species == "human" and data_species == "both"
            ):
                return {
                    "consistent": False,
                    "issue": f"物种不匹配: 背景描述为{self._species_name(bg_species)}，"
                    f"数据推断为{self._species_name(data_species)}",
                    "background_species": bg_species,
                    "data_species": data_species,
                }

        return {
            "consistent": True,
            "background_species": bg_species,
            "data_species": data_species,
        }

    def infer_species_from_data(self, adata: Any) -> str | None:
        """
        Infer species from gene names in data.

        Args:
            adata: AnnData object.

        Returns:
            Species string ('human', 'mouse', 'both') or None.
        """
        if adata.var_names is None or len(adata.var_names) == 0:
            return None

        sample_genes = (
            adata.var_names[:100].tolist()
            if len(adata.var_names) > 100
            else adata.var_names.tolist()
        )

        human_count = 0
        mouse_count = 0

        human_markers = [
            "ACTB", "GAPDH", "B2M", "PPIA", "RPL13A", "CD44", "CD45", "PTPRC"
        ]
        mouse_markers = [
            "Actb", "Gapdh", "B2m", "Ppia", "Rpl13a", "Cd44", "Cd45", "Ptprc"
        ]

        for gene in sample_genes:
            gene_upper = str(gene).upper()
            gene_lower = str(gene).lower()

            for marker in human_markers:
                if marker in gene_upper:
                    human_count += 1
                    break

            for marker in mouse_markers:
                if marker.upper() in gene_upper or marker.lower() in gene_lower:
                    mouse_count += 1
                    break

        total = human_count + mouse_count
        if total == 0:
            return None

        human_ratio = human_count / total
        if human_ratio > 0.7:
            return "human"
        elif (1 - human_ratio) > 0.7:
            return "mouse"
        else:
            return "both"

    def check_tissue_type(self, adata: Any, background: str) -> dict[str, Any]:
        """
        Check if tissue type in background matches data.

        Args:
            adata: AnnData object.
            background: Background description.

        Returns:
            dict with consistent, warning, background_tissue, data_tissue.
        """
        background_lower = background.lower()

        bg_tissue = None
        for tissue, patterns in self.tissue_patterns.items():
            for pattern in patterns:
                if pattern in background_lower:
                    bg_tissue = tissue
                    break
            if bg_tissue:
                break

        data_tissue = self.infer_tissue_from_markers(adata)

        if bg_tissue and data_tissue and bg_tissue != data_tissue:
            return {
                "consistent": False,
                "warning": f"组织类型可能不匹配: 背景描述为{bg_tissue}，"
                f"数据marker指向{data_tissue}",
                "background_tissue": bg_tissue,
                "data_tissue": data_tissue,
            }

        return {
            "consistent": True,
            "background_tissue": bg_tissue,
            "data_tissue": data_tissue,
        }

    def infer_tissue_from_markers(self, adata: Any) -> str | None:
        """
        Infer tissue type from marker genes in data.

        Args:
            adata: AnnData object.

        Returns:
            Tissue type string or None.
        """
        if adata.var_names is None or len(adata.var_names) == 0:
            return None

        tissue_markers = {
            "PBMC": [
                "CD3D", "CD3E", "CD4", "CD8A", "CD19", "MS4A1", "NKG7", "GNLY"
            ],
            "brain": ["SNAP25", "SYP", "GFAP", "OLIG1", "MBP", "PLP1", "NEUN"],
            "liver": ["ALB", "APOC3", "HP", "TF", "Apoe", "Liver"],
            "lung": ["SFTPC", "SFTPA1", "FOXJ1", "KRT5", "ABCA3"],
            "kidney": ["NPHS1", "NPHS2", "PODXL", "WT1", "KRT8"],
            "heart": ["MYH6", "MYH7", "TNNI3", "TNNT2", "ACTC1"],
            "breast": ["ESR1", "PGR", "ERBB2", "KRT8", "KRT18"],
            "tumor": ["EPCAM", "KRT5", "KRT14", "TP63", "MKI67"],
        }

        adata_genes = set(str(g).upper() for g in adata.var_names)

        best_match = None
        best_score = 0

        for tissue, markers in tissue_markers.items():
            score = sum(1 for m in markers if m.upper() in adata_genes)
            if score > best_score:
                best_score = score
                best_match = tissue

        return best_match if best_score >= 2 else None

    def check_cell_count(self, adata: Any) -> dict[str, Any]:
        """
        Check if cell count is reasonable.

        Args:
            adata: AnnData object.

        Returns:
            dict with acceptable, warning, n_cells.
        """
        n_cells = adata.n_obs

        if n_cells < 100:
            return {
                "acceptable": False,
                "warning": f"细胞数过少 ({n_cells})，可能无法进行可靠分析",
                "n_cells": n_cells,
            }
        elif n_cells > 1000000:
            return {
                "acceptable": False,
                "warning": f"细胞数过多 ({n_cells})，可能需要降采样处理",
                "n_cells": n_cells,
            }

        return {"acceptable": True, "n_cells": n_cells}

    def check_gene_count(self, adata: Any) -> dict[str, Any]:
        """
        Check if gene count is reasonable.

        Args:
            adata: AnnData object.

        Returns:
            dict with acceptable, warning, n_genes.
        """
        n_genes = adata.n_vars

        if n_genes < 500:
            return {
                "acceptable": False,
                "warning": f"基因数过少 ({n_genes})，可能数据质量有问题",
                "n_genes": n_genes,
            }
        elif n_genes > 60000:
            return {
                "acceptable": False,
                "warning": f"基因数过多 ({n_genes})，可能包含非编码RNA",
                "n_genes": n_genes,
            }

        return {"acceptable": True, "n_genes": n_genes}

    def check_existing_analysis(self, adata: Any) -> dict[str, Any]:
        """
        Detect existing analysis in h5ad file.

        Args:
            adata: AnnData object.

        Returns:
            dict with has_analysis, types, details.
        """
        existing: dict[str, Any] = {
            "has_analysis": False,
            "types": [],
            "details": {},
        }

        if "X_pca" in adata.obsm:
            existing["has_analysis"] = True
            existing["types"].append(f"PCA ({adata.obsm['X_pca'].shape[1]} PCs)")
            existing["details"]["pca"] = adata.obsm["X_pca"].shape

        if "X_umap" in adata.obsm:
            existing["has_analysis"] = True
            existing["types"].append("UMAP")
            existing["details"]["umap"] = adata.obsm["X_umap"].shape

        if "X_tsne" in adata.obsm:
            existing["has_analysis"] = True
            existing["types"].append("t-SNE")
            existing["details"]["tsne"] = adata.obsm["X_tsne"].shape

        if "leiden" in adata.obs:
            existing["has_analysis"] = True
            n_clusters = adata.obs["leiden"].nunique()
            existing["types"].append(f"Leiden聚类 ({n_clusters} clusters)")
            existing["details"]["leiden"] = n_clusters

        if "louvain" in adata.obs:
            existing["has_analysis"] = True
            n_clusters = adata.obs["louvain"].nunique()
            existing["types"].append(f"Louvain聚类 ({n_clusters} clusters)")
            existing["details"]["louvain"] = n_clusters

        if "rank_genes_groups" in adata.uns:
            existing["has_analysis"] = True
            existing["types"].append("差异表达分析")
            existing["details"]["deg"] = True

        if "cell_type" in adata.obs or "celltype" in adata.obs:
            existing["has_analysis"] = True
            existing["types"].append("细胞类型注释")
            existing["details"]["annotated"] = True

        return existing

    def extract_research_keywords(self, research: str) -> list[str]:
        """
        Extract key research topics from research description.

        Args:
            research: Research question text.

        Returns:
            List of extracted keywords.
        """
        keywords = []

        research_lower = research.lower()

        for category, patterns in self.disease_patterns.items():
            for pattern in patterns:
                if pattern in research_lower:
                    keywords.append(category)
                    break

        research_upper = research.upper()
        research_chinese = re.findall(r"[\u4e00-\u9fff]+", research)

        important_patterns = [
            "comparison",
            "compare",
            "comparative",
            "比较",
            "trajectory",
            "pseudotime",
            "轨迹",
            "发育",
            "cell-cell communication",
            "cellphone",
            "配体受体",
            "通讯",
            "subtype",
            "亚型",
            "heterogeneity",
            "异质性",
            "marker",
            "marker gene",
            "marker基因",
            "treatment",
            "therapy",
            "治疗",
            "药物",
        ]

        for pattern in important_patterns:
            if (
                pattern.lower() in research_lower
                or pattern.upper() in research_upper
                or pattern in research_chinese
            ):
                if pattern not in keywords:
                    keywords.append(pattern)

        return keywords[:10]

    def _species_name(self, code: str) -> str:
        """Convert species code to readable name."""
        names = {
            "human": "人类 (Human)",
            "mouse": "小鼠 (Mouse)",
            "rat": "大鼠 (Rat)",
            "both": "混合/异种移植",
        }
        return names.get(code, code)

    def generate_report(self, check_result: dict[str, Any]) -> str:
        """
        Generate human-readable report from check result.

        Args:
            check_result: Result from check() method.

        Returns:
            Formatted report string.
        """
        lines = []

        if check_result["consistent"]:
            lines.append("✓ 数据与背景描述基本一致")
        else:
            lines.append("✗ 发现数据与背景描述不一致的问题:")

        for issue in check_result["issues"]:
            lines.append(f"  - 问题: {issue}")

        for warning in check_result["warnings"]:
            lines.append(f"  - 警告: {warning}")

        if check_result["suggestions"]:
            lines.append("\n建议:")
            for i, suggestion in enumerate(check_result["suggestions"], 1):
                lines.append(f"  {i}. {suggestion}")

        return "\n".join(lines)
