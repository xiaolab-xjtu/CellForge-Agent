#!/usr/bin/env python3
"""Tests for CapabilityRouter."""

import json
import tempfile
from pathlib import Path

import pytest


class TestCapabilityRouter:

    def _make_library(self, tmpdir: str) -> Path:
        """Create a minimal library structure for testing."""
        root = Path(tmpdir)
        for cap_id, skill_id, purpose in [
            ("data_preparation", "scanpy_qc", "QC filtering"),
            ("data_preparation", "scanpy_normalize", "Normalization"),
            ("representation", "scanpy_pca", "PCA"),
            ("clustering_annotation", "scanpy_leiden", "Leiden clustering"),
        ]:
            skill_dir = root / cap_id / skill_id
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "skill.json").write_text(json.dumps({
                "skill_id": skill_id,
                "capability": cap_id,
                "cognitive_layer": {"purpose": purpose},
            }))

        for cap_id, cap_name, description, skill_ids, order in [
            ("data_preparation", "Data Preparation", "Prepare raw data", ["scanpy_qc", "scanpy_normalize"], 1),
            ("representation", "Representation and Integration", "Dimensionality reduction", ["scanpy_pca"], 2),
            ("clustering_annotation", "Clustering and Annotation", "Cluster and annotate cells", ["scanpy_leiden"], 3),
        ]:
            (root / cap_id / "capability.json").write_text(json.dumps({
                "id": cap_id,
                "name": cap_name,
                "description": description,
                "skill_ids": skill_ids,
                "stable": True,
                "typical_order": order,
            }))

        return root

    def test_scan_loads_capabilities(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            count = router.scan()

            assert count == 3
            cap_ids = [c["id"] for c in router.get_capability_manifest()]
            assert "data_preparation" in cap_ids
            assert "representation" in cap_ids
            assert "clustering_annotation" in cap_ids

    def test_capability_manifest_fields(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()

            for cap in router.get_capability_manifest():
                assert "id" in cap
                assert "name" in cap
                assert "description" in cap

    def test_capability_manifest_sorted_by_order(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()

            manifest = router.get_capability_manifest()
            orders = [c["typical_order"] for c in manifest]
            assert orders == sorted(orders)

    def test_filter_manifest_single_capability(self):
        from src.agent.capability_router import CapabilityRouter
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            registry = SkillRegistry(root)
            registry.scan()

            filtered = router.filter_manifest(registry, ["data_preparation"])
            skill_ids = [s["id"] for s in filtered]
            assert "scanpy_qc" in skill_ids
            assert "scanpy_normalize" in skill_ids
            assert "scanpy_pca" not in skill_ids
            assert "scanpy_leiden" not in skill_ids

    def test_filter_manifest_multiple_capabilities(self):
        from src.agent.capability_router import CapabilityRouter
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            registry = SkillRegistry(root)
            registry.scan()

            filtered = router.filter_manifest(registry, ["data_preparation", "representation"])
            skill_ids = [s["id"] for s in filtered]
            assert "scanpy_qc" in skill_ids
            assert "scanpy_pca" in skill_ids
            assert "scanpy_leiden" not in skill_ids

    def test_filter_manifest_empty_returns_all(self):
        from src.agent.capability_router import CapabilityRouter
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            registry = SkillRegistry(root)
            registry.scan()

            assert len(router.filter_manifest(registry, [])) == len(registry.get_tool_manifest())

    def test_keyword_select_clustering(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()

            selected = router.keyword_select("cluster cells and find differential genes")
            assert "clustering_annotation" in selected

    def test_keyword_select_normalization(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()

            selected = router.keyword_select("normalize and filter low quality cells")
            assert "data_preparation" in selected

    def test_keyword_select_no_match_returns_empty(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()

            selected = router.keyword_select("xyzzy nonsense words that match nothing")
            assert selected == []

    def test_get_capability_by_id(self):
        from src.agent.capability_router import CapabilityRouter

        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()

            cap = router.get_capability("data_preparation")
            assert cap is not None
            assert cap["name"] == "Data Preparation"

            assert router.get_capability("nonexistent") is None

    def test_scan_missing_root_returns_zero(self):
        from src.agent.capability_router import CapabilityRouter

        router = CapabilityRouter("/nonexistent/path")
        assert router.scan() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
