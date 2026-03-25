#!/usr/bin/env python3
"""Tests for SkillRegistry."""

import json
import tempfile
from pathlib import Path

import pytest


class TestSkillRegistry:
    """Tests for SkillRegistry class."""

    def test_init_default_root(self):
        """Test initialization with default root."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        registry = SkillRegistry()
        assert registry.skills_root == Path("skills/library/")

    def test_init_custom_root(self):
        """Test initialization with custom root."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        registry = SkillRegistry("/custom/path")
        assert registry.skills_root == Path("/custom/path")

    def test_scan_empty_dir(self):
        """Test scanning an empty directory."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(tmpdir)
            count = registry.scan()
            assert count == 0
            assert len(registry) == 0

    def test_scan_with_skill(self):
        """Test scanning directory with a valid skill."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test_skill"
            skill_dir.mkdir()
            skill_json = skill_dir / "skill.json"
            skill_json.write_text(json.dumps({
                "skill_id": "test_skill",
                "cognitive_layer": {"purpose": "Test purpose"},
            }))

            registry = SkillRegistry(tmpdir)
            count = registry.scan()

            assert count == 1
            assert "test_skill" in registry.skill_ids

    def test_scan_invalid_json(self):
        """Test scanning directory with invalid JSON."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "bad_skill"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text("not valid json")

            registry = SkillRegistry(tmpdir)
            count = registry.scan()

            assert count == 0

    def test_scan_missing_skill_id(self):
        """Test scanning skill without skill_id."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "no_id_skill"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(json.dumps({
                "cognitive_layer": {"purpose": "No ID skill"},
            }))

            registry = SkillRegistry(tmpdir)
            count = registry.scan()

            assert count == 0

    def test_get_tool_manifest(self):
        """Test getting tool manifest."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my_skill"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(json.dumps({
                "skill_id": "my_skill",
                "cognitive_layer": {"purpose": "My purpose"},
            }))

            registry = SkillRegistry(tmpdir)
            registry.scan()

            manifest = registry.get_tool_manifest()

            assert len(manifest) == 1
            assert manifest[0]["id"] == "my_skill"
            assert manifest[0]["purpose"] == "My purpose"

    def test_get_skill_spec_on_demand(self):
        """Test loading full skill spec on demand."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "full_skill"
            skill_dir.mkdir()
            skill_json = skill_dir / "skill.json"
            skill_data = {
                "skill_id": "full_skill",
                "cognitive_layer": {"purpose": "Full skill"},
                "execution_layer": {"code_template": "print('hello')"},
            }
            skill_json.write_text(json.dumps(skill_data))

            registry = SkillRegistry(tmpdir)
            registry.scan()

            spec = registry.get_skill_spec("full_skill")

            assert spec is not None
            assert spec["skill_id"] == "full_skill"
            assert "code_template" in spec["execution_layer"]

    def test_register_skill_folder(self):
        """Test dynamic skill registration."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SkillRegistry(tmpdir)
            registry.scan()
            assert len(registry) == 0

            new_skill_dir = Path(tmpdir) / "new_skill"
            new_skill_dir.mkdir()
            (new_skill_dir / "skill.json").write_text(json.dumps({
                "skill_id": "new_skill",
                "cognitive_layer": {"purpose": "New skill"},
            }))

            ok = registry.register_skill_folder(new_skill_dir)

            assert ok is True
            assert "new_skill" in registry.skill_ids

    def test_search(self):
        """Test skill search."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            for name, purpose in [
                ("scanpy_filter", "Filter cells"),
                ("scanpy_normalize", "Normalize data"),
                ("其他工具", "其他目的"),
            ]:
                skill_dir = Path(tmpdir) / name
                skill_dir.mkdir()
                (skill_dir / "skill.json").write_text(json.dumps({
                    "skill_id": name,
                    "cognitive_layer": {"purpose": purpose},
                }))

            registry = SkillRegistry(tmpdir)
            registry.scan()

            results = registry.search("filter")
            assert len(results) == 1
            assert results[0]["id"] == "scanpy_filter"

            results = registry.search("normal")
            assert len(results) == 1
            assert results[0]["id"] == "scanpy_normalize"

    def test_unregister(self):
        """Test skill unregistration."""
        from scAgent_v2.src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "to_remove"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(json.dumps({
                "skill_id": "to_remove",
                "cognitive_layer": {"purpose": "To be removed"},
            }))

            registry = SkillRegistry(tmpdir)
            registry.scan()
            assert "to_remove" in registry.skill_ids

            ok = registry.unregister("to_remove")
            assert ok is True
            assert "to_remove" not in registry.skill_ids

            ok = registry.unregister("nonexistent")
            assert ok is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
