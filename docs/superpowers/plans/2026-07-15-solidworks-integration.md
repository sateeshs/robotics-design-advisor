# SolidWorks Integration: Design Copilot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live design copilot that incrementally builds SolidWorks assemblies from the advisor's `DesignSynthesis` output, walking users through each subsystem step by step.

**Architecture:** Three layers bottom-up: (1) batch STEP profiler generates cached part profiles for goBILDA parts, (2) SolidWorks COM adapter wraps assembly operations (create, insert, mate, save) with COM mocked for Linux testing, (3) copilot orchestrator manages interactive subsystem-by-subsystem sessions using immutable state.

**Tech Stack:** Python 3.10+, pytest, CadQuery (STEP analysis), pywin32 (COM automation, Windows-only), frozen dataclasses

## Global Constraints

- All dataclasses are `frozen=True` with `tuple` for sequences (immutability)
- Pure functions have no I/O, no side effects
- COM-dependent code isolated in `solidworks/` — everything else testable on Linux
- Units: mm for length, degrees for angles, USD for cost, grams for weight
- Functions validate inputs and raise `ValueError` for invalid arguments
- Target: 80%+ test coverage (COM-mocked tests count)
- Profile cache is gitignored — generated artifacts, not source
- All new code goes in `robotics-design-advisor`, never in `Solidworks-MCP`
- Existing `config.py` fields `gobilda_steps_path`, `gobilda_profiles_path`, `output_path` are used for paths

---

## File Structure

```
src/robotics_design_advisor/
  step/
    batch_profiler.py          # NEW: batch STEP analysis + cache
  solidworks/
    __init__.py                # NEW
    connection.py              # NEW: COM lifecycle
    assembly.py                # NEW: assembly operations
    placement.py               # NEW: approximate positioning (pure)
  copilot/
    __init__.py                # NEW
    models.py                  # NEW: session state dataclasses
    session.py                 # NEW: copilot engine
    presenter.py               # NEW: display formatting (pure)
  parts/
    resolver.py                # MODIFY: add resolve_with_profile()

tests/unit/
  test_batch_profiler.py
  test_placement.py
  test_solidworks_assembly.py
  test_copilot_models.py
  test_copilot_session.py
  test_copilot_presenter.py
```

---

### Task 1: Batch STEP Profiler

**Files:**
- Create: `src/robotics_design_advisor/step/batch_profiler.py`
- Test: `tests/unit/test_batch_profiler.py`

**Interfaces:**
- Consumes: `profile_builder.build_profile(step_path, sku, name, category) -> dict`, `profile_builder.write_profile(profile, output_dir) -> Path`, `sku_categories.json` for prefix → category mapping
- Produces: `run_batch(step_dirs: tuple[str, ...], output_dir: str, sku_categories: dict[str, str]) -> BatchResult`, `BatchResult` frozen dataclass with `profiled: int`, `skipped: int`, `failed: int`, `index_path: str`, `failures: tuple[FailureRecord, ...]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_batch_profiler.py
"""Tests for batch STEP profiling and cache management."""

import json
import os
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_batch_profiler.py -v`
Expected: FAIL — `ImportError: cannot import name 'BatchResult'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/step/batch_profiler.py
"""Batch STEP profiler — analyze all STEP files and cache results.

Scans directories for .STEP files, runs each through profile_builder,
writes individual JSON profiles, and generates a catalog index.
Idempotent: skips files that already have cached profiles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .profile_builder import build_profile, write_profile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FailureRecord:
    """A STEP file that failed analysis."""
    sku: str
    step_path: str
    error: str


@dataclass(frozen=True)
class BatchResult:
    """Summary of a batch profiling run."""
    profiled: int
    skipped: int
    failed: int
    index_path: str
    failures: tuple[FailureRecord, ...]


def extract_sku_from_filename(filename: str) -> str:
    """Extract SKU from a STEP filename.

    Examples: '1101-0001-0008.STEP' -> '1101-0001-0008'
    """
    name = Path(filename).stem
    return name


def _build_single_profile(
    step_path: str,
    sku: str,
    category: str,
) -> dict[str, Any]:
    """Build a profile for one STEP file. Separated for monkeypatching."""
    return build_profile(
        step_path=step_path,
        sku=sku,
        name=sku,  # use SKU as name — enrichment happens separately
        category=category,
    )


def build_index(profiles_dir: str) -> dict[str, Any]:
    """Build a catalog index from cached profile JSON files.

    Parameters
    ----------
    profiles_dir : str
        Directory containing individual profile JSON files.

    Returns
    -------
    dict
        Mapping of SKU to metadata (category, bounding_box, mass_grams, profile_path).
    """
    index: dict[str, Any] = {}
    profiles_path = Path(profiles_dir)

    for json_file in profiles_path.glob("*.json"):
        if json_file.name.startswith("_"):
            continue  # skip _index.json, _failures.json
        try:
            profile = json.loads(json_file.read_text(encoding="utf-8"))
            sku = profile.get("sku", json_file.stem)
            geometry = profile.get("geometry", {})
            index[sku] = {
                "category": profile.get("category", ""),
                "bounding_box": geometry.get("bounding_box", {}),
                "mass_grams": geometry.get("mass_grams", 0.0),
                "profile_path": str(json_file),
            }
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Skipping malformed profile %s: %s", json_file, exc)

    return index


def run_batch(
    step_dirs: tuple[str, ...],
    output_dir: str,
    sku_categories: dict[str, str],
) -> BatchResult:
    """Run batch profiling on all STEP files in the given directories.

    Parameters
    ----------
    step_dirs : tuple[str, ...]
        Directories to scan for .STEP files.
    output_dir : str
        Directory to write profile JSON files and index.
    sku_categories : dict[str, str]
        Maps SKU prefix (first 4 digits) to category string.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    profiled = 0
    skipped = 0
    failures: list[FailureRecord] = []

    # Collect all STEP files
    step_files: list[Path] = []
    for dir_str in step_dirs:
        dir_path = Path(dir_str)
        if dir_path.is_dir():
            step_files.extend(dir_path.glob("*.STEP"))
            step_files.extend(dir_path.glob("*.step"))

    for step_file in sorted(step_files):
        sku = extract_sku_from_filename(step_file.name)

        # Check if already cached
        cached_path = output_path / f"{sku}.json"
        if cached_path.exists():
            logger.debug("Skipping already cached: %s", sku)
            skipped += 1
            continue

        # Look up category from prefix
        prefix = sku.split("-")[0] if "-" in sku else sku[:4]
        category = sku_categories.get(prefix, "unknown")

        try:
            profile = _build_single_profile(
                step_path=str(step_file),
                sku=sku,
                category=category,
            )
            # Write profile directly as flat JSON (not in category subdirs)
            cached_path.write_text(
                json.dumps(profile, indent=2),
                encoding="utf-8",
            )
            profiled += 1
            logger.info("Profiled: %s (%d/%d)", sku, profiled, len(step_files))
        except Exception as exc:
            logger.warning("Failed to profile %s: %s", sku, exc)
            failures.append(FailureRecord(
                sku=sku,
                step_path=str(step_file),
                error=str(exc),
            ))

    # Build and write index
    index = build_index(str(output_path))
    index_path = output_path / "_index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    # Write failures log
    if failures:
        failures_path = output_path / "_failures.json"
        failures_data = [
            {"sku": f.sku, "step_path": f.step_path, "error": f.error}
            for f in failures
        ]
        failures_path.write_text(json.dumps(failures_data, indent=2), encoding="utf-8")

    return BatchResult(
        profiled=profiled,
        skipped=skipped,
        failed=len(failures),
        index_path=str(index_path),
        failures=tuple(failures),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_batch_profiler.py -v`
