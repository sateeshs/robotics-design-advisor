"""Tests for batch STEP profiling and cache management."""

import json
from pathlib import Path

import pytest

from robotics_design_advisor.step.batch_profiler import (
    BatchResult,
    FailureRecord,
    build_index,
    extract_sku_from_filename,
    run_batch,
)


class TestExtractSku:
    def test_standard_gobilda_name(self):
        assert extract_sku_from_filename("1101-0001-0008.STEP") == "1101-0001-0008"

    def test_lowercase_extension(self):
        assert extract_sku_from_filename("1101-0001-0008.step") == "1101-0001-0008"

    def test_no_extension(self):
        assert extract_sku_from_filename("1101-0001-0008") == "1101-0001-0008"


class TestBuildIndex:
    def test_builds_index_from_profiles(self, tmp_path):
        profile = {
            "sku": "1101-0001-0008",
            "name": "U-Channel 8mm",
            "category": "structure/beam",
            "geometry": {
                "bounding_box": {"x": 48.0, "y": 48.0, "z": 8.0, "unit": "mm"},
                "mass_grams": 15.2,
            },
        }
        profile_path = tmp_path / "1101-0001-0008.json"
        profile_path.write_text(json.dumps(profile))

        index = build_index(str(tmp_path))
        assert "1101-0001-0008" in index
        entry = index["1101-0001-0008"]
        assert entry["category"] == "structure/beam"
        assert entry["bounding_box"]["x"] == 48.0

    def test_empty_dir_returns_empty(self, tmp_path):
        index = build_index(str(tmp_path))
        assert index == {}


class TestBatchResult:
    def test_creation(self):
        result = BatchResult(
            profiled=5,
            skipped=2,
            failed=1,
            index_path="/data/profiles/_index.json",
            failures=(
                FailureRecord(sku="BAD-001", step_path="/bad.STEP", error="parse error"),
            ),
        )
        assert result.profiled == 5
        assert result.failed == 1
        assert len(result.failures) == 1


class TestRunBatch:
    def test_skips_already_cached(self, tmp_path, monkeypatch):
        # Create a fake STEP dir with one file
        step_dir = tmp_path / "steps"
        step_dir.mkdir()
        (step_dir / "1101-0001-0008.STEP").write_text("fake")

        # Create an existing cached profile
        cache_dir = tmp_path / "profiles"
        cache_dir.mkdir()
        cached_profile = {
            "sku": "1101-0001-0008",
            "name": "1101-0001-0008",
            "category": "structure/beam",
            "geometry": {
                "bounding_box": {"x": 1, "y": 1, "z": 1, "unit": "mm"},
                "mass_grams": 1.0,
            },
        }
        (cache_dir / "1101-0001-0008.json").write_text(json.dumps(cached_profile))

        categories = {"1101": "structure/beam"}

        # Mock build_profile to track if it gets called
        call_count = 0

        def mock_build_profile(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return cached_profile

        monkeypatch.setattr(
            "robotics_design_advisor.step.batch_profiler._build_single_profile",
            mock_build_profile,
        )

        result = run_batch(
            step_dirs=(str(step_dir),),
            output_dir=str(cache_dir),
            sku_categories=categories,
        )
        assert result.skipped >= 1
        assert call_count == 0

    def test_writes_index_file(self, tmp_path, monkeypatch):
        step_dir = tmp_path / "steps"
        step_dir.mkdir()
        (step_dir / "1101-0001-0008.STEP").write_text("fake")

        cache_dir = tmp_path / "profiles"
        cache_dir.mkdir()

        categories = {"1101": "structure/beam"}
        fake_profile = {
            "sku": "1101-0001-0008",
            "name": "1101-0001-0008",
            "category": "structure/beam",
            "geometry": {
                "bounding_box": {"x": 48.0, "y": 48.0, "z": 8.0, "unit": "mm"},
                "mass_grams": 15.2,
            },
        }

        monkeypatch.setattr(
            "robotics_design_advisor.step.batch_profiler._build_single_profile",
            lambda *a, **kw: fake_profile,
        )

        result = run_batch(
            step_dirs=(str(step_dir),),
            output_dir=str(cache_dir),
            sku_categories=categories,
        )
        assert result.profiled == 1
        assert Path(result.index_path).exists()
        index = json.loads(Path(result.index_path).read_text())
        assert "1101-0001-0008" in index

    def test_records_failure(self, tmp_path, monkeypatch):
        step_dir = tmp_path / "steps"
        step_dir.mkdir()
        (step_dir / "1101-0001-0008.STEP").write_text("fake")

        cache_dir = tmp_path / "profiles"
        cache_dir.mkdir()

        categories = {"1101": "structure/beam"}

        def mock_fail(*args, **kwargs):
            raise RuntimeError("CadQuery failed")

        monkeypatch.setattr(
            "robotics_design_advisor.step.batch_profiler._build_single_profile",
            mock_fail,
        )

        result = run_batch(
            step_dirs=(str(step_dir),),
            output_dir=str(cache_dir),
            sku_categories=categories,
        )
        assert result.failed == 1
        assert result.failures[0].sku == "1101-0001-0008"
        assert "CadQuery" in result.failures[0].error

    def test_empty_step_dirs(self, tmp_path):
        cache_dir = tmp_path / "profiles"
        cache_dir.mkdir()
        result = run_batch(
            step_dirs=(),
            output_dir=str(cache_dir),
            sku_categories={},
        )
        assert result.profiled == 0
        assert result.failed == 0
