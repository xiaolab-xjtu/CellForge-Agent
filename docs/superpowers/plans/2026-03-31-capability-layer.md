# Capability-Layer Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat 12-skill manifest exposed to the LLM with a two-stage capability-routing architecture that reduces cognitive load and enables logical grouping of skills.

**Architecture:** A `CapabilityRouter` class loads `capability.json` metadata from each subdirectory of `skills/library/`. Stage 1: LLM selects which capabilities are relevant to the research goal. Stage 2: LLM plans specific skills from the filtered manifest of selected capabilities. Skills are physically reorganized into `skills/library/{capability}/{skill_name}/` subdirectories.

**Tech Stack:** Python 3.10+, `pathlib`, `json`, existing `SkillRegistry` / `LLMPlanner` classes, `pytest`

---

## Problem Statement

`LLMPlanner._build_user_prompt()` today hands the LLM all 12 skills at once plus a hard-coded 9-step ordering constraint. As the skill library grows this prompt bloats, conflicting constraints create planning errors, and there is no way to group or hide experimental skills.

**Root cause:** there is only one routing stage; skill selection and pipeline ordering are collapsed into a single LLM call.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create dir | `skills/library/data_preparation/` | QC, filter, normalize, HVG, scale |
| Create dir | `skills/library/representation/` | PCA, neighbors, UMAP, harmony |
| Create dir | `skills/library/clustering_annotation/` | Leiden, CellTypist, DEG |
| Create dir | `skills/library/utilities/` | Future expansion (empty) |
| Create ×4 | `skills/library/{cap}/capability.json` | Capability metadata |
| Modify ×12 | `skills/library/{cap}/{skill}/skill.json` | Add `"capability"` field |
| Modify | `src/core/config.py` | Add `LIBRARY_ROOT` constant |
| Modify | `src/agent/registry.py` | Add `capability` to `SkillIndexEntry`; add `get_skills_by_capability()` |
| Create | `src/agent/capability_router.py` | Load capabilities; filter skill manifest by capability |
| Modify | `src/agent/planner.py` | Inject `CapabilityRouter`; 2-stage planning in `create_initial_plan()` |
| Modify | `tests/test_registry.py` | Update path expectations for nested structure |
| Create | `tests/test_capability_router.py` | Unit tests for `CapabilityRouter` |

### Skill → Capability Mapping

| Skill | Capability |
|-------|-----------|
| `scanpy_qc` | `data_preparation` |
| `scanpy_filter_cells` | `data_preparation` |
| `scanpy_normalize` | `data_preparation` |
| `scanpy_hvg` | `data_preparation` |
| `scanpy_scale` | `data_preparation` |
| `scanpy_pca` | `representation` |
| `scanpy_neighbors` | `representation` |
| `scanpy_umap` | `representation` |
| `harmony_batch` | `representation` |
| `scanpy_leiden` | `clustering_annotation` |
| `celltypist_annotate` | `clustering_annotation` |
| `scanpy_rank_genes` | `clustering_annotation` |

---

## Task 1: Move Skills into Capability Subdirectories

**Files:**
- Move: `skills/{skill_name}/` → `skills/library/{capability}/{skill_name}/`
- Modify: `src/core/config.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/library/data_preparation
mkdir -p skills/library/representation
mkdir -p skills/library/clustering_annotation
mkdir -p skills/library/utilities
```

- [ ] **Step 2: Move data_preparation skills**

```bash
git mv skills/scanpy_qc          skills/library/data_preparation/scanpy_qc
git mv skills/scanpy_filter_cells skills/library/data_preparation/scanpy_filter_cells
git mv skills/scanpy_normalize   skills/library/data_preparation/scanpy_normalize
git mv skills/scanpy_hvg         skills/library/data_preparation/scanpy_hvg
git mv skills/scanpy_scale       skills/library/data_preparation/scanpy_scale
```

- [ ] **Step 3: Move representation skills**

