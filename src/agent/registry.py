#!/usr/bin/env python3
"""
SkillRegistry - Registry and discovery module for scAgent_v2 skills.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillIndexEntry:
    """Lightweight index entry for a skill."""
    skill_id: str
    purpose: str
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

        return SkillIndexEntry(
            skill_id=skill_id,
            purpose=purpose,
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
            {"id": entry.skill_id, "purpose": entry.purpose}
            for entry in self._index.values()
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
