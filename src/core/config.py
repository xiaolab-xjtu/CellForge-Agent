#!/usr/bin/env python3
"""
CellForge Agent Configuration

Path, API, analysis thresholds, and validation settings.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

SKILLS_ROOT = PROJECT_ROOT / "skills"
LIBRARY_ROOT = SKILLS_ROOT / "library"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

API_CONFIG = {
    "text_model": os.getenv("MINIMAX_TEXT_MODEL", "MiniMax-M2.7-highspeed"),
    "text_api_url": os.getenv("MINIMAX_TEXT_API_URL", "https://api.minimaxi.com/v1"),
    "vision_model": os.getenv("MINIMAX_VISION_MODEL", "MiniMax-M2.7-highspeed"),
    "vision_api_url": os.getenv("MINIMAX_VISION_API_URL", "https://api.minimaxi.com/v1"),
    "api_key": os.getenv("MINIMAX_API_KEY", ""),
}

AGENT_CONFIG = {
    "max_retries": 3,
    "max_step_retries": 5,
    "numeric_validation": True,
    "visual_validation": True,
    "deep_research_enabled": True,
    "deep_research_rounds": 1,
    "python_first": True,
}

ANALYSIS_CONFIG = {
    "qc": {
        "min_genes": 200,
        "min_cells": 3,
        "max_mito_pct": 20,
    },
    "normalization": {
        "target_sum": 1e4,
    },
    "hvg": {
        "n_top_genes": 2000,
        "flavor": "seurat_v3",
    },
    "pca": {
        "n_comps": 50,
    },
    "clustering": {
        "leiden_resolutions": [0.2, 0.5, 0.8],
    },
    "umap": {
        "n_neighbors": 15,
        "min_dist": 0.5,
    },
    "batch_correction": {
        "key": "batch",
    },
}

OUTPUT_CONFIG = {
    "figure_dpi": 150,
    "figure_width": 10,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

STEP_NAMES = [
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