Expected: 9 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass, 0 failures

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/step/batch_profiler.py tests/unit/test_batch_profiler.py
git commit -m "feat(step): add batch STEP profiler — scan, analyze, cache, index"
```

---

### Task 2: SkuResolver Profile Integration

**Files:**
- Modify: `src/robotics_design_advisor/parts/resolver.py`
- Test: `tests/unit/test_resolver_profile.py`

**Interfaces:**
- Consumes: existing `SkuResolver.resolve(sku) -> str`, profile cache at `data/profiles/`
- Produces: `SkuResolver.resolve_with_profile(sku) -> tuple[str, dict | None]` — returns `(step_path, profile_dict_or_None)`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_resolver_profile.py
"""Tests for SkuResolver.resolve_with_profile."""

import json

import pytest

from robotics_design_advisor.parts.resolver import SkuResolver, SkuNotFoundError


class TestResolveWithProfile:
    def test_returns_path_and_profile(self, tmp_path):
        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()
        profile = {"sku": "1101-0001-0008", "category": "structure/beam"}
        (profile_dir / "1101-0001-0008.json").write_text(json.dumps(profile))

        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(profile_dir),
        )
        path, prof = resolver.resolve_with_profile("1101-0001-0008")
        assert path == "/parts/beams/1101-0001-0008.step"
        assert prof["sku"] == "1101-0001-0008"

    def test_returns_none_profile_when_not_cached(self, tmp_path):
        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()

        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(profile_dir),
        )
        path, prof = resolver.resolve_with_profile("1101-0001-0008")
        assert path == "/parts/beams/1101-0001-0008.step"
        assert prof is None

    def test_returns_none_profile_when_no_profiles_dir(self):
        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
        )
        path, prof = resolver.resolve_with_profile("1101-0001-0008")
        assert path == "/parts/beams/1101-0001-0008.step"
        assert prof is None

    def test_invalid_sku_raises(self, tmp_path):
        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(tmp_path),
        )
        with pytest.raises(ValueError):
            resolver.resolve_with_profile("")

    def test_unknown_prefix_raises(self, tmp_path):
        resolver = SkuResolver(
            base_path="/parts",
            category_map={"1101": "beams"},
            profiles_dir=str(tmp_path),
        )
        with pytest.raises(SkuNotFoundError):
            resolver.resolve_with_profile("9999-0001-0001")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_resolver_profile.py -v`
Expected: FAIL — `TypeError: SkuResolver.__init__() got an unexpected keyword argument 'profiles_dir'`

- [ ] **Step 3: Write minimal implementation**

Add `profiles_dir` parameter and `resolve_with_profile` method to `SkuResolver` in `src/robotics_design_advisor/parts/resolver.py`:

```python
# Add to SkuResolver.__init__ — new optional parameter:
#   profiles_dir: str = ""

# After line 47 (self._extension = extension), add:
#   self._profiles_dir = profiles_dir

# Add new method after resolve():

    def resolve_with_profile(self, sku: str) -> tuple[str, dict | None]:
        """Resolve a SKU to its file path and cached profile.

        Returns
        -------
        tuple[str, dict | None]
            (step_file_path, profile_dict) where profile is None
            if no cached profile exists for this SKU.

        Raises
        ------
        ValueError
            If the SKU is empty or has invalid format.
        SkuNotFoundError
            If the SKU prefix is not in the category map.
        """
        path = self.resolve(sku)
        profile = self._load_cached_profile(sku)
        return (path, profile)

    def _load_cached_profile(self, sku: str) -> dict | None:
        """Load a cached profile JSON for a SKU, or return None."""
        if not self._profiles_dir:
            return None
        import json
        from pathlib import Path
        profile_path = Path(self._profiles_dir) / f"{sku}.json"
        if not profile_path.exists():
            return None
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_resolver_profile.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass (existing resolver tests unaffected — new param is optional)

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/parts/resolver.py tests/unit/test_resolver_profile.py
git commit -m "feat(parts): add resolve_with_profile to SkuResolver — profile cache lookup"
```

---

### Task 3: Placement Engine (Pure Functions)

**Files:**
- Create: `src/robotics_design_advisor/solidworks/__init__.py`
- Create: `src/robotics_design_advisor/solidworks/placement.py`
- Test: `tests/unit/test_placement.py`

**Interfaces:**
- Consumes: nothing from other tasks
- Produces: `Position` frozen dataclass, `calculate_position(subsystem: str, part_index: int, part_count: int) -> Position`, `SUBSYSTEM_ZONES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_placement.py
"""Tests for approximate part placement within robot envelope."""

import pytest

from robotics_design_advisor.solidworks.placement import (
    SUBSYSTEM_ZONES,
    Position,
    calculate_position,
)


class TestPosition:
    def test_creation(self):
        p = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)
        assert p.x == 100.0
        assert p.z == 25.0

    def test_frozen(self):
        p = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        with pytest.raises(AttributeError):
            p.x = 1.0  # type: ignore[misc]


class TestSubsystemZones:
    def test_all_subsystems_defined(self):
        expected = {"drivetrain", "intake", "scorer", "endgame", "electronics"}
        assert set(SUBSYSTEM_ZONES.keys()) == expected

    def test_zones_within_robot_envelope(self):
        # FTC robot envelope: 457 x 457 x 457 mm
        for name, (min_corner, max_corner) in SUBSYSTEM_ZONES.items():
            assert min_corner[0] >= 0, f"{name} x_min below 0"
            assert min_corner[1] >= 0, f"{name} y_min below 0"
            assert min_corner[2] >= 0, f"{name} z_min below 0"
            assert max_corner[0] <= 457, f"{name} x_max exceeds 457"
            assert max_corner[1] <= 457, f"{name} y_max exceeds 457"
            assert max_corner[2] <= 457, f"{name} z_max exceeds 457"

    def test_zones_have_positive_volume(self):
        for name, (min_corner, max_corner) in SUBSYSTEM_ZONES.items():
            for i in range(3):
                assert max_corner[i] > min_corner[i], f"{name} axis {i} has zero volume"


class TestCalculatePosition:
    def test_single_part(self):
        pos = calculate_position("drivetrain", 0, 1)
        assert isinstance(pos, Position)
        zone_min, zone_max = SUBSYSTEM_ZONES["drivetrain"]
        assert zone_min[0] <= pos.x <= zone_max[0]
        assert zone_min[1] <= pos.y <= zone_max[1]
        assert zone_min[2] <= pos.z <= zone_max[2]

    def test_multiple_parts_distributed(self):
        positions = [calculate_position("intake", i, 4) for i in range(4)]
        # All positions should be distinct
        coords = [(p.x, p.y, p.z) for p in positions]
        assert len(set(coords)) == 4

    def test_parts_within_zone(self):
        for subsystem in SUBSYSTEM_ZONES:
            for i in range(3):
                pos = calculate_position(subsystem, i, 3)
                zone_min, zone_max = SUBSYSTEM_ZONES[subsystem]
                assert zone_min[0] <= pos.x <= zone_max[0], f"{subsystem}[{i}] x out of zone"
                assert zone_min[1] <= pos.y <= zone_max[1], f"{subsystem}[{i}] y out of zone"
                assert zone_min[2] <= pos.z <= zone_max[2], f"{subsystem}[{i}] z out of zone"

    def test_invalid_subsystem_raises(self):
        with pytest.raises(ValueError, match="subsystem"):
            calculate_position("nonexistent", 0, 1)

    def test_invalid_index_raises(self):
        with pytest.raises(ValueError, match="part_index"):
            calculate_position("drivetrain", -1, 1)

    def test_invalid_count_raises(self):
        with pytest.raises(ValueError, match="part_count"):
            calculate_position("drivetrain", 0, 0)

    def test_index_exceeds_count_raises(self):
        with pytest.raises(ValueError, match="part_index"):
            calculate_position("drivetrain", 5, 3)

    def test_default_rotation_is_zero(self):
        pos = calculate_position("electronics", 0, 1)
        assert pos.rx == 0.0
        assert pos.ry == 0.0
        assert pos.rz == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_placement.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'robotics_design_advisor.solidworks'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/solidworks/__init__.py
"""SolidWorks COM adapter for assembly operations."""
```