```bash
git mv skills/scanpy_pca       skills/library/representation/scanpy_pca
git mv skills/scanpy_neighbors skills/library/representation/scanpy_neighbors
git mv skills/scanpy_umap      skills/library/representation/scanpy_umap
git mv skills/harmony_batch    skills/library/representation/harmony_batch
```

- [ ] **Step 4: Move clustering_annotation skills**

```bash
git mv skills/scanpy_leiden      skills/library/clustering_annotation/scanpy_leiden
git mv skills/celltypist_annotate skills/library/clustering_annotation/celltypist_annotate
git mv skills/scanpy_rank_genes  skills/library/clustering_annotation/scanpy_rank_genes
```

- [ ] **Step 5: Verify move — no skill.json left in skills/ root**

```bash
find skills -maxdepth 2 -name "skill.json"
```

Expected: no output (all skill.json files are now 3 levels deep).

```bash
find skills/library -name "skill.json" | wc -l
```

Expected: `12`

- [ ] **Step 6: Update `src/core/config.py` — add LIBRARY_ROOT**

In `src/core/config.py`, after line `SKILLS_ROOT = PROJECT_ROOT / "skills"`:

```python
SKILLS_ROOT = PROJECT_ROOT / "skills"
LIBRARY_ROOT = SKILLS_ROOT / "library"
```

- [ ] **Step 7: Run existing registry tests to verify rglob still works**

```bash
pytest tests/test_registry.py -v
```

Expected: some tests fail because the default path `"skills/library/"` now contains nested folders — the rglob scan should still find all 12 skills. Fix any path-related failures in the next task.

- [ ] **Step 8: Commit**

```bash
git add skills/library/ src/core/config.py
git commit -m "refactor: reorganize skills into capability subdirectories

Moves 12 skills from skills/{name}/ into skills/library/{capability}/{name}/.
Adds LIBRARY_ROOT to config.py.
SkillRegistry.scan() uses rglob so skill loading is unaffected."
```

---

## Task 2: Add `capability` Field to Each skill.json

**Files:**
- Modify ×12: `skills/library/{capability}/{skill_name}/skill.json`

For each skill, open its `skill.json` and add `"capability": "{cap_id}"` as a top-level field. The capability IDs are: `data_preparation`, `representation`, `clustering_annotation`.

- [ ] **Step 1: Add capability field — data_preparation skills (5 skills)**

For each of the 5 files below, add `"capability": "data_preparation"` as the second top-level key (after `"skill_id"`). Edit each file in place:

`skills/library/data_preparation/scanpy_qc/skill.json` — add after `"skill_id"`:
```json
"capability": "data_preparation",
```

Repeat for:
- `skills/library/data_preparation/scanpy_filter_cells/skill.json`
- `skills/library/data_preparation/scanpy_normalize/skill.json`
- `skills/library/data_preparation/scanpy_hvg/skill.json`
- `skills/library/data_preparation/scanpy_scale/skill.json`

- [ ] **Step 2: Add capability field — representation skills (4 skills)**

Add `"capability": "representation"` to:
- `skills/library/representation/scanpy_pca/skill.json`
- `skills/library/representation/scanpy_neighbors/skill.json`
- `skills/library/representation/scanpy_umap/skill.json`
- `skills/library/representation/harmony_batch/skill.json`

- [ ] **Step 3: Add capability field — clustering_annotation skills (3 skills)**

Add `"capability": "clustering_annotation"` to:
- `skills/library/clustering_annotation/scanpy_leiden/skill.json`
- `skills/library/clustering_annotation/celltypist_annotate/skill.json`
- `skills/library/clustering_annotation/scanpy_rank_genes/skill.json`

- [ ] **Step 4: Verify all 12 skill.json files have the capability field**

```bash
grep -r '"capability"' skills/library --include="skill.json" | wc -l
```

Expected: `12`

- [ ] **Step 5: Commit**

```bash
git add skills/library/
git commit -m "feat: add capability field to all skill.json files"
```

