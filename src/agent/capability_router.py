#!/usr/bin/env python3
"""
CapabilityRouter - Two-stage skill routing for CellForge Agent.

Stage 1: Select which capabilities are needed for a research goal.
  - Keyword + phrase matching with confidence scoring
  - Handles multi-capability queries
  - Returns empty list on no match → caller falls back to full manifest

Stage 2: filter_manifest() returns only skills from selected capabilities.

Usage:
    router = CapabilityRouter(library_root)
    router.scan()

    # Stage 1 with scores
    result = router.select(research_text)          # → SelectionResult
    cap_ids = result.capability_ids                # sorted by confidence desc
    print(result.scores)                           # {"data_preparation": 0.8, ...}

    # Simple list API (backward-compatible)
    cap_ids = router.keyword_select(research_text)

    # Stage 2
    filtered = router.filter_manifest(registry, cap_ids)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required fields for capability.json — used in validate_capability_schema()
# ---------------------------------------------------------------------------
_REQUIRED_CAPABILITY_FIELDS: set[str] = {"id", "name", "description", "skill_ids"}

# ---------------------------------------------------------------------------
# Matching rules per capability.
#
# Each entry is a dict with:
#   "phrases"    : list[str]  — exact phrase matches (higher weight per hit)
#   "keywords"   : list[str]  — single-token/prefix matches (lower weight)
#   "aliases"    : list[str]  — alternative names / synonyms for the cap itself
#   "weight"     : float      — base weight per keyword hit (default 1.0)
#   "phrase_weight": float    — weight per phrase hit (default 2.0)
#
# To add or tune rules for a capability: edit this dict only.
# No other code changes are needed.
# ---------------------------------------------------------------------------
_CAPABILITY_RULES: dict[str, dict[str, Any]] = {
    "data_preparation": {
        "aliases": ["preprocessing", "prep", "data prep", "data cleaning"],
        "phrases": [
            "quality control", "highly variable genes", "highly variable",
            "log normalize", "log1p normalize", "size factor", "count normalization",
            "doublet removal", "ambient rna", "cell filtering", "gene filtering",
            "feature selection",
        ],
        "keywords": [
            "qc", "filter", "normalize", "normalization", "hvg",
            "scale", "preprocess", "raw count", "log1p",
        ],
        "weight": 1.0,
        "phrase_weight": 2.5,
    },
    "representation": {
        "aliases": ["dimensionality reduction", "dim red", "embedding", "visualization"],
        "phrases": [
            "principal component", "principal component analysis",
            "neighbor graph", "k nearest neighbor", "knn graph",
            "batch correction", "batch integration", "batch effect",
            "data integration", "2d visualization", "low dimensional",
        ],
        "keywords": [
            "pca", "umap", "tsne", "neighbor", "embedding",
            "batch", "harmony", "integration", "dimension", "visuali",
            "projection", "diffmap",
        ],
        "weight": 1.0,
        "phrase_weight": 2.5,
    },
    "clustering_annotation": {
        "aliases": [
            "cell type identification", "cluster analysis",
            "cell annotation", "cell typing", "cell labeling",
        ],
        "phrases": [
            "differential expression", "differentially expressed",
            "cell type annotation", "cell type identification",
            "marker gene", "rank genes", "leiden clustering",
            "louvain clustering", "community detection",
            "stimulation response", "treatment vs control",
            "condition comparison", "ifn response",
        ],
        "keywords": [
            "cluster", "leiden", "louvain", "annotation", "annotate",
            "celltypist", "deg", "differential", "marker", "stimulat",
            "condition", "compare", "response", "cell type", "subtype",
        ],
        "weight": 1.0,
        "phrase_weight": 2.5,
    },
    "utilities": {
        "aliases": ["developer tools", "skill builder"],
        "phrases": [
            "create skill", "new skill", "build skill", "skill template",
            "skill creator",
        ],
        "keywords": [
            "sc-skill", "skill-creator",
        ],
        "weight": 1.0,
        "phrase_weight": 3.0,  # higher — utilities are rarely triggered
    },
}

# ---------------------------------------------------------------------------
# Negation guards: if these tokens appear near a keyword we reduce confidence.
# Simple "not X" / "without X" patterns.
# ---------------------------------------------------------------------------
_NEGATION_PREFIXES = re.compile(
    r"\b(no|not|without|skip|omit|exclude|avoid)\b.{0,20}$",
    re.IGNORECASE,
)


@dataclass
class SelectionResult:
    """Result of Stage 1 capability selection."""

    capability_ids: list[str]
    """Capability ids above the confidence threshold, sorted by score desc."""

    scores: dict[str, float]
    """Raw confidence score per capability id (0.0 – 1.0)."""

    fallback: bool
    """True when no capability matched confidently → caller should use full manifest."""

    def __bool__(self) -> bool:
        return bool(self.capability_ids)


class CapabilityRouter:
    """
    Loads capability metadata and provides Stage 1 routing.

    Library structure expected::

        library_root/
            data_preparation/
                capability.json
                scanpy_qc/skill.json
                ...
            representation/
                capability.json
                ...

    Scoring algorithm
    -----------------
    For each capability:
    1. Count phrase hits × phrase_weight
    2. Count keyword hits × weight  (deduplicated — same token counted once)
    3. Deduct 50% of score for each negation guard triggered
    4. Normalize to [0, 1] using a soft cap of 10 points per capability
    5. A capability is selected when score ≥ threshold (default 0.15)

    The threshold is intentionally low to prefer recall over precision for
    the routing step — the LLM in Stage 2 will make the final skill selection.
    """

    CONFIDENCE_THRESHOLD = 0.09
    """Minimum normalised score for a capability to be selected.

    With weight=1.0 and soft-cap at 10, a single keyword hit scores 0.10,
    which exceeds this threshold. Set higher to require stronger evidence.
    """

    def __init__(self, library_root: str | Path) -> None:
        self._library_root = Path(library_root)
        self._capabilities: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def scan(self) -> int:
        """Load all capability.json files from direct subdirectories."""
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

            issues = validate_capability_schema(cap_data)
            if issues:
                logger.warning("capability.json schema issues in %s: %s", cap_json, issues)

            self._capabilities[cap_id] = cap_data
            logger.debug("Loaded capability: %s", cap_id)

        return len(self._capabilities)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_capability_manifest(self) -> list[dict[str, Any]]:
        """
        Return lightweight capability list sorted by typical_order.

        Returns:
            list[dict]: Each dict has id, name, description, stable, typical_order.
        """
        return sorted(
            [
                {
                    "id": cap["id"],
                    "name": cap["name"],
                    "description": cap["description"],
                    "stable": cap.get("stable", True),
                    "typical_order": cap.get("typical_order", 99),
                    "skill_ids": cap.get("skill_ids", []),
                }
                for cap in self._capabilities.values()
            ],
            key=lambda c: c["typical_order"],
        )

    def get_capability(self, capability_id: str) -> dict[str, Any] | None:
        """Return full capability metadata by id, or None if not found."""
        return self._capabilities.get(capability_id)

    def filter_manifest(
        self,
        registry: Any,
        capability_ids: list[str],
    ) -> list[dict[str, str]]:
        """
        Return skill manifest filtered to the given capability ids.

        If capability_ids is empty, returns the full manifest (safe fallback).
        """
        if not capability_ids:
            return registry.get_tool_manifest()

        cap_set = set(capability_ids)
        return [
            entry for entry in registry.get_tool_manifest()
            if entry.get("capability") in cap_set
        ]

    def select(
        self,
        text: str,
        threshold: float | None = None,
    ) -> SelectionResult:
        """
        Full Stage 1 selection with confidence scoring.

        Args:
            text: Research description or background text.
            threshold: Override the default CONFIDENCE_THRESHOLD.

        Returns:
            SelectionResult with capability_ids, scores, and fallback flag.
        """
        threshold = threshold if threshold is not None else self.CONFIDENCE_THRESHOLD
        raw_scores = self._score_text(text)

        selected = {
            cap_id: score
            for cap_id, score in raw_scores.items()
            if score >= threshold and cap_id in self._capabilities
        }

        # Sort by score descending, then by typical_order for ties
        def _sort_key(cap_id: str) -> tuple[float, int]:
            return (-selected[cap_id], self._capabilities[cap_id].get("typical_order", 99))

        sorted_ids = sorted(selected.keys(), key=_sort_key)

        fallback = len(sorted_ids) == 0
        if fallback:
            logger.debug("No capability matched confidently for: %.60s…", text)

        return SelectionResult(
            capability_ids=sorted_ids,
            scores=raw_scores,
            fallback=fallback,
        )

    def keyword_select(self, text: str) -> list[str]:
        """
        Backward-compatible simple API — returns list of matching capability ids.

        Wraps select() and returns capability_ids (empty list on no match).
        Caller should fall back to full manifest when empty.
        """
        return self.select(text).capability_ids

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _score_text(self, text: str) -> dict[str, float]:
        """
        Score text against all capability rules.

        Returns:
            dict: capability_id → normalised score in [0, 1].
        """
        text_lower = text.lower()
        scores: dict[str, float] = {}

        for cap_id, rules in _CAPABILITY_RULES.items():
            if cap_id not in self._capabilities:
                continue

            raw = 0.0
            phrase_weight = rules.get("phrase_weight", 2.5)
            kw_weight = rules.get("weight", 1.0)

            # 1. Phrase matches (multi-word, higher weight)
            for phrase in rules.get("phrases", []):
                if phrase in text_lower:
                    if not _is_negated(text_lower, phrase):
                        raw += phrase_weight
                        logger.debug("Phrase hit '%s' for cap '%s'", phrase, cap_id)

            # 2. Alias matches (treat like phrases)
            for alias in rules.get("aliases", []):
                if alias in text_lower:
                    if not _is_negated(text_lower, alias):
                        raw += phrase_weight * 0.8  # slightly lower than exact phrase
                        logger.debug("Alias hit '%s' for cap '%s'", alias, cap_id)

            # 3. Keyword matches (deduped — each keyword counted once)
            seen_kw: set[str] = set()
            for kw in rules.get("keywords", []):
                if kw in seen_kw:
                    continue
                if kw in text_lower:
                    if not _is_negated(text_lower, kw):
                        raw += kw_weight
                        seen_kw.add(kw)
                        logger.debug("Keyword hit '%s' for cap '%s'", kw, cap_id)

            # 4. Normalise: soft cap at 10 points → score in [0, 1]
            scores[cap_id] = min(raw / 10.0, 1.0)

        return scores

    def __repr__(self) -> str:
        return (
            f"CapabilityRouter(root={self._library_root}, "
            f"capabilities={list(self._capabilities.keys())})"
        )


# ---------------------------------------------------------------------------
# Module-level helpers (also useful in tests)
# ---------------------------------------------------------------------------

def validate_capability_schema(cap_data: dict[str, Any]) -> list[str]:
    """
    Validate a capability.json dict against the required schema.

    Args:
        cap_data: Parsed capability.json content.

    Returns:
        List of issue strings (empty = valid).
    """
    issues = []
    for field_name in _REQUIRED_CAPABILITY_FIELDS:
        if field_name not in cap_data:
            issues.append(f"Missing required field: '{field_name}'")

    if "skill_ids" in cap_data and not isinstance(cap_data["skill_ids"], list):
        issues.append("'skill_ids' must be a list")

    if "stable" in cap_data and not isinstance(cap_data["stable"], bool):
        issues.append("'stable' must be a boolean")

    if "typical_order" in cap_data and not isinstance(cap_data["typical_order"], int):
        issues.append("'typical_order' must be an integer")

    return issues


def _is_negated(text: str, token: str) -> bool:
    """
    Return True when token appears to be negated (e.g. "no normalization").

    Checks for negation words within 20 chars before the token occurrence.
    """
    idx = text.find(token)
    if idx == -1:
        return False
    preceding = text[max(0, idx - 30) : idx]
    return bool(_NEGATION_PREFIXES.search(preceding))