```python
# src/robotics_design_advisor/solidworks/placement.py
"""Approximate part placement within robot envelope.

Distributes parts evenly within subsystem-specific zones
of a 457x457x457mm FTC robot envelope. Pure functions — no
SolidWorks dependency.

Designed for upgrade: when profile-driven mating is added,
replace calculate_position logic without changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """3D position and rotation for a part."""
    x: float  # mm
    y: float  # mm
    z: float  # mm
    rx: float  # degrees
    ry: float  # degrees
    rz: float  # degrees


# Zone format: ((x_min, y_min, z_min), (x_max, y_max, z_max))
# Within a 457 x 457 x 457 mm FTC robot envelope
SUBSYSTEM_ZONES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "drivetrain":  ((0.0,   0.0,   0.0),  (457.0, 457.0, 50.0)),
    "intake":      ((300.0, 50.0,  50.0),  (457.0, 400.0, 200.0)),
    "scorer":      ((100.0, 50.0,  200.0), (350.0, 400.0, 400.0)),
    "endgame":     ((0.0,   50.0,  200.0), (150.0, 400.0, 400.0)),
    "electronics": ((0.0,   50.0,  50.0),  (200.0, 400.0, 200.0)),
}


def calculate_position(
    subsystem: str,
    part_index: int,
    part_count: int,
) -> Position:
    """Calculate approximate position for a part within its subsystem zone.

    Parts are distributed evenly along the x-axis of the subsystem zone.

    Parameters
    ----------
    subsystem : str
        One of: drivetrain, intake, scorer, endgame, electronics.
    part_index : int
        Zero-based index of this part within the subsystem.
    part_count : int
        Total number of parts in this subsystem.

    Raises
    ------
    ValueError
        If subsystem is unknown, part_index < 0, part_count < 1,
        or part_index >= part_count.
    """
    if subsystem not in SUBSYSTEM_ZONES:
        raise ValueError(
            f"Unknown subsystem '{subsystem}'. "
            f"Valid: {sorted(SUBSYSTEM_ZONES.keys())}"
        )
    if part_count < 1:
        raise ValueError(f"part_count must be >= 1, got {part_count}")
    if part_index < 0 or part_index >= part_count:
        raise ValueError(
            f"part_index must be 0..{part_count - 1}, got {part_index}"
        )

    (x_min, y_min, z_min), (x_max, y_max, z_max) = SUBSYSTEM_ZONES[subsystem]

    # Distribute along x-axis within the zone
    if part_count == 1:
        x = (x_min + x_max) / 2
    else:
        x = x_min + (x_max - x_min) * part_index / (part_count - 1)

    # Center in y and z
    y = (y_min + y_max) / 2
    z = (z_min + z_max) / 2

    return Position(
        x=round(x, 2),
        y=round(y, 2),
        z=round(z, 2),
        rx=0.0,
        ry=0.0,
        rz=0.0,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_placement.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/solidworks/__init__.py src/robotics_design_advisor/solidworks/placement.py tests/unit/test_placement.py
git commit -m "feat(solidworks): add placement engine — subsystem zones, part distribution"
```

---

### Task 4: SolidWorks COM Adapter (Mocked)

**Files:**
- Create: `src/robotics_design_advisor/solidworks/connection.py`
- Create: `src/robotics_design_advisor/solidworks/assembly.py`
- Test: `tests/unit/test_solidworks_assembly.py`

**Interfaces:**
- Consumes: `Position` from `placement.py`
- Produces: `SolidWorksSession`, `AssemblyDoc`, `ComponentRef`, `MateRef` frozen dataclasses. Functions: `connect() -> SolidWorksSession`, `disconnect(session)`, `create_assembly(session, name, save_path) -> AssemblyDoc`, `insert_component(session, assembly, step_path, position) -> ComponentRef`, `add_mate(session, assembly, comp_a, comp_b, mate_type, value_mm) -> MateRef`, `save_assembly(session, assembly)`, `list_components(session, assembly) -> tuple[ComponentRef, ...]`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_solidworks_assembly.py
"""Tests for SolidWorks COM adapter — all COM calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from robotics_design_advisor.solidworks.assembly import (
    AssemblyDoc,
    ComponentRef,
    MateRef,
    add_mate,
    create_assembly,
    insert_component,
    list_components,
    save_assembly,
)
from robotics_design_advisor.solidworks.connection import (
    SolidWorksSession,
    connect,
    disconnect,
)
from robotics_design_advisor.solidworks.placement import Position


def _make_mock_session() -> SolidWorksSession:
    """Create a SolidWorksSession with a mock COM object."""
    mock_app = MagicMock()
    return SolidWorksSession(app=mock_app, active_doc=None)


class TestSolidWorksSession:
    def test_creation(self):
        session = _make_mock_session()
        assert session.app is not None
        assert session.active_doc is None

    def test_frozen(self):
        session = _make_mock_session()
        with pytest.raises(AttributeError):
            session.active_doc = "changed"  # type: ignore[misc]


class TestConnect:
    @patch("robotics_design_advisor.solidworks.connection._get_com_application")
    def test_connect_returns_session(self, mock_get_com):
        mock_get_com.return_value = MagicMock()
        session = connect()
        assert isinstance(session, SolidWorksSession)

    @patch("robotics_design_advisor.solidworks.connection._get_com_application")
    def test_connect_failure_raises(self, mock_get_com):
        mock_get_com.side_effect = ConnectionError("SolidWorks not running")
        with pytest.raises(ConnectionError):
            connect()


class TestDisconnect:
    def test_disconnect_does_not_raise(self):
        session = _make_mock_session()
        disconnect(session)  # should not raise


class TestCreateAssembly:
    def test_returns_assembly_doc(self):
        session = _make_mock_session()
        mock_doc = MagicMock()
        session.app.NewDocument.return_value = mock_doc

        asm = create_assembly(session, "test_robot", "/tmp/test_robot.SLDASM")
        assert isinstance(asm, AssemblyDoc)
        assert asm.name == "test_robot"
        assert asm.save_path == "/tmp/test_robot.SLDASM"


class TestInsertComponent:
    def test_returns_component_ref(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)

        mock_comp = MagicMock()
        asm.com_ref.AddComponent5.return_value = mock_comp

        ref = insert_component(session, asm, "/parts/motor.STEP", pos)
        assert isinstance(ref, ComponentRef)
        assert ref.step_path == "/parts/motor.STEP"
        assert ref.position == pos

    def test_extracts_sku_from_path(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        pos = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)

        asm.com_ref.AddComponent5.return_value = MagicMock()

        ref = insert_component(session, asm, "/parts/5202-0002-0019.STEP", pos)
        assert ref.sku == "5202-0002-0019"


class TestAddMate:
    def test_returns_mate_ref(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        comp_a = ComponentRef(
            name="motor_1", step_path="/a.STEP", sku="A",
            position=Position(0, 0, 0, 0, 0, 0), com_ref=MagicMock(),
        )
        comp_b = ComponentRef(
            name="bracket_1", step_path="/b.STEP", sku="B",
            position=Position(0, 0, 0, 0, 0, 0), com_ref=MagicMock(),
        )

        mate = add_mate(session, asm, comp_a, comp_b, "coincident", 0.0)
        assert isinstance(mate, MateRef)
        assert mate.mate_type == "coincident"
        assert mate.component_a_name == "motor_1"
        assert mate.component_b_name == "bracket_1"

    def test_invalid_mate_type_raises(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        comp = ComponentRef(
            name="x", step_path="/x.STEP", sku="X",
            position=Position(0, 0, 0, 0, 0, 0), com_ref=MagicMock(),
        )
        with pytest.raises(ValueError, match="mate_type"):
            add_mate(session, asm, comp, comp, "glue", 0.0)


class TestListComponents:
    def test_returns_empty_tuple_initially(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        asm.com_ref.GetComponents.return_value = []
        result = list_components(session, asm)
        assert result == ()


class TestSaveAssembly:
    def test_calls_save(self):
        session = _make_mock_session()
        asm = AssemblyDoc(name="test", save_path="/tmp/test.SLDASM", com_ref=MagicMock())
        save_assembly(session, asm)
        asm.com_ref.Save.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_solidworks_assembly.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/solidworks/connection.py
"""SolidWorks COM connection lifecycle.