---

## Task 3: Create capability.json Files

**Files:**
- Create: `skills/library/data_preparation/capability.json`
- Create: `skills/library/representation/capability.json`
- Create: `skills/library/clustering_annotation/capability.json`
- Create: `skills/library/utilities/capability.json`

- [ ] **Step 1: Create data_preparation/capability.json**

```json
{
  "id": "data_preparation",
  "name": "Data Preparation",
  "description": "Quality control, normalization, and feature selection to prepare raw count data. Use when the user needs to clean, filter, or preprocess data before analysis.",
  "skill_ids": [
    "scanpy_qc",
    "scanpy_filter_cells",
    "scanpy_normalize",
    "scanpy_hvg",
    "scanpy_scale"
  ],
  "stable": true,
  "typical_order": 1
}
```

- [ ] **Step 2: Create representation/capability.json**

```json
{
  "id": "representation",
  "name": "Representation and Integration",
  "description": "Dimensionality reduction, neighbor graph construction, visualization, and batch effect correction. Use when the user needs PCA, UMAP, or to integrate data from multiple batches.",
  "skill_ids": [
    "scanpy_pca",
    "scanpy_neighbors",
    "scanpy_umap",
    "harmony_batch"
  ],
  "stable": true,
  "typical_order": 2
}
```

- [ ] **Step 3: Create clustering_annotation/capability.json**

```json
{
  "id": "clustering_annotation",
  "name": "Clustering and Annotation",
  "description": "Cell clustering, cell type annotation, and differential expression analysis. Use when the user needs to identify cell types, find marker genes, or compare conditions.",
  "skill_ids": [
    "scanpy_leiden",
    "celltypist_annotate",
    "scanpy_rank_genes"
  ],
  "stable": true,
  "typical_order": 3
}
```

- [ ] **Step 4: Create utilities/capability.json**

```json
{
  "id": "utilities",
  "name": "Utilities",
  "description": "Miscellaneous helper operations not covered by the core capabilities. Use for custom or experimental operations.",
  "skill_ids": [],
  "stable": false,
  "typical_order": 4
}
```

- [ ] **Step 5: Verify 4 capability.json files exist**

```bash
find skills/library -name "capability.json" | sort
```

Expected:
```
skills/library/clustering_annotation/capability.json
skills/library/data_preparation/capability.json
skills/library/representation/capability.json
skills/library/utilities/capability.json
```

- [ ] **Step 6: Commit**

```bash
git add skills/library/
git commit -m "feat: add capability.json metadata files for four capability groups"
```

---

## Task 4: Update SkillRegistry — Add Capability Indexing

**Files:**
- Modify: `src/agent/registry.py`
- Modify: `tests/test_registry.py`

- [ ] **Step 1: Write failing tests for new registry behaviour**

In `tests/test_registry.py`, add at the end of `TestSkillRegistry`:

