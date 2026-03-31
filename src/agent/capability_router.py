#!/usr/bin/env python3
"""
CapabilityRouter - Two-stage skill routing for CellForge Agent.

Stage 1: Select which capabilities are needed for a research goal.
Stage 2: Return a filtered skill manifest for selected capabilities.

Usage:
    router = CapabilityRouter(library_root)
    router.scan()

    # Stage 1 (keyword-based)
    cap_ids = router.keyword_select(research_text)

    # Stage 2
    filtered_manifest = router.filter_manifest(registry, cap_ids)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Keywords that suggest each capability. Used for fast keyword-based Stage 1.
_CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    "data_preparation": [
        "qc", "quality", "filter", "normalize", "normalization",
        "hvg", "highly variable", "scale", "preprocess", "raw",
    ],
    "representation": [
        "pca", "umap", "dimension", "embedding", "neighbor",
        "batch", "integration", "harmony", "visuali",
    ],
    "clustering_annotation": [
        "cluster", "leiden", "louvain", "annotation", "cell type",
        "celltypist", "marker", "deg", "differential", "rank gene",
        "stimulat", "condition", "compare", "response",
    ],
    "utilities": [
        "create skill", "new skill", "skill creator", "sc-skill",
    ],
}


class CapabilityRouter:
    """
    Loads capability metadata and provides Stage 1 routing.

    Library structure expected:
        library_root/
            data_preparation/
                capability.json
                scanpy_qc/skill.json
                ...
            representation/
                capability.json
                ...
    """

    def __init__(self, library_root: str | Path) -> None:
        """
        Args:
            library_root: Path to skills/library/ directory.
        """
        self._library_root = Path(library_root)
        self._capabilities: dict[str, dict[str, Any]] = {}

    def scan(self) -> int:
        """
        Load all capability.json files from direct subdirectories.

        Returns:
            int: Number of capabilities loaded.
        """
        self._capabilities.clear()

        if not self._library_root.exists():
            logger.warning("Library root does not exist: %s", self._library_root)
            return 0

        for cap_dir in sorted(self._library_root.iterdir()):
            if not cap_dir.is_dir():
                continue

            cap_json = cap_dir / "capability.json"
            if not cap_json.exists():
                continue

            try:
                with open(cap_json, "r", encoding="utf-8") as f:
                    cap_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Cannot load %s: %s", cap_json, e)
                continue

            cap_id = cap_data.get("id")
            if not cap_id:
                logger.warning("capability.json missing 'id': %s", cap_json)
                continue

            self._capabilities[cap_id] = cap_data
            logger.debug("Loaded capability: %s", cap_id)

        return len(self._capabilities)

    def get_capability_manifest(self) -> list[dict[str, Any]]:
        """
        Return lightweight capability list for Stage 1 LLM prompt.

        Returns:
            list[dict]: Each dict has 'id', 'name', 'description', 'stable', 'typical_order'.
        """
        return sorted(
            [
                {
                    "id": cap["id"],
                    "name": cap["name"],
                    "description": cap["description"],
                    "stable": cap.get("stable", True),
                    "typical_order": cap.get("typical_order", 99),
                }
                for cap in self._capabilities.values()
            ],
            key=lambda c: c["typical_order"],
        )

    def get_capability(self, capability_id: str) -> dict[str, Any] | None:
        """Return full capability metadata by id."""
        return self._capabilities.get(capability_id)

    def filter_manifest(
        self,
        registry: Any,
        capability_ids: list[str],
    ) -> list[dict[str, str]]:
        """
        Return skill manifest filtered to the given capability ids.

        If capability_ids is empty, returns the full manifest (safe fallback).

        Args:
            registry: SkillRegistry instance.
            capability_ids: List of capability ids selected in Stage 1.

        Returns:
            list[dict]: Filtered skill manifest entries (id, purpose, capability).
        """
        if not capability_ids:
            return registry.get_tool_manifest()

        cap_set = set(capability_ids)
        return [
            entry for entry in registry.get_tool_manifest()
            if entry.get("capability") in cap_set
        ]

    def keyword_select(self, text: str) -> list[str]:
        """
        Fast keyword-based Stage 1 selection (no LLM call needed).

        Scans text for keywords associated with each capability and
        returns all matching capability ids. Returns empty list if
        nothing matches (caller should fall back to full manifest).

        Args:
            text: Research description or background text.

        Returns:
            list[str]: Matching capability ids sorted by typical_order.
        """
        text_lower = text.lower()
        matched = []

        for cap_id, keywords in _CAPABILITY_KEYWORDS.items():
            if cap_id not in self._capabilities:
                continue
            if any(kw in text_lower for kw in keywords):
                matched.append(cap_id)

        # Sort by typical_order for deterministic output
        order = {cap_id: self._capabilities[cap_id].get("typical_order", 99) for cap_id in matched}
        matched.sort(key=lambda c: order.get(c, 99))
        return matched

    def __repr__(self) -> str:
        return (
            f"CapabilityRouter(root={self._library_root}, "
            f"capabilities={list(self._capabilities.keys())})"
        )