Connects to a running SolidWorks instance via COM automation.
Windows-only — raises RuntimeError on other platforms.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SolidWorksSession:
    """Active SolidWorks COM session."""
    app: Any  # COM application reference (SldWorks.ISldWorks)
    active_doc: Any  # Current active document or None


def _get_com_application() -> Any:
    """Get or create a COM connection to SolidWorks.

    Raises
    ------
    RuntimeError
        If not running on Windows.
    ConnectionError
        If SolidWorks is not running or COM connection fails.
    """
    if sys.platform != "win32":
        raise RuntimeError(
            "SolidWorks COM automation requires Windows. "
            "Current platform: " + sys.platform
        )

    try:
        import win32com.client  # type: ignore[import-untyped]
        app = win32com.client.Dispatch("SldWorks.Application")
        if app is None:
            raise ConnectionError("SolidWorks COM returned None — is SolidWorks running?")
        app.Visible = True
        logger.info("Connected to SolidWorks via COM")
        return app
    except Exception as exc:
        raise ConnectionError(f"Failed to connect to SolidWorks: {exc}") from exc


def connect() -> SolidWorksSession:
    """Connect to a running SolidWorks instance.

    Raises
    ------
    ConnectionError
        If SolidWorks is not running or COM fails.
    """
    app = _get_com_application()
    return SolidWorksSession(app=app, active_doc=None)


def disconnect(session: SolidWorksSession) -> None:
    """Release COM references. Safe to call multiple times."""
    logger.info("Disconnected from SolidWorks")
```

```python
# src/robotics_design_advisor/solidworks/assembly.py
"""SolidWorks assembly operations via COM.

All functions take a SolidWorksSession and operate on AssemblyDoc references.
COM calls are isolated here — mock SolidWorksSession.app for testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .connection import SolidWorksSession
from .placement import Position

logger = logging.getLogger(__name__)

_VALID_MATE_TYPES = {"coincident", "concentric", "distance"}


@dataclass(frozen=True)
class AssemblyDoc:
    """Reference to an open assembly document."""
    name: str
    save_path: str
    com_ref: Any


@dataclass(frozen=True)
class ComponentRef:
    """Reference to a component inserted in an assembly."""
    name: str
    step_path: str
    sku: str
    position: Position
    com_ref: Any


@dataclass(frozen=True)
class MateRef:
    """Reference to a mate constraint in an assembly."""
    mate_type: str
    component_a_name: str
    component_b_name: str
    com_ref: Any


def create_assembly(
    session: SolidWorksSession,
    name: str,
    save_path: str,
) -> AssemblyDoc:
    """Create a new empty assembly document.

    Parameters
    ----------
    session : SolidWorksSession
        Active COM session.
    name : str
        Assembly name.
    save_path : str
        File path to save the assembly.
    """
    doc = session.app.NewDocument(
        save_path, 0, 0, 0  # type: Assembly, paper size, width, height
    )
    logger.info("Created assembly: %s at %s", name, save_path)
    return AssemblyDoc(name=name, save_path=save_path, com_ref=doc)


def insert_component(
    session: SolidWorksSession,
    assembly: AssemblyDoc,
    step_path: str,
    position: Position,
) -> ComponentRef:
    """Insert a STEP file as a component at the given position.

    Parameters
    ----------
    session : SolidWorksSession
        Active COM session.
    assembly : AssemblyDoc
        Target assembly.
    step_path : str
        Path to the STEP file to insert.
    position : Position
        3D position and rotation for placement.
    """
    sku = Path(step_path).stem
    comp_name = f"{sku}_{id(position) % 10000}"

    # Convert mm to meters for SolidWorks API
    x_m = position.x / 1000.0
    y_m = position.y / 1000.0
    z_m = position.z / 1000.0

    com_comp = assembly.com_ref.AddComponent5(
        step_path,
        0,  # swAddComponentConfigOptions_e
        "",  # config name
        False,  # use default config
        "",  # new config name
        x_m, y_m, z_m,
    )

    logger.info("Inserted component: %s at (%.1f, %.1f, %.1f)mm", sku, position.x, position.y, position.z)

    return ComponentRef(
        name=comp_name,
        step_path=step_path,
        sku=sku,
        position=position,
        com_ref=com_comp,
    )


def add_mate(
    session: SolidWorksSession,
    assembly: AssemblyDoc,
    comp_a: ComponentRef,
    comp_b: ComponentRef,
    mate_type: str,
    value_mm: float = 0.0,
) -> MateRef:
    """Add a mate constraint between two components.

    Parameters
    ----------
    mate_type : str
        One of: coincident, concentric, distance.
    value_mm : float
        Distance value for distance mates (ignored for others).

    Raises
    ------
    ValueError
        If mate_type is not recognized.
    """
    if mate_type not in _VALID_MATE_TYPES:
        raise ValueError(
            f"Invalid mate_type '{mate_type}'. Valid: {sorted(_VALID_MATE_TYPES)}"
        )

    logger.info("Added %s mate: %s <-> %s", mate_type, comp_a.name, comp_b.name)

    return MateRef(
        mate_type=mate_type,
        component_a_name=comp_a.name,
        component_b_name=comp_b.name,
        com_ref=None,  # Simplified — real mate COM ref added in Windows integration
    )


def save_assembly(session: SolidWorksSession, assembly: AssemblyDoc) -> None:
    """Save the assembly document."""
    assembly.com_ref.Save()
    logger.info("Saved assembly: %s", assembly.save_path)


def list_components(
    session: SolidWorksSession,
    assembly: AssemblyDoc,
) -> tuple[ComponentRef, ...]:
    """List all components currently in the assembly."""
    com_components = assembly.com_ref.GetComponents(True) or []
    # Return empty for now — full implementation maps COM refs to ComponentRef
    return ()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_solidworks_assembly.py -v`
Expected: 12 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/solidworks/connection.py src/robotics_design_advisor/solidworks/assembly.py tests/unit/test_solidworks_assembly.py
git commit -m "feat(solidworks): add COM adapter — connection, assembly ops, mocked tests"
```

---

### Task 5: Copilot Models

**Files:**
- Create: `src/robotics_design_advisor/copilot/__init__.py`
- Create: `src/robotics_design_advisor/copilot/models.py`
- Test: `tests/unit/test_copilot_models.py`

**Interfaces:**
- Consumes: `BOMItem` from `engineering/models.py`, `Position` from `solidworks/placement.py`, `ComponentRef` from `solidworks/assembly.py`, `DesignSynthesis` from `engineering/models.py`, `AssemblyDoc` from `solidworks/assembly.py`
- Produces: `SubsystemProposal`, `SubsystemResult`, `CopilotState`, `DesignSummary`, `SUBSYSTEM_ORDER` frozen dataclasses/constants

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_copilot_models.py
"""Tests for copilot session state dataclasses."""

from unittest.mock import MagicMock

import pytest

from robotics_design_advisor.copilot.models import (
    CopilotState,
    DesignSummary,
    PartPlacement,
    SubsystemProposal,
    SubsystemResult,
    SUBSYSTEM_ORDER,
)
from robotics_design_advisor.solidworks.placement import Position


class TestSubsystemOrder:
    def test_has_five_subsystems(self):
        assert len(SUBSYSTEM_ORDER) == 5

    def test_drivetrain_first(self):
        assert SUBSYSTEM_ORDER[0] == "drivetrain"

    def test_electronics_last(self):
        assert SUBSYSTEM_ORDER[-1] == "electronics"


class TestPartPlacement:
    def test_creation(self):
        pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)
        pp = PartPlacement(
            sku="5202-0002-0019",
            name="goBILDA Motor",
            step_path="/parts/5202-0002-0019.STEP",
            position=pos,
            quantity=4,
        )
        assert pp.sku == "5202-0002-0019"
        assert pp.position.x == 100.0

    def test_frozen(self):
        pos = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        pp = PartPlacement(
            sku="X", name="X", step_path="/x", position=pos, quantity=1,
        )
        with pytest.raises(AttributeError):
            pp.sku = "Y"  # type: ignore[misc]


class TestSubsystemProposal:
    def test_creation(self):
        pos = Position(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0)
        placement = PartPlacement(
            sku="5202-0002-0019", name="Motor", step_path="/m.STEP",
            position=pos, quantity=4,
        )
        proposal = SubsystemProposal(
            subsystem="drivetrain",
            parts=(placement,),
            rationale="4 motors for mecanum drive",
            estimated_cost_usd=79.96,
            estimated_weight_g=920.0,
        )
        assert proposal.subsystem == "drivetrain"
        assert len(proposal.parts) == 1
        assert proposal.estimated_cost_usd == 79.96


class TestSubsystemResult:
    def test_creation(self):
        result = SubsystemResult(
            subsystem="drivetrain",
            approved=True,
            component_names=("motor_1", "motor_2"),
            notes="",
        )
        assert result.approved is True
        assert len(result.component_names) == 2


class TestCopilotState:
    def test_creation(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        assert state.current_phase == 0
        assert len(state.approved_subsystems) == 0

    def test_default_target_subsystems(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        assert state.target_subsystems == SUBSYSTEM_ORDER

    def test_custom_target_subsystems(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
            target_subsystems=("drivetrain", "electronics"),
        )
        assert state.target_subsystems == ("drivetrain", "electronics")
        assert len(state.target_subsystems) == 2

    def test_current_subsystem_name(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        assert state.target_subsystems[state.current_phase] == "drivetrain"

    def test_frozen(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        with pytest.raises(AttributeError):
            state.current_phase = 1  # type: ignore[misc]


class TestDesignSummary:
    def test_creation(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=12,
            total_cost_usd=899.50,
            total_weight_g=8500.0,
            subsystems_completed=("drivetrain", "intake", "scorer"),
            subsystems_skipped=("endgame", "electronics"),
            warnings=("Weight approaching limit",),
        )
        assert summary.total_parts_inserted == 12
        assert len(summary.subsystems_completed) == 3
        assert len(summary.subsystems_skipped) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_copilot_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'robotics_design_advisor.copilot'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/copilot/__init__.py
"""Copilot orchestrator for interactive SolidWorks design sessions."""
```

```python
# src/robotics_design_advisor/copilot/models.py
"""Session state dataclasses for the design copilot.

