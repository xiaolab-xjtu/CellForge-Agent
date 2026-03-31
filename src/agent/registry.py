#!/usr/bin/env python3
"""
SkillRegistry - Registry and discovery module for CellForge Agent skills.

Manages skills stored in skills/library/, where each skill resides in its own
folder (folder name = tool name) containing skill.json.

Lazy Indexing:
    On init, only skill_id, purpose, and file_path are loaded into memory.
    Full skill.json content is loaded on-demand via get_skill_spec().

Dynamic Discovery:
    refresh() allows rescanning the disk without restarting the Agent.

Usage:
    registry = SkillRegistry("skills/library/")
    registry.scan()  # Initial lazy scan

    # LLM view for planner
    manifest = registry.get_tool_manifest()

    # Get full skill spec on-demand
    skill = registry.get_skill_spec("scanpy_filter_cells")

    # Dynamic registration from sc-skill-creator
    registry.register_skill_folder("/path/to/newly/created/skill_folder")
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillIndexEntry:
    """Lightweight index entry for a skill."""
    skill_id: str
    purpose: str
    capability: str
    file_path: Path


class SkillRegistry:
    """
    Registry for scanning and accessing skills.

    Storage Structure:
        skills/library/
            scanpy_filter_cells/
                skill.json
            scanpy_normalize/
                skill.json
            ...

    The registry uses lazy indexing: only metadata (skill_id, purpose, file_path)
    is loaded into memory during scan. Full skill content is loaded on-demand.
    """

    def __init__(self, skills_root: str | Path = "skills/library/") -> None:
        """
        Initialize registry with skills root folder.

        Args:
            skills_root: Path to the skills library root directory.
                        Defaults to "skills/library/" relative to working directory.
        """
        self._skills_root = Path(skills_root)
        self._index: dict[str, SkillIndexEntry] = {}
        self._initialized = False

    @property
    def skills_root(self) -> Path:
        """Return the skills root path."""
        return self._skills_root

    def scan(self) -> int:
        """
        Perform initial lazy scan of skills_root.

        Recursively scans the root directory and indexes all valid skill folders.
        A valid skill folder must contain skill.json with a skill_id field.

        Returns:
            int: Number of skills indexed.
        """
        self._index.clear()

        if not self._skills_root.exists():
            logger.warning("Skills root does not exist: %s", self._skills_root)
            return 0

        for subfolder in self._skills_root.rglob("*"):
            if not subfolder.is_dir():
                continue

            skill_json_path = subfolder / "skill.json"
            if not skill_json_path.exists():
                continue

            entry = self._parse_skill_entry(skill_json_path)
            if entry is not None:
                self._index[entry.skill_id] = entry
                logger.debug("Indexed skill: %s", entry.skill_id)

        self._initialized = True
        return len(self._index)

    def _parse_skill_entry(self, skill_json_path: Path) -> SkillIndexEntry | None:
        """
        Parse a skill.json file and extract indexable metadata.

        Args:
            skill_json_path: Absolute path to skill.json file.

        Returns:
            SkillIndexEntry if valid skill found, None otherwise.
        """
        try:
            with open(skill_json_path, "r", encoding="utf-8") as f:
                skill_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in %s: %s", skill_json_path, e)
            return None
        except OSError as e:
            logger.warning("Cannot read %s: %s", skill_json_path, e)
            return None

        skill_id = skill_data.get("skill_id")
        if not skill_id:
            logger.warning("skill.json missing skill_id: %s", skill_json_path)
            return None

        cognitive_layer = skill_data.get("cognitive_layer", {})
        purpose = cognitive_layer.get("purpose", "N/A")
        capability = skill_data.get("capability", "")

        return SkillIndexEntry(
            skill_id=skill_id,
            purpose=purpose,
            capability=capability,
            file_path=skill_json_path.resolve(),
        )

    def refresh(self) -> int:
        """
        Refresh the registry by rescanning disk for new or changed skills.

        Unlike scan(), this preserves the registry state and adds/updates
        skills found on disk. Useful when sc-skill-creator generates new skills.

        Returns:
            int: Total number of skills currently indexed.
        """
        return self.scan()

    def get_skill_spec(self, skill_id: str) -> dict[str, Any] | None:
        """
        Load and return the full skill specification on-demand.

        Args:
            skill_id: The unique identifier of the skill.

        Returns:
            dict: The complete skill.json content, or None if not found.
        """
        if not self._initialized:
            self.scan()

        entry = self._index.get(skill_id)
        if entry is None:
            logger.debug("Skill not found: %s", skill_id)
            return None

        try:
            with open(entry.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", entry.file_path, e)
            return None
        except OSError as e:
            logger.error("Cannot read %s: %s", entry.file_path, e)
            return None

    def get_tool_manifest(self) -> list[dict[str, str]]:
        """
        Return a lightweight manifest for LLM/planner tool selection.

        Returns:
            list[dict]: List of dicts with 'id' and 'purpose' keys.
        """
        if not self._initialized:
            self.scan()

        return [
            {"id": entry.skill_id, "purpose": entry.purpose, "capability": entry.capability}
            for entry in self._index.values()
        ]

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

    def register_skill_folder(self, folder_path: str | Path) -> bool:
        """
        Dynamically register a newly created skill folder.

        This method allows sc-skill-creator to inject a newly generated
        skill into the registry without rescanning the entire disk.

        Args:
            folder_path: Path to the skill folder (not the skill.json path).

        Returns:
            bool: True if registered successfully, False otherwise.
        """
        folder = Path(folder_path)

        if not folder.exists():
            logger.error("Skill folder does not exist: %s", folder)
            return False

        if not folder.is_dir():
            logger.error("Path is not a directory: %s", folder)
            return False

        skill_json_path = folder / "skill.json"
        if not skill_json_path.exists():
            logger.error("skill.json not found in: %s", folder)
            return False

        entry = self._parse_skill_entry(skill_json_path)
        if entry is None:
            return False

        self._index[entry.skill_id] = entry
        self._initialized = True
        logger.info("Dynamically registered skill: %s", entry.skill_id)
        return True

    def unregister(self, skill_id: str) -> bool:
        """
        Remove a skill from the registry.

        Args:
            skill_id: The skill identifier to remove.

        Returns:
            bool: True if removed, False if not found.
        """
        if skill_id in self._index:
            del self._index[skill_id]
            logger.info("Unregistered skill: %s", skill_id)
            return True
        return False

    def search(self, query: str) -> list[dict[str, str]]:
        """
        Search skills by keyword in skill_id or purpose.

        Args:
            query: Search term (case-insensitive).

        Returns:
            list[dict]: Matching skills with 'id' and 'purpose'.
        """
        if not self._initialized:
            self.scan()

        query_lower = query.lower()
        return [
            {"id": entry.skill_id, "purpose": entry.purpose}
            for entry in self._index.values()
            if query_lower in entry.skill_id.lower()
            or query_lower in entry.purpose.lower()
        ]

    @property
    def skill_ids(self) -> list[str]:
        """Return list of all registered skill IDs."""
        if not self._initialized:
            self.scan()
        return list(self._index.keys())

    def __len__(self) -> int:
        """Return number of skills in registry."""
        return len(self._index)

    def __repr__(self) -> str:
        return (
            f"SkillRegistry(root={self._skills_root}, "
            f"skills={len(self)}, initialized={self._initialized})"
        )

    def _normalize_name(self, name: str) -> str:
        """Normalize skill name: replace hyphens with underscores and lowercase."""
        return name.replace("-", "_").replace(" ", "_").lower()

    def check_skill_id_consistency(self) -> list[dict[str, Any]]:
        """
        Check if folder names match the skill_id in skill.json.

        Returns:
            list of issues found, each dict contains:
            - folder: actual folder name
            - skill_id: skill_id from skill.json
            - issue: description of the problem
            - fix: suggested fix
        """
        issues = []
        if not self._initialized:
            self.scan()

        for skill_id, entry in self._index.items():
            folder_name = entry.file_path.parent.name
            if self._normalize_name(skill_id) != self._normalize_name(folder_name):
                issues.append({
                    "folder": folder_name,
                    "skill_id": skill_id,
                    "issue": "Folder name does not match skill_id",
                    "fix": f"Rename folder to '{skill_id}' or change skill_id in skill.json"
                })

        return issues

    def fuzzy_match_skill(self, step_name: str) -> str | None:
        """
        Match a step name to an available skill using fuzzy matching.

        Args:
            step_name: The step name to match (e.g., 'clustering', 'DEG_analysis')

        Returns:
            Matching skill_id or None if no match found.
        """
        if not self._initialized:
            self.scan()

        step_norm = self._normalize_name(step_name)

        STEP_KEYWORDS = {
            "qc": ["qc", "filter", "quality"],
            "filter_cells": ["filter_cells", "filter", "qc"],
            "normalization": ["normalize", "normalization", "log1p"],
            "hvg": ["hvg", "highly_variable", "variable_genes"],
            "scaling": ["scale", "scaling"],
            "pca": ["pca"],
            "neighbors": ["neighbors", "neighbor"],
            "clustering": ["leiden", "cluster", "louvain"],
            "umap": ["umap"],
            "batch_correction": ["batch", "harmony", "batch_correction"],
            "cell_annotation": ["celltypist", "annotate", "cell_annotation", "annotation"],
            "deg_analysis": ["rank_genes", "deg", "differential", "markers"],
            "trajectory": ["trajectory", "paga", "dpt", "pseudotime"],
        }

        keywords = STEP_KEYWORDS.get(step_norm, [step_norm])

        for skill_id in self._index:
            skill_norm = self._normalize_name(skill_id)
            for kw in keywords:
                if kw in skill_norm or skill_norm in kw:
                    logger.info(f"Fuzzy matched '{step_name}' to '{skill_id}'")
                    return skill_id

        logger.warning(f"No fuzzy match found for step: '{step_name}'")
        return None

    def validate_all(self) -> dict[str, Any]:
        """
        Run all validation checks and return a report.

        Returns:
            dict with:
            - skill_id_mismatches: folder/skill_id consistency issues
            - available_skills: list of all registered skill_ids
            - missing_essential: steps without matching skills
        """
        if not self._initialized:
            self.scan()

        report = {
            "skill_id_mismatches": self.check_skill_id_consistency(),
            "available_skills": list(self._index.keys()),
            "missing_essential": [],
        }

        ESSENTIAL_STEPS = [
            "qc", "filter_cells", "normalization", "hvg", "scaling",
            "pca", "neighbors", "clustering", "umap", "deg_analysis"
        ]

        for step in ESSENTIAL_STEPS:
            matched = self.fuzzy_match_skill(step)
            if not matched:
                report["missing_essential"].append(step)

        return report

    def auto_fix(self, dry_run: bool = True) -> dict[str, Any]:
        """
        Automatically fix naming inconsistencies.

        Args:
            dry_run: If True, only report fixes without executing them.

        Returns:
            dict with:
            - fixes_applied: list of fixes applied or planned
            - errors: any errors encountered
        """
        if not self._initialized:
            self.scan()

        fixes = []
        errors = []

        issues = self.check_skill_id_consistency()
        for issue in issues:
            old_folder = issue["folder"]
            new_folder = issue["skill_id"]
            old_path = self._skills_root / old_folder
            new_path = self._skills_root / new_folder

            if dry_run:
                fixes.append({
                    "type": "rename_folder",
                    "from": str(old_path),
                    "to": str(new_path),
                    "status": "planned"
                })
            else:
                try:
                    shutil.move(str(old_path), str(new_path))
                    logger.info(f"Renamed {old_folder} to {new_folder}")
                    fixes.append({
                        "type": "rename_folder",
                        "from": str(old_path),
                        "to": str(new_path),
                        "status": "applied"
                    })
                    self._index[new_folder] = self._index.pop(old_folder)
                except Exception as e:
                    logger.error(f"Failed to rename {old_folder}: {e}")
                    errors.append({"folder": old_folder, "error": str(e)})

        return {"fixes": fixes, "errors": errors}


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    root_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("skills/library/")
    registry = SkillRegistry(root_path)
    count = registry.scan()

    print(f"=== SkillRegistry: {registry} ===\n")
    print(f"Found {count} skills:\n")

    for item in registry.get_tool_manifest():
        print(f"  [{item['id']}]")
        print(f"    Purpose: {item['purpose']}\n")