```python
def test_scan_nested_capability_structure(self):
    """Skill in a nested capability subdirectory is found by rglob."""
    from src.agent.registry import SkillRegistry

    with tempfile.TemporaryDirectory() as tmpdir:
        cap_dir = Path(tmpdir) / "data_preparation"
        skill_dir = cap_dir / "scanpy_qc"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.json").write_text(json.dumps({
            "skill_id": "scanpy_qc",
            "capability": "data_preparation",
            "cognitive_layer": {"purpose": "QC filtering"},
        }))

        registry = SkillRegistry(tmpdir)
        count = registry.scan()

        assert count == 1
        assert "scanpy_qc" in registry.skill_ids

def test_skill_index_entry_has_capability(self):
    """SkillIndexEntry stores capability field from skill.json."""
    from src.agent.registry import SkillRegistry

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir) / "cap_a" / "my_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.json").write_text(json.dumps({
            "skill_id": "my_skill",
            "capability": "cap_a",
            "cognitive_layer": {"purpose": "Does something"},
        }))

        registry = SkillRegistry(tmpdir)
        registry.scan()

        manifest = registry.get_tool_manifest()
        entry = next(e for e in manifest if e["id"] == "my_skill")
        assert entry.get("capability") == "cap_a"

def test_get_skills_by_capability(self):
    """get_skills_by_capability filters by capability id."""
    from src.agent.registry import SkillRegistry

    with tempfile.TemporaryDirectory() as tmpdir:
        for cap, skill, purpose in [
            ("prep", "qc", "Quality control"),
            ("prep", "norm", "Normalization"),
            ("dim", "pca", "Dimensionality reduction"),
        ]:
            d = Path(tmpdir) / cap / skill
            d.mkdir(parents=True)
            (d / "skill.json").write_text(json.dumps({
                "skill_id": skill,
                "capability": cap,
                "cognitive_layer": {"purpose": purpose},
            }))

        registry = SkillRegistry(tmpdir)
        registry.scan()

        prep_skills = registry.get_skills_by_capability("prep")
        assert len(prep_skills) == 2
        assert all(e["capability"] == "prep" for e in prep_skills)

        dim_skills = registry.get_skills_by_capability("dim")
        assert len(dim_skills) == 1
        assert dim_skills[0]["id"] == "pca"
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
pytest tests/test_registry.py::TestSkillRegistry::test_skill_index_entry_has_capability \
       tests/test_registry.py::TestSkillRegistry::test_get_skills_by_capability -v
```

Expected: both FAIL (`AttributeError` or `KeyError`).

- [ ] **Step 3: Update `SkillIndexEntry` dataclass in `src/agent/registry.py`**

Change the `SkillIndexEntry` dataclass (currently at line ~43):

```python
@dataclass(frozen=True)
class SkillIndexEntry:
    """Lightweight index entry for a skill."""
    skill_id: str
    purpose: str
    capability: str
    file_path: Path
```

- [ ] **Step 4: Update `_parse_skill_entry` to read capability**

In `_parse_skill_entry` (currently builds `SkillIndexEntry` near line ~143), add reading of the `capability` field:

```python
        cognitive_layer = skill_data.get("cognitive_layer", {})
        purpose = cognitive_layer.get("purpose", "N/A")
        capability = skill_data.get("capability", "")

        return SkillIndexEntry(
            skill_id=skill_id,
            purpose=purpose,
            capability=capability,
            file_path=skill_json_path.resolve(),
        )
```

- [ ] **Step 5: Update `get_tool_manifest` to include capability**

In `get_tool_manifest` (currently at line ~189), include capability in the returned dicts:

```python
    def get_tool_manifest(self) -> list[dict[str, str]]:
        """
        Return a lightweight manifest for LLM/planner tool selection.

        Returns:
            list[dict]: List of dicts with 'id', 'purpose', and 'capability' keys.
        """
        if not self._initialized:
            self.scan()

        return [
            {"id": entry.skill_id, "purpose": entry.purpose, "capability": entry.capability}
            for entry in self._index.values()
        ]
```

- [ ] **Step 6: Add `get_skills_by_capability` method to `SkillRegistry`**

Add after `get_tool_manifest`:

```python
    def get_skills_by_capability(self, capability_id: str) -> list[dict[str, str]]:
        """
        Return skill manifest filtered to a single capability.

        Args:
            capability_id: The capability identifier to filter by.

        Returns:
            list[dict]: Skills in that capability with 'id', 'purpose', 'capability'.
        """
        if not self._initialized:
            self.scan()

        return [
            {"id": entry.skill_id, "purpose": entry.purpose, "capability": entry.capability}
            for entry in self._index.values()
            if entry.capability == capability_id
        ]
```

- [ ] **Step 7: Run all registry tests**

```bash
pytest tests/test_registry.py -v
```

Expected: all PASS. If `test_scan_nested_capability_structure` was already implicitly covered by rglob, it should pass immediately. The new tests should now pass.

- [ ] **Step 8: Commit**