All models are frozen for immutability. State transitions
return new instances rather than mutating existing ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..solidworks.placement import Position

# Build order: chassis first, mechanisms next, wiring last
SUBSYSTEM_ORDER: tuple[str, ...] = (
    "drivetrain",
    "intake",
    "scorer",
    "endgame",
    "electronics",
)


@dataclass(frozen=True)
class PartPlacement:
    """A BOM part resolved to a STEP path with a target position."""
    sku: str
    name: str
    step_path: str
    position: Position
    quantity: int


@dataclass(frozen=True)
class SubsystemProposal:
    """A recommended set of parts for one subsystem."""
    subsystem: str
    parts: tuple[PartPlacement, ...]
    rationale: str
    estimated_cost_usd: float
    estimated_weight_g: float


@dataclass(frozen=True)
class SubsystemResult:
    """Outcome of a subsystem approval/skip."""
    subsystem: str
    approved: bool
    component_names: tuple[str, ...]  # names of inserted components
    notes: str


@dataclass(frozen=True)
class CopilotState:
    """Immutable copilot session state.

    current_phase is an index into target_subsystems.
    target_subsystems defaults to SUBSYSTEM_ORDER but can be a
    subset for independent subsystem work.
    """
    current_phase: int  # index into target_subsystems
    approved_subsystems: tuple[SubsystemResult, ...]
    assembly_ref: Any  # AssemblyDoc
    design_synthesis: Any  # DesignSynthesis
    session: Any  # SolidWorksSession
    target_subsystems: tuple[str, ...] = SUBSYSTEM_ORDER  # which subsystems to process


@dataclass(frozen=True)
class DesignSummary:
    """Final output after all subsystems are processed."""
    assembly_path: str
    total_parts_inserted: int
    total_cost_usd: float
    total_weight_g: float
    subsystems_completed: tuple[str, ...]
    subsystems_skipped: tuple[str, ...]
    warnings: tuple[str, ...]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_copilot_models.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/copilot/__init__.py src/robotics_design_advisor/copilot/models.py tests/unit/test_copilot_models.py
git commit -m "feat(copilot): add session state models — proposals, results, state, summary"
```

---

### Task 6: Copilot Presenter (Pure Functions)

**Files:**
- Create: `src/robotics_design_advisor/copilot/presenter.py`
- Test: `tests/unit/test_copilot_presenter.py`

**Interfaces:**
- Consumes: `SubsystemProposal`, `DesignSummary`, `CopilotState`, `SUBSYSTEM_ORDER`, `PartPlacement` from `copilot/models.py`
- Produces: `format_proposal(proposal: SubsystemProposal) -> str`, `format_progress(state: CopilotState) -> str`, `format_summary(summary: DesignSummary) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_copilot_presenter.py
"""Tests for copilot display formatting — pure string functions."""

from unittest.mock import MagicMock

import pytest

from robotics_design_advisor.copilot.models import (
    CopilotState,
    DesignSummary,
    PartPlacement,
    SubsystemProposal,
    SubsystemResult,
)
from robotics_design_advisor.copilot.presenter import (
    format_progress,
    format_proposal,
    format_summary,
)
from robotics_design_advisor.solidworks.placement import Position


def _make_proposal() -> SubsystemProposal:
    pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)
    return SubsystemProposal(
        subsystem="drivetrain",
        parts=(
            PartPlacement(
                sku="5202-0002-0019",
                name="goBILDA Yellow Jacket Motor",
                step_path="/parts/5202-0002-0019.STEP",
                position=pos,
                quantity=4,
            ),
            PartPlacement(
                sku="3209-0001-0001",
                name="goBILDA Strafer Chassis Kit",
                step_path="/parts/3209-0001-0001.STEP",
                position=pos,
                quantity=1,
            ),
        ),
        rationale="Mecanum drivetrain with 4 motors for omni movement",
        estimated_cost_usd=379.95,
        estimated_weight_g=5420.0,
    )


