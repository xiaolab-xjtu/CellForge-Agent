#!/usr/bin/env python3
"""Tests for CapabilityRouter — scoring, multi-cap, negation, schema validation."""

import json
import tempfile
from pathlib import Path

import pytest

from src.agent.capability_router import (
    CapabilityRouter,
    SelectionResult,
    validate_capability_schema,
    _is_negated,
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _write_skill(skill_dir: Path, skill_id: str, cap: str, purpose: str = "") -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill.json").write_text(json.dumps({
        "skill_id": skill_id,
        "capability": cap,
        "cognitive_layer": {"purpose": purpose or f"Purpose of {skill_id}"},
    }))


def _write_capability(cap_dir: Path, cap_id: str, name: str, desc: str,
                       skill_ids: list, stable: bool = True, order: int = 1) -> None:
    (cap_dir / "capability.json").write_text(json.dumps({
        "id": cap_id,
        "name": name,
        "description": desc,
        "skill_ids": skill_ids,
        "stable": stable,
        "typical_order": order,
    }))


def _make_library(tmpdir: str) -> Path:
    """Minimal 3-capability library for general tests."""
    root = Path(tmpdir)
    for cap_id, skill_id, purpose in [
        ("data_preparation", "scanpy_qc", "QC filtering"),
        ("data_preparation", "scanpy_normalize", "Normalization"),
        ("representation", "scanpy_pca", "PCA"),
        ("clustering_annotation", "scanpy_leiden", "Leiden clustering"),
        ("clustering_annotation", "scanpy_rank_genes", "DEG analysis"),
    ]:
        _write_skill(root / cap_id / skill_id, skill_id, cap_id, purpose)

    _write_capability(root / "data_preparation", "data_preparation",
                      "Data Preparation", "QC, normalize, scale",
                      ["scanpy_qc", "scanpy_normalize"], stable=True, order=1)
    _write_capability(root / "representation", "representation",
                      "Representation", "PCA, UMAP, neighbors",
                      ["scanpy_pca"], stable=True, order=2)
    _write_capability(root / "clustering_annotation", "clustering_annotation",
                      "Clustering & Annotation", "Cluster and annotate",
                      ["scanpy_leiden", "scanpy_rank_genes"], stable=True, order=3)
    return root


# ---------------------------------------------------------------------------
# Scan / lifecycle
# ---------------------------------------------------------------------------

class TestScan:
    def test_loads_all_capabilities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            count = router.scan()
            assert count == 3

    def test_missing_root_returns_zero(self):
        router = CapabilityRouter("/nonexistent/path/xyz")
        assert router.scan() == 0

    def test_capability_without_id_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap_dir = Path(tmpdir) / "bad_cap"
            cap_dir.mkdir()
            (cap_dir / "capability.json").write_text(json.dumps({"name": "No ID Cap"}))
            router = CapabilityRouter(tmpdir)
            assert router.scan() == 0

    def test_invalid_json_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap_dir = Path(tmpdir) / "broken"
            cap_dir.mkdir()
            (cap_dir / "capability.json").write_text("not json {{")
            router = CapabilityRouter(tmpdir)
            assert router.scan() == 0


# ---------------------------------------------------------------------------
# Manifest / metadata
# ---------------------------------------------------------------------------

class TestManifest:
    def test_manifest_sorted_by_typical_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            orders = [c["typical_order"] for c in router.get_capability_manifest()]
            assert orders == sorted(orders)

    def test_manifest_contains_required_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            for cap in router.get_capability_manifest():
                assert "id" in cap
                assert "name" in cap
                assert "description" in cap
                assert "stable" in cap
                assert "skill_ids" in cap

    def test_get_capability_by_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            cap = router.get_capability("data_preparation")
            assert cap is not None
            assert cap["name"] == "Data Preparation"

    def test_get_capability_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            assert router.get_capability("does_not_exist") is None


# ---------------------------------------------------------------------------
# SelectionResult dataclass
# ---------------------------------------------------------------------------

class TestSelectionResult:
    def test_bool_true_when_capabilities_selected(self):
        result = SelectionResult(capability_ids=["data_preparation"], scores={}, fallback=False)
        assert bool(result) is True

    def test_bool_false_when_empty(self):
        result = SelectionResult(capability_ids=[], scores={}, fallback=True)
        assert bool(result) is False


# ---------------------------------------------------------------------------
# Stage 1 routing — keyword_select (backward-compat API)
# ---------------------------------------------------------------------------

class TestKeywordSelect:
    def test_normalization_selects_data_preparation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            assert "data_preparation" in router.keyword_select("normalize the data")

    def test_clustering_selects_clustering_annotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            assert "clustering_annotation" in router.keyword_select("cluster cells and find marker genes")

    def test_pca_selects_representation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            assert "representation" in router.keyword_select("run pca and umap")

    def test_no_match_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.keyword_select("xyzzy gobbledygook words match nothing")
            assert result == []

    def test_multi_capability_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.keyword_select(
                "normalize the raw counts, then run pca and umap, then cluster and annotate"
            )
            assert "data_preparation" in result
            assert "representation" in result
            assert "clustering_annotation" in result


# ---------------------------------------------------------------------------
# Stage 1 routing — select() with confidence scores
# ---------------------------------------------------------------------------