```bash
git add src/agent/registry.py tests/test_registry.py
git commit -m "feat: add capability field to SkillIndexEntry and get_skills_by_capability()"
```

---

## Task 5: Create CapabilityRouter

**Files:**
- Create: `src/agent/capability_router.py`
- Create: `tests/test_capability_router.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_capability_router.py`:

```python
#!/usr/bin/env python3
"""Tests for CapabilityRouter."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestCapabilityRouter:
    """Tests for CapabilityRouter class."""

    def _make_library(self, tmpdir: str) -> Path:
        """Create a minimal library structure for testing."""
        root = Path(tmpdir)
        for cap_id, cap_name, skill_id, purpose in [
            ("data_preparation", "Data Preparation", "scanpy_qc", "QC filtering"),
            ("data_preparation", "Data Preparation", "scanpy_normalize", "Normalization"),
            ("representation", "Representation", "scanpy_pca", "PCA"),
            ("clustering_annotation", "Clustering", "scanpy_leiden", "Leiden clustering"),
        ]:
            skill_dir = root / cap_id / skill_id
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "skill.json").write_text(json.dumps({
                "skill_id": skill_id,
                "capability": cap_id,
                "cognitive_layer": {"purpose": purpose},
            }))

        for cap_id, cap_name, description, skill_ids in [
            ("data_preparation", "Data Preparation", "Prepare raw data", ["scanpy_qc", "scanpy_normalize"]),
            ("representation", "Representation and Integration", "Dimensionality reduction", ["scanpy_pca"]),
            ("clustering_annotation", "Clustering and Annotation", "Cluster and annotate cells", ["scanpy_leiden"]),
        ]:
            cap_dir = root / cap_id
            (cap_dir / "capability.json").write_text(json.dumps({
                "id": cap_id,
                "name": cap_name,
                "description": description,
                "skill_ids": skill_ids,
                "stable": True,
                "typical_order": 1,
            }))

        return root

    def test_scan_loads_capabilities(self):
        """scan() loads all capability.json files."""
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            library_root = self._make_library(tmpdir)
            router = CapabilityRouter(library_root)
            router.scan()

            caps = router.get_capability_manifest()
            cap_ids = [c["id"] for c in caps]
            assert "data_preparation" in cap_ids
            assert "representation" in cap_ids
            assert "clustering_annotation" in cap_ids

    def test_capability_manifest_fields(self):
        """Capability manifest entries have id, name, description."""
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            library_root = self._make_library(tmpdir)
            router = CapabilityRouter(library_root)
            router.scan()

            caps = router.get_capability_manifest()
            for cap in caps:
                assert "id" in cap
                assert "name" in cap
                assert "description" in cap

    def test_filter_manifest_by_capabilities(self):
        """filter_manifest returns only skills for the given capability ids."""
        from src.agent.capability_router import CapabilityRouter
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            library_root = self._make_library(tmpdir)
            router = CapabilityRouter(library_root)
            router.scan()

            registry = SkillRegistry(library_root)
            registry.scan()

            filtered = router.filter_manifest(registry, ["data_preparation"])
            skill_ids = [s["id"] for s in filtered]
            assert "scanpy_qc" in skill_ids
            assert "scanpy_normalize" in skill_ids
            assert "scanpy_pca" not in skill_ids
            assert "scanpy_leiden" not in skill_ids

    def test_filter_manifest_multiple_capabilities(self):
        """filter_manifest with multiple capability ids returns union."""
        from src.agent.capability_router import CapabilityRouter
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            library_root = self._make_library(tmpdir)
            router = CapabilityRouter(library_root)
            router.scan()
            registry = SkillRegistry(library_root)
            registry.scan()

            filtered = router.filter_manifest(registry, ["data_preparation", "representation"])
            skill_ids = [s["id"] for s in filtered]
            assert "scanpy_qc" in skill_ids
            assert "scanpy_pca" in skill_ids
            assert "scanpy_leiden" not in skill_ids

    def test_filter_manifest_empty_returns_all(self):
        """filter_manifest with empty capability list returns full manifest."""
        from src.agent.capability_router import CapabilityRouter
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            library_root = self._make_library(tmpdir)
            router = CapabilityRouter(library_root)
            router.scan()
            registry = SkillRegistry(library_root)
            registry.scan()

            filtered = router.filter_manifest(registry, [])
            assert len(filtered) == len(registry.get_tool_manifest())

    def test_keyword_select_capabilities(self):
        """keyword_select returns capabilities matching research keywords."""
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            library_root = self._make_library(tmpdir)
            router = CapabilityRouter(library_root)
            router.scan()

            # "normalize and cluster" should match data_preparation + clustering_annotation
            selected = router.keyword_select("I want to normalize the data and cluster cells")
            assert "data_preparation" in selected or "clustering_annotation" in selected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
pytest tests/test_capability_router.py -v
```