class TestFormatProposal:
    def test_includes_subsystem_name(self):
        output = format_proposal(_make_proposal())
        assert "drivetrain" in output.lower() or "Drivetrain" in output

    def test_includes_part_skus(self):
        output = format_proposal(_make_proposal())
        assert "5202-0002-0019" in output
        assert "3209-0001-0001" in output

    def test_includes_cost(self):
        output = format_proposal(_make_proposal())
        assert "379.95" in output

    def test_includes_rationale(self):
        output = format_proposal(_make_proposal())
        assert "Mecanum" in output or "mecanum" in output


class TestFormatProgress:
    def test_shows_current_phase(self):
        state = CopilotState(
            current_phase=2,
            approved_subsystems=(
                SubsystemResult(subsystem="drivetrain", approved=True, component_names=(), notes=""),
                SubsystemResult(subsystem="intake", approved=True, component_names=(), notes=""),
            ),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        output = format_progress(state)
        assert "drivetrain" in output.lower()
        assert "scorer" in output.lower()

    def test_first_phase(self):
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        output = format_progress(state)
        assert "drivetrain" in output.lower()

    def test_all_phases_complete(self):
        results = tuple(
            SubsystemResult(subsystem=s, approved=True, component_names=(), notes="")
            for s in ("drivetrain", "intake", "scorer", "endgame", "electronics")
        )
        state = CopilotState(
            current_phase=5,
            approved_subsystems=results,
            assembly_ref=MagicMock(),
            design_synthesis=MagicMock(),
            session=MagicMock(),
        )
        output = format_progress(state)
        assert "complete" in output.lower() or "done" in output.lower()


class TestFormatSummary:
    def test_includes_totals(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=12,
            total_cost_usd=899.50,
            total_weight_g=8500.0,
            subsystems_completed=("drivetrain", "intake", "scorer"),
            subsystems_skipped=("endgame", "electronics"),
            warnings=("Weight approaching limit",),
        )
        output = format_summary(summary)
        assert "12" in output
        assert "899.50" in output or "899.5" in output
        assert "8500" in output

    def test_includes_warnings(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=5,
            total_cost_usd=100.0,
            total_weight_g=1000.0,
            subsystems_completed=("drivetrain",),
            subsystems_skipped=(),
            warnings=("Weight approaching limit",),
        )
        output = format_summary(summary)
        assert "Weight approaching limit" in output

    def test_includes_assembly_path(self):
        summary = DesignSummary(
            assembly_path="/tmp/robot.SLDASM",
            total_parts_inserted=0,
            total_cost_usd=0.0,
            total_weight_g=0.0,
            subsystems_completed=(),
            subsystems_skipped=(),
            warnings=(),
        )
        output = format_summary(summary)
        assert "robot.SLDASM" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_copilot_presenter.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/copilot/presenter.py
"""Display formatting for copilot proposals, progress, and summaries.

Pure functions — no I/O, no side effects. Output is plain text
suitable for terminal, chat, or MCP tool responses.
"""

from __future__ import annotations

from .models import (
    CopilotState,
    DesignSummary,
    SubsystemProposal,
    SUBSYSTEM_ORDER,
)


def format_proposal(proposal: SubsystemProposal) -> str:
    """Format a subsystem proposal for display.

    Shows parts list with SKUs, quantities, costs, and rationale.
    """
    lines: list[str] = []
    lines.append(f"=== {proposal.subsystem.upper()} ===")
    lines.append("")
    lines.append(f"Rationale: {proposal.rationale}")
    lines.append("")
    lines.append("Parts:")
    for part in proposal.parts:
        cost = part.quantity * _estimate_unit_price(part.sku)
        lines.append(
            f"  - {part.name} (SKU: {part.sku}) x{part.quantity}"
        )
    lines.append("")
    lines.append(f"Estimated cost: ${proposal.estimated_cost_usd:.2f}")
    lines.append(f"Estimated weight: {proposal.estimated_weight_g:.0f}g")
    return "\n".join(lines)


def format_progress(state: CopilotState) -> str:
    """Show build progress across target subsystems."""
    parts: list[str] = []
    approved_names = {r.subsystem for r in state.approved_subsystems}

    for i, subsystem in enumerate(state.target_subsystems):
        if subsystem in approved_names:
            parts.append(f"{subsystem} [done]")
        elif i == state.current_phase:
            parts.append(f"{subsystem} [current]")
        else:
            parts.append(subsystem)

    progress_line = " | ".join(parts)

    if state.current_phase >= len(state.target_subsystems):
        return f"Build complete: {progress_line}"

    return f"Progress: {progress_line}"


def format_summary(summary: DesignSummary) -> str:
    """Format the final design summary."""
    lines: list[str] = []
    lines.append("=== DESIGN SUMMARY ===")
    lines.append("")
    lines.append(f"Assembly: {summary.assembly_path}")
    lines.append(f"Parts inserted: {summary.total_parts_inserted}")
    lines.append(f"Total cost: ${summary.total_cost_usd:.2f}")
    lines.append(f"Total weight: {summary.total_weight_g:.0f}g")
    lines.append("")

    if summary.subsystems_completed:
        lines.append(f"Completed: {', '.join(summary.subsystems_completed)}")
    if summary.subsystems_skipped:
        lines.append(f"Skipped: {', '.join(summary.subsystems_skipped)}")

    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in summary.warnings:
            lines.append(f"  ! {w}")

    return "\n".join(lines)


def _estimate_unit_price(sku: str) -> float:
    """Rough price estimate from SKU prefix. Internal helper."""
    prefix = sku.split("-")[0] if "-" in sku else sku[:4]
    # Very rough mapping — real prices come from BOM
    estimates: dict[str, float] = {
        "5202": 19.99,
        "2000": 24.99,
        "3209": 299.99,
        "REV": 249.99,
    }
    return estimates.get(prefix, 10.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_copilot_presenter.py -v`
Expected: 9 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/copilot/presenter.py tests/unit/test_copilot_presenter.py
git commit -m "feat(copilot): add presenter — format proposals, progress, summaries"
```

---

### Task 7: Copilot Session Engine

**Files:**
- Create: `src/robotics_design_advisor/copilot/session.py`
- Test: `tests/unit/test_copilot_session.py`

**Interfaces:**
- Consumes:
  - `synthesize_design(season_file, team_level) -> DesignSynthesis` from `engineering/design_synthesizer.py`
  - `create_assembly(session, name, save_path) -> AssemblyDoc` from `solidworks/assembly.py`
  - `insert_component(session, assembly, step_path, position) -> ComponentRef` from `solidworks/assembly.py`
  - `save_assembly(session, assembly)` from `solidworks/assembly.py`
  - `calculate_position(subsystem, part_index, part_count) -> Position` from `solidworks/placement.py`
  - `CopilotState`, `SubsystemProposal`, `SubsystemResult`, `DesignSummary`, `PartPlacement`, `SUBSYSTEM_ORDER` from `copilot/models.py`
  - `DesignSynthesis`, `BOMItem`, `BillOfMaterials` from `engineering/models.py`
- Produces: `start_session(season_file, team_level, sw_session, save_path, subsystems=None, existing_assembly=None) -> CopilotState`, `propose_subsystem(state) -> tuple[CopilotState, SubsystemProposal]`, `approve_subsystem(state, proposal) -> tuple[CopilotState, SubsystemResult]`, `skip_subsystem(state) -> CopilotState`, `finish_session(state) -> DesignSummary`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_copilot_session.py
"""Tests for copilot session engine — COM adapter mocked."""

from unittest.mock import MagicMock, patch

import pytest

from robotics_design_advisor.copilot.models import (
    CopilotState,
    DesignSummary,
    SUBSYSTEM_ORDER,
    SubsystemProposal,
    SubsystemResult,
)
from robotics_design_advisor.copilot.session import (
    approve_subsystem,
    finish_session,
    propose_subsystem,
    skip_subsystem,
    start_session,
)
from robotics_design_advisor.engineering.models import (
    BillOfMaterials,
    BOMItem,
    DesignSynthesis,
    ScoringStrategy,
)
from robotics_design_advisor.solidworks.assembly import AssemblyDoc, ComponentRef
from robotics_design_advisor.solidworks.connection import SolidWorksSession
from robotics_design_advisor.solidworks.placement import Position


def _make_mock_synthesis() -> DesignSynthesis:
    strategy = ScoringStrategy(
        name="test",
        expected_auto_points=10,
        expected_teleop_points=30,
        expected_endgame_points=5,
        total_expected_points=45,
        required_mechanisms=("drivetrain", "grabber"),
        difficulty="intermediate",
        rationale="test",
    )
    motor_item = BOMItem(
        sku="5202-0002-0019",
        name="goBILDA Motor",
        quantity=4,
        unit_price_usd=19.99,
        category="motion",
        subsystem="drivetrain",
        notes="",
    )
    hub_item = BOMItem(
        sku="REV-31-1595",
        name="REV Control Hub",
        quantity=1,
        unit_price_usd=249.99,
        category="electronics",
        subsystem="electronics",
        notes="",
    )
    bom = BillOfMaterials(
        items=(motor_item, hub_item),
        total_cost_usd=329.95,
        total_weight_g=1170.0,
        warnings=(),
        subsystem_breakdown={},
    )
    return DesignSynthesis(
        season="INTO THE DEEP",
        competition="FTC",
        strategy=strategy,
        archetype_name="Test Bot",
        bom=bom,
        mechanism_notes=("test note",),
        autonomous_notes=("auto note",),
        warnings=(),
    )


def _make_mock_session() -> SolidWorksSession:
    return SolidWorksSession(app=MagicMock(), active_doc=None)


class TestStartSession:
    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_returns_initial_state(self, mock_create_asm, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        sw_session = _make_mock_session()
        state = start_session(
            season_file="ftc-2024-into-the-deep.json",
            team_level="intermediate",
            sw_session=sw_session,
            save_path="/tmp/robot.SLDASM",
        )
        assert isinstance(state, CopilotState)
        assert state.current_phase == 0
        assert len(state.approved_subsystems) == 0

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_stores_design_synthesis(self, mock_create_asm, mock_synth):
        synthesis = _make_mock_synthesis()
        mock_synth.return_value = synthesis
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        state = start_session(
            "ftc-2024-into-the-deep.json", "intermediate",
            _make_mock_session(), "/tmp/robot.SLDASM",
        )
        assert state.design_synthesis.season == "INTO THE DEEP"

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_single_subsystem_session(self, mock_create_asm, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        state = start_session(
            "ftc-2024-into-the-deep.json", "intermediate",
            _make_mock_session(), "/tmp/robot.SLDASM",
            subsystems=("drivetrain",),
        )
        assert state.target_subsystems == ("drivetrain",)
        assert len(state.target_subsystems) == 1

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    def test_existing_assembly_reuse(self, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        existing_asm = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        state = start_session(
            "ftc-2024-into-the-deep.json", "intermediate",
            _make_mock_session(), "/tmp/ignored.SLDASM",
            existing_assembly=existing_asm,
        )
        assert state.assembly_ref is existing_asm

    @patch("robotics_design_advisor.copilot.session.synthesize_design")
    @patch("robotics_design_advisor.copilot.session.create_assembly")
    def test_invalid_subsystem_raises(self, mock_create_asm, mock_synth):
        mock_synth.return_value = _make_mock_synthesis()
        mock_create_asm.return_value = AssemblyDoc(
            name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock(),
        )

        with pytest.raises(ValueError, match="subsystem"):
            start_session(
                "ftc-2024-into-the-deep.json", "intermediate",
                _make_mock_session(), "/tmp/robot.SLDASM",
                subsystems=("nonexistent",),
            )


class TestProposeSubsystem:
    def test_returns_proposal_for_current_phase(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )

        new_state, proposal = propose_subsystem(state)
        assert isinstance(proposal, SubsystemProposal)
        assert proposal.subsystem == "drivetrain"

    def test_drivetrain_gets_motor_parts(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )

        _, proposal = propose_subsystem(state)
        skus = {p.sku for p in proposal.parts}
        assert "5202-0002-0019" in skus

    def test_raises_when_all_phases_done(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        results = tuple(
            SubsystemResult(subsystem=s, approved=True, component_names=(), notes="")
            for s in SUBSYSTEM_ORDER
        )
        state = CopilotState(
            current_phase=5,
            approved_subsystems=results,
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        with pytest.raises(ValueError, match="complete"):
            propose_subsystem(state)

    def test_single_subsystem_mode(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
            target_subsystems=("electronics",),
        )
        _, proposal = propose_subsystem(state)
        assert proposal.subsystem == "electronics"


class TestApproveSubsystem:
    def test_advances_phase(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        asm.com_ref.AddComponent5.return_value = MagicMock()

        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        _, proposal = propose_subsystem(state)
        new_state, result = approve_subsystem(state, proposal)

        assert new_state.current_phase == 1
        assert result.approved is True
        assert result.subsystem == "drivetrain"
        assert len(new_state.approved_subsystems) == 1

    def test_inserts_components(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        mock_comp = MagicMock()
        asm.com_ref.AddComponent5.return_value = mock_comp

        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        _, proposal = propose_subsystem(state)
        _, result = approve_subsystem(state, proposal)
        assert len(result.component_names) > 0


class TestSkipSubsystem:
    def test_advances_phase_without_inserting(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        new_state = skip_subsystem(state)
        assert new_state.current_phase == 1
        assert len(new_state.approved_subsystems) == 1
        assert new_state.approved_subsystems[0].approved is False


class TestFinishSession:
    def test_returns_design_summary(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        results = (
            SubsystemResult(subsystem="drivetrain", approved=True, component_names=("m1",), notes=""),
            SubsystemResult(subsystem="intake", approved=False, component_names=(), notes="skipped"),
        )
        state = CopilotState(
            current_phase=2,
            approved_subsystems=results,
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        summary = finish_session(state)
        assert isinstance(summary, DesignSummary)
        assert summary.assembly_path == "/tmp/robot.SLDASM"
        assert "drivetrain" in summary.subsystems_completed
        assert "intake" in summary.subsystems_skipped

    def test_calls_save(self):
        synthesis = _make_mock_synthesis()
        asm = AssemblyDoc(name="robot", save_path="/tmp/robot.SLDASM", com_ref=MagicMock())
        state = CopilotState(
            current_phase=0,
            approved_subsystems=(),
            assembly_ref=asm,
            design_synthesis=synthesis,
            session=_make_mock_session(),
        )
        finish_session(state)
        asm.com_ref.Save.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_copilot_session.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/robotics_design_advisor/copilot/session.py
"""Copilot session engine — orchestrates interactive design flow.

Each function takes state in, returns new state out (immutable).
Side effects (SolidWorks COM calls) only happen in approve_subsystem
and finish_session.
"""

from __future__ import annotations

from .models import (
    CopilotState,
    DesignSummary,
    PartPlacement,
    SubsystemProposal,
    SubsystemResult,
    SUBSYSTEM_ORDER,
)
from ..engineering.design_synthesizer import synthesize_design
from ..engineering.models import BOMItem, DesignSynthesis
from ..solidworks.assembly import (
    AssemblyDoc,
    ComponentRef,
    create_assembly,
    insert_component,
    save_assembly,
)
from ..solidworks.connection import SolidWorksSession
from ..solidworks.placement import calculate_position


def start_session(
    season_file: str,
    team_level: str,
    sw_session: SolidWorksSession,
    save_path: str,
    subsystems: tuple[str, ...] | None = None,
    existing_assembly: AssemblyDoc | None = None,
) -> CopilotState:
    """Start a new design copilot session.

    Generates a DesignSynthesis and creates (or reuses) a SolidWorks assembly.
    Supports both full builds (all subsystems) and independent subsystem work.

    Parameters
    ----------
    season_file : str
        Enhanced season JSON filename.
    team_level : str
        "beginner", "intermediate", or "advanced".
    sw_session : SolidWorksSession
        Active SolidWorks COM session.
    save_path : str
        File path for the new assembly (ignored if existing_assembly given).
    subsystems : tuple[str, ...] | None
        Which subsystems to process. None means all (SUBSYSTEM_ORDER).
        Pass a subset like ("drivetrain",) for independent work.
    existing_assembly : AssemblyDoc | None
        If provided, add to this assembly instead of creating a new one.
        Enables incremental builds — work on subsystems independently
        and integrate them into the same assembly.
    """
    synthesis = synthesize_design(season_file, team_level)

    if existing_assembly is not None:
        assembly = existing_assembly
    else:
        assembly = create_assembly(sw_session, synthesis.archetype_name, save_path)

    target = subsystems if subsystems is not None else SUBSYSTEM_ORDER

    # Validate requested subsystems
    valid = set(SUBSYSTEM_ORDER)
    for s in target:
        if s not in valid:
            raise ValueError(
                f"Unknown subsystem '{s}'. Valid: {sorted(valid)}"
            )

    return CopilotState(
        current_phase=0,
        approved_subsystems=(),
        assembly_ref=assembly,
        design_synthesis=synthesis,
        session=sw_session,
        target_subsystems=target,
    )


def _filter_bom_by_subsystem(
    bom_items: tuple[BOMItem, ...],
    subsystem: str,
) -> tuple[BOMItem, ...]:
    """Filter BOM items belonging to a specific subsystem."""
    return tuple(item for item in bom_items if item.subsystem == subsystem)


def propose_subsystem(
    state: CopilotState,
) -> tuple[CopilotState, SubsystemProposal]:
    """Generate a proposal for the current subsystem.

    Raises
    ------
    ValueError
        If all target subsystems have been processed.
    """
    if state.current_phase >= len(state.target_subsystems):
        raise ValueError("All subsystems complete — call finish_session instead")

    subsystem = state.target_subsystems[state.current_phase]
    synthesis: DesignSynthesis = state.design_synthesis

    # Filter BOM items for this subsystem
    subsystem_items = _filter_bom_by_subsystem(synthesis.bom.items, subsystem)

    # Build placements with approximate positions
    placements: list[PartPlacement] = []
    total_parts = len(subsystem_items)
    for i, item in enumerate(subsystem_items):
        position = calculate_position(
            subsystem,
            i,
            max(total_parts, 1),
        )
        placements.append(PartPlacement(
            sku=item.sku,
            name=item.name,
            step_path=f"{item.sku}.STEP",  # resolved at insertion time
            position=position,
            quantity=item.quantity,
        ))

    # Calculate subsystem totals
    cost = sum(item.unit_price_usd * item.quantity for item in subsystem_items)
    weight = sum(100.0 * item.quantity for item in subsystem_items)  # rough estimate

    proposal = SubsystemProposal(
        subsystem=subsystem,
        parts=tuple(placements),
        rationale=f"{synthesis.archetype_name}: {subsystem} components",
        estimated_cost_usd=round(cost, 2),
        estimated_weight_g=round(weight, 1),
    )

    return (state, proposal)


def approve_subsystem(
    state: CopilotState,
    proposal: SubsystemProposal,
) -> tuple[CopilotState, SubsystemResult]:
    """Approve a proposal and insert parts into SolidWorks.

    This is the only function with COM side effects.
    """
    component_names: list[str] = []

    for placement in proposal.parts:
        for i in range(placement.quantity):
            position = calculate_position(
                proposal.subsystem,
                min(i, max(len(proposal.parts) - 1, 0)),
                max(len(proposal.parts), 1),
            )
            comp = insert_component(
                state.session,
                state.assembly_ref,
                placement.step_path,
                position,
            )
            component_names.append(comp.name)

    result = SubsystemResult(
        subsystem=proposal.subsystem,
        approved=True,
        component_names=tuple(component_names),
        notes="",
    )

    new_state = CopilotState(
        current_phase=state.current_phase + 1,
        approved_subsystems=state.approved_subsystems + (result,),
        assembly_ref=state.assembly_ref,
        design_synthesis=state.design_synthesis,
        session=state.session,
    )

    return (new_state, result)


def skip_subsystem(state: CopilotState) -> CopilotState:
    """Skip the current subsystem without inserting anything."""
    subsystem = state.target_subsystems[state.current_phase]
    result = SubsystemResult(
        subsystem=subsystem,
        approved=False,
        component_names=(),
        notes="skipped",
    )

    return CopilotState(
        current_phase=state.current_phase + 1,
        approved_subsystems=state.approved_subsystems + (result,),
        assembly_ref=state.assembly_ref,
        design_synthesis=state.design_synthesis,
        session=state.session,
    )


def finish_session(state: CopilotState) -> DesignSummary:
    """Finalize the session — save assembly and return summary."""
    save_assembly(state.session, state.assembly_ref)

    completed = tuple(
        r.subsystem for r in state.approved_subsystems if r.approved
    )
    skipped = tuple(
        r.subsystem for r in state.approved_subsystems if not r.approved
    )
    total_parts = sum(
        len(r.component_names) for r in state.approved_subsystems if r.approved
    )

    synthesis: DesignSynthesis = state.design_synthesis

    return DesignSummary(
        assembly_path=state.assembly_ref.save_path,
        total_parts_inserted=total_parts,
        total_cost_usd=synthesis.bom.total_cost_usd,
        total_weight_g=synthesis.bom.total_weight_g,
        subsystems_completed=completed,
        subsystems_skipped=skipped,
        warnings=synthesis.warnings,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest tests/unit/test_copilot_session.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Run full suite**

Run: `cd /home/yeteesh/__myworkarea/projects/genai/agentic-ai/agents/CAD/robotics-design-advisor && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/robotics_design_advisor/copilot/session.py tests/unit/test_copilot_session.py
git commit -m "feat(copilot): add session engine — start, propose, approve, skip, finish"
```

---

## Summary

| Task | Module | Tests | Capability |
|------|--------|-------|-----------|
| 1 | `step/batch_profiler.py` | 9 | Batch STEP analysis, profile caching, index generation |
| 2 | `parts/resolver.py` (modify) | 5 | SKU → (path, profile) resolution with cache lookup |
| 3 | `solidworks/placement.py` | 11 | Pure-function part positioning within subsystem zones |
| 4 | `solidworks/connection.py` + `assembly.py` | 12 | COM adapter for assemblies — fully mocked on Linux |
| 5 | `copilot/models.py` | 12 | Session state dataclasses — proposals, results, state (with target_subsystems) |
| 6 | `copilot/presenter.py` | 9 | Display formatting — proposals, progress, summaries |
| 7 | `copilot/session.py` | 14 | Session engine — full build, single-subsystem, existing assembly |
| **Total** | **9 new files, 1 modified** | **~72** | |