class TestSelect:
    def test_select_returns_selection_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.select("normalize and filter cells")
            assert isinstance(result, SelectionResult)

    def test_scores_dict_contains_all_capabilities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.select("normalize cells")
            # scores contains loaded capabilities
            assert "data_preparation" in result.scores
            assert "representation" in result.scores

    def test_scores_in_unit_interval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.select("normalize pca cluster differential expression")
            for cap_id, score in result.scores.items():
                assert 0.0 <= score <= 1.0, f"{cap_id} score {score} out of [0,1]"

    def test_fallback_true_when_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.select("xyzzy gobbledygook words match nothing")
            assert result.fallback is True
            assert result.capability_ids == []

    def test_fallback_false_when_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.select("normalize my data")
            assert result.fallback is False

    def test_custom_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            # Very high threshold should suppress results
            result = router.select("normalize", threshold=0.99)
            assert result.capability_ids == [] or result.fallback

    def test_phrase_match_scores_higher_than_keyword(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            phrase_result = router.select("quality control and highly variable genes")
            kw_result = router.select("qc hvg")
            # phrase query should score >= keyword-only query for data_preparation
            assert (phrase_result.scores.get("data_preparation", 0)
                    >= kw_result.scores.get("data_preparation", 0))

    def test_alias_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            result = router.select("I want dimensionality reduction")
            assert "representation" in result.capability_ids

    def test_sorted_by_score_descending(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            # Heavy clustering text → clustering should rank #1
            result = router.select(
                "cluster leiden louvain annotate cell type marker differential expression deg"
            )
            if len(result.capability_ids) >= 2:
                scores = [result.scores[c] for c in result.capability_ids]
                assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Negation handling
# ---------------------------------------------------------------------------

class TestNegation:
    def test_negated_keyword_reduces_score(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            router = CapabilityRouter(root)
            router.scan()
            normal = router.select("normalize the data")
            negated = router.select("do not normalize, skip normalization")
            # negated should score lower or not be selected
            normal_score = normal.scores.get("data_preparation", 0)
            negated_score = negated.scores.get("data_preparation", 0)
            assert negated_score <= normal_score

    def test_is_negated_detects_not_prefix(self):
        assert _is_negated("please do not normalize the data", "normalize") is True

    def test_is_negated_false_without_negation(self):
        assert _is_negated("please normalize the data", "normalize") is False

    def test_is_negated_detects_without(self):
        assert _is_negated("run the pipeline without batch correction", "batch") is True


# ---------------------------------------------------------------------------
# filter_manifest
# ---------------------------------------------------------------------------

class TestFilterManifest:
    def test_filter_single_capability(self):
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            registry = SkillRegistry(root)
            registry.scan()
            router = CapabilityRouter(root)
            router.scan()

            filtered = router.filter_manifest(registry, ["data_preparation"])
            ids = [s["id"] for s in filtered]
            assert "scanpy_qc" in ids
            assert "scanpy_normalize" in ids
            assert "scanpy_pca" not in ids

    def test_filter_multiple_capabilities(self):
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            registry = SkillRegistry(root)
            registry.scan()
            router = CapabilityRouter(root)
            router.scan()

            filtered = router.filter_manifest(registry, ["data_preparation", "representation"])
            ids = [s["id"] for s in filtered]
            assert "scanpy_qc" in ids
            assert "scanpy_pca" in ids
            assert "scanpy_leiden" not in ids

    def test_filter_empty_list_returns_full_manifest(self):
        from src.agent.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            root = _make_library(tmpdir)
            registry = SkillRegistry(root)
            registry.scan()
            router = CapabilityRouter(root)
            router.scan()

            full = registry.get_tool_manifest()
            assert router.filter_manifest(registry, []) == full


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestValidateCapabilitySchema:
    def test_valid_schema_returns_no_issues(self):
        cap = {
            "id": "my_cap",
            "name": "My Cap",
            "description": "Does things",
            "skill_ids": ["skill_a"],
            "stable": True,
            "typical_order": 1,
        }
        assert validate_capability_schema(cap) == []

    def test_missing_required_field_reported(self):
        cap = {"name": "No ID", "description": "x", "skill_ids": []}
        issues = validate_capability_schema(cap)
        assert any("id" in i for i in issues)

    def test_wrong_type_skill_ids(self):
        cap = {"id": "x", "name": "x", "description": "x", "skill_ids": "not_a_list"}
        issues = validate_capability_schema(cap)
        assert any("skill_ids" in i for i in issues)

    def test_wrong_type_stable(self):
        cap = {"id": "x", "name": "x", "description": "x", "skill_ids": [], "stable": "yes"}
        issues = validate_capability_schema(cap)
        assert any("stable" in i for i in issues)

    def test_wrong_type_typical_order(self):
        cap = {"id": "x", "name": "x", "description": "x", "skill_ids": [], "typical_order": "first"}
        issues = validate_capability_schema(cap)
        assert any("typical_order" in i for i in issues)

    def test_schema_validation_runs_on_scan(self, caplog):
        """scan() logs a warning when capability.json has schema issues."""
        import logging
        with tempfile.TemporaryDirectory() as tmpdir:
            cap_dir = Path(tmpdir) / "broken_cap"
            cap_dir.mkdir()
            # Missing required fields
            (cap_dir / "capability.json").write_text(json.dumps({
                "id": "broken_cap",
                # name, description, skill_ids all missing
            }))
            router = CapabilityRouter(tmpdir)
            with caplog.at_level(logging.WARNING, logger="src.agent.capability_router"):
                router.scan()
            assert any("schema" in r.message.lower() for r in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