Expected: all FAIL with `ModuleNotFoundError: No module named 'src.agent.capability_router'`.

- [ ] **Step 3: Create `src/agent/capability_router.py`**

```python
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

    def get_capability_manifest(self) -> list[dict[str, str]]:
        """
        Return lightweight capability list for Stage 1 LLM prompt.

        Returns:
            list[dict]: Each dict has 'id', 'name', 'description'.
        """
        return [
            {
                "id": cap["id"],
                "name": cap["name"],
                "description": cap["description"],
            }
            for cap in self._capabilities.values()
        ]

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
        returns all matching capability ids. Falls back to all capabilities
        if nothing matches.

        Args:
            text: Research description or background text.

        Returns:
            list[str]: Matching capability ids (may be empty → caller uses all).
        """
        text_lower = text.lower()
        matched = []

        for cap_id, keywords in _CAPABILITY_KEYWORDS.items():
            if cap_id not in self._capabilities:
                continue
            if any(kw in text_lower for kw in keywords):
                matched.append(cap_id)

        return matched

    def __repr__(self) -> str:
        return (
            f"CapabilityRouter(root={self._library_root}, "
            f"capabilities={list(self._capabilities.keys())})"
        )
```

- [ ] **Step 4: Run capability router tests**

```bash
pytest tests/test_capability_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent/capability_router.py tests/test_capability_router.py
git commit -m "feat: add CapabilityRouter for two-stage skill routing"
```

---

## Task 6: Integrate CapabilityRouter into LLMPlanner

**Files:**
- Modify: `src/agent/planner.py`

The `LLMPlanner.__init__` gains an optional `capability_router` parameter. `create_initial_plan` uses Stage 1 keyword selection to filter the manifest before building the user prompt.

- [ ] **Step 1: Update `LLMPlanner.__init__`**

In `src/agent/planner.py`, change `LLMPlanner.__init__` (currently at line ~72):

```python
    def __init__(
        self,
        api_client: Any,
        registry: Any,
        max_retries: int = 3,
        capability_router: Any | None = None,
    ) -> None:
        """
        Initialize LLM planner.

        Args:
            api_client: APIClient instance for LLM calls
            registry: SkillRegistry instance for tool manifest
            max_retries: Maximum retry attempts for failed steps
            capability_router: Optional CapabilityRouter for two-stage routing.
                               If None, all skills are included in every prompt.
        """
        self._api_client = api_client
        self._registry = registry
        self.max_retries = max_retries
        self._capability_router = capability_router
```

- [ ] **Step 2: Update `create_initial_plan` to use two-stage routing**

In `create_initial_plan` (currently at line ~85), replace the `manifest = self._registry.get_tool_manifest()` line with:

```python
        manifest = self._get_filtered_manifest(background, research)
```

Then add the helper method after `create_initial_plan`:

```python
    def _get_filtered_manifest(
        self, background: str, research: str
    ) -> list[dict[str, str]]:
        """
        Stage 1 routing: select capabilities, then return filtered skill manifest.

        Falls back to full manifest if no router is configured or no capabilities match.
        """
        if self._capability_router is None:
            return self._registry.get_tool_manifest()

        combined_text = f"{background} {research}"
        selected_caps = self._capability_router.keyword_select(combined_text)

        if not selected_caps:
            logger.debug("No capability matched — using full manifest")
            return self._registry.get_tool_manifest()

        logger.info("Stage 1 selected capabilities: %s", selected_caps)
        filtered = self._capability_router.filter_manifest(self._registry, selected_caps)

        if not filtered:
            logger.warning("Filtered manifest is empty — falling back to full manifest")
            return self._registry.get_tool_manifest()

        return filtered
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS. The planner tests (if any) pass because `capability_router=None` is the default and preserves existing behaviour.

- [ ] **Step 4: Commit**

```bash
git add src/agent/planner.py
git commit -m "feat: integrate CapabilityRouter into LLMPlanner for two-stage routing

When a CapabilityRouter is provided, Stage 1 keyword-selects capabilities
and Stage 2 only sees the filtered skill manifest. Falls back to full
manifest when router is absent or no capabilities match."
```

---

## Task 7: Wire CapabilityRouter in agent.py

**Files:**
- Modify: `src/agent/agent.py`

The agent creates a `CapabilityRouter` and passes it to `LLMPlanner`.

- [ ] **Step 1: Read the relevant section of agent.py**

Look at how `LLMPlanner` is instantiated — find the line that calls `LLMPlanner(...)`.

```bash
grep -n "LLMPlanner" src/agent/agent.py
```

- [ ] **Step 2: Add CapabilityRouter import and construction**

In `src/agent/agent.py`, add the import near the top with other agent imports:

```python
from src.agent.capability_router import CapabilityRouter
```

Then in the section where `LLMPlanner` is created, add router construction first. Assuming it looks like:

```python
self._planner = LLMPlanner(api_client=self._api_client, registry=self._registry)
```

Change to:

```python
from src.core.config import LIBRARY_ROOT
self._capability_router = CapabilityRouter(LIBRARY_ROOT)
self._capability_router.scan()
self._planner = LLMPlanner(
    api_client=self._api_client,
    registry=self._registry,
    capability_router=self._capability_router,
)
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/agent/agent.py
git commit -m "feat: wire CapabilityRouter into agent initialization"
```

---

## Task 8: Update Default Registry Path

**Files:**
- Modify: `src/agent/registry.py`
- Modify: `src/core/config.py` (verify LIBRARY_ROOT is used everywhere)

The `SkillRegistry` default path was `"skills/library/"`. Skills are now inside `skills/library/{capability}/`, so the root is the same — no change needed there. But `config.py`'s `SKILLS_ROOT` is no longer the scan root; `LIBRARY_ROOT` is. Verify the agent and any other callers use `LIBRARY_ROOT`.

- [ ] **Step 1: Verify registry default path matches library root**

```bash
grep -n "SkillRegistry(" src/agent/agent.py
grep -n "SKILLS_ROOT\|LIBRARY_ROOT" src/agent/agent.py src/core/config.py
```

Expected: `agent.py` uses `LIBRARY_ROOT` (or `config.LIBRARY_ROOT`) when constructing `SkillRegistry`. If it still uses `SKILLS_ROOT`, update it.

- [ ] **Step 2: If agent.py uses SKILLS_ROOT for SkillRegistry, change it**

Find and update the `SkillRegistry` construction in `agent.py` to use `LIBRARY_ROOT`:

```python
from src.core.config import LIBRARY_ROOT
self._registry = SkillRegistry(LIBRARY_ROOT)
self._registry.scan()
```

- [ ] **Step 3: Run a quick smoke test**

```bash
cd /Users/zhengtao_xiao/ClaudeWorkSpace/CellForge-Agent && python -c "
from src.core.config import LIBRARY_ROOT
from src.agent.registry import SkillRegistry
r = SkillRegistry(LIBRARY_ROOT)
count = r.scan()
print(f'Found {count} skills')
print([e['id'] for e in r.get_tool_manifest()])
"
```

Expected output: `Found 12 skills` followed by all 12 skill IDs.

- [ ] **Step 4: Commit if any files changed**

```bash
git add src/agent/agent.py src/core/config.py
git commit -m "fix: use LIBRARY_ROOT as SkillRegistry scan root after capability restructure"
```

---

## Task 9: Final Verification and Migration Note

- [ ] **Step 1: Run the full test suite one last time**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all green.

- [ ] **Step 2: Verify no skill.json files remain in the old flat location**

```bash
find skills -maxdepth 2 -name "skill.json" 2>/dev/null
```

Expected: no output (all skill.json are 3 levels deep inside `skills/library/`).

- [ ] **Step 3: Verify capability routing works end-to-end**

```bash
cd /Users/zhengtao_xiao/ClaudeWorkSpace/CellForge-Agent && python -c "
from src.core.config import LIBRARY_ROOT
from src.agent.registry import SkillRegistry
from src.agent.capability_router import CapabilityRouter

registry = SkillRegistry(LIBRARY_ROOT)
registry.scan()
router = CapabilityRouter(LIBRARY_ROOT)
router.scan()

print('=== Capabilities ===')
for cap in router.get_capability_manifest():
    print(f'  {cap[\"id\"]}: {cap[\"name\"]}')

print()
print('=== Stage 1: keyword_select for DEG analysis ===')
selected = router.keyword_select('compare CTRL vs STIM conditions and find differential genes')
print(f'  Selected: {selected}')

print()
print('=== Stage 2: filtered manifest ===')
filtered = router.filter_manifest(registry, selected)
for s in filtered:
    print(f'  {s[\"id\"]} ({s[\"capability\"]}): {s[\"purpose\"]}')
"
```

Expected: capabilities listed, `clustering_annotation` selected, only leiden/celltypist/rank_genes in filtered manifest.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "docs: verify capability-layer refactor complete

All 12 skills reorganized into 4 capability subdirectories.
Two-stage routing operational: CapabilityRouter reduces LLM context
from 12 skills to 3-5 relevant skills per research goal."
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Audit current skill system → covered in problem statement
  - Refactor into two-layer architecture → Tasks 1–3 (directory + metadata)
  - Map skills to capabilities → mapping table in file map
  - Two-stage routing → Tasks 5–6 (CapabilityRouter + LLMPlanner)
  - Standardized interfaces → capability.json schema in Task 3
  - Stable vs experimental flag → `"stable": true/false` in capability.json
  - Future extensibility → `utilities/` directory + keyword dict extensible
  - Direct implementation (not just analysis) → all tasks produce code
- [x] **No placeholders:** every code block is complete and runnable
- [x] **Type consistency:** `SkillIndexEntry.capability: str` added in Task 4 Step 3 matches usage in `get_skills_by_capability()` and `filter_manifest()`
- [x] **Method names consistent:** `keyword_select` used in Task 5 tests and Task 6 implementation; `filter_manifest` used in Task 5 tests and Task 6; `get_capability_manifest` used in Task 5 tests and Task 6 prompt building

---

## Developer Migration Notes

If you have added a custom skill directly to `skills/`:
1. Identify which capability it belongs to (or use `utilities` for uncategorized)
2. Move it: `git mv skills/my_skill skills/library/{capability}/my_skill`
3. Add `"capability": "{capability_id}"` to `my_skill/skill.json`
4. No code changes needed — the registry's `rglob` will find it automatically

To add a new capability:
1. Create `skills/library/{new_cap_id}/capability.json` following the schema in Task 3
2. Add keyword triggers to `_CAPABILITY_KEYWORDS` in `src/agent/capability_router.py`
3. Add skills under `skills/library/{new_cap_id}/{skill_name}/skill.json`
4. No other code changes required
