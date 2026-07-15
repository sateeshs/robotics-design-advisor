# SolidWorks Integration: Design Copilot

## Overview

A live interactive design copilot that takes the robotics design advisor's outputs (season analysis, scoring strategies, archetypes, BOM) and incrementally builds a SolidWorks assembly. The copilot recommends each subsystem one at a time (drivetrain, intake, scorer, endgame, electronics), the user approves or adjusts, and approved parts are inserted into the SolidWorks assembly with approximate positioning. The user can refine placement in SolidWorks between subsystems.

## Deployment Model

Both the robotics-design-advisor and SolidWorks run on the same Windows machine. The advisor launches SolidWorks COM automation directly — no network, no remote server. All new code lives in the `robotics-design-advisor` repository (never in the Solidworks-MCP fork).

## Architecture

```
+---------------------------------------------+
|  Copilot Orchestrator                       |
|  (interactive subsystem-by-subsystem flow)  |
+---------------------------------------------+
|  SolidWorks COM Adapter                     |
|  (create assembly, insert, position, mate)  |
+---------------------------------------------+
|  Part Profile Cache                         |
|  (batch STEP analysis -> indexed JSON)      |
+---------------------------------------------+
|  Existing modules (design_synthesizer,      |
|  parts/, step/, BOM, archetypes)            |
+---------------------------------------------+
```

**Data flow:** User provides season + team level -> `DesignSynthesis` is generated -> copilot presents subsystem recommendations one by one -> on approval, COM adapter inserts goBILDA parts from the BOM into SolidWorks -> parts placed at approximate coordinates by subsystem zone -> user adjusts in SolidWorks -> next subsystem.

## Layer 1: Part Profile Cache (Batch STEP Analysis)

### Purpose

Batch-process all 910 goBILDA STEP files through the existing `step/profile_builder.py` pipeline and cache results as JSON. This provides the indexed part catalog that the copilot uses for SKU resolution, geometry lookup, and future mate suggestions.

### New File

`src/robotics_design_advisor/step/batch_profiler.py`

### Behavior

- Scans two goBILDA STEP directories for `.STEP` files:
  - `/media/yeteesh/Data/__MyWorkArea/__myfiles/robotics/goBILDA-CAD-STEP-with-images/`
  - Additional directories passed as arguments to the batch function (no global config)
- Runs each file through `profile_builder.build_profile()` (CadQuery-based geometry analysis)
- Writes individual profile JSON files to `data/profiles/` (gitignored)
- Generates a catalog index at `data/profiles/_index.json` mapping SKU to profile path + basic metadata (category, bounding box dimensions, weight estimate)
- Idempotent: skips files that already have a cached profile (checks by filename + file modification time)
- Logs failed analyses to `data/profiles/_failures.json` with error messages
- SKU extracted from STEP filename (e.g., `1101-0001-0008.STEP` -> SKU `1101-0001-0008`)

### Runtime

One-time batch job. ~2-5 seconds per file, 910 files = ~30-75 minutes. Run once, cache reused indefinitely.

### Integration with Existing Code

- The existing `SkuResolver` in `parts/resolver.py` gets a small update: a new method `resolve_with_profile(sku)` that returns both the STEP file path and the cached profile data. Returns `(path, None)` if no cached profile exists for that SKU.
- The existing `PartsCatalog` in `parts/query.py` can optionally load from the index for enriched search results

### Testing

- Unit tests with 2-3 real STEP files from the goBILDA set
- Test idempotent skip behavior (profile already cached)
- Test failure handling (corrupt or unsupported STEP file)
- Test index generation (correct SKU mapping, metadata extraction)

## Layer 2: SolidWorks COM Adapter

### Purpose

Wrap SolidWorks COM automation for assembly-level operations. This is the bridge between the advisor's design outputs and actual CAD model creation.

### New Package

`src/robotics_design_advisor/solidworks/`

### Files

#### `solidworks/connection.py` — COM Lifecycle

- `connect() -> SolidWorksSession`: Attaches to running SolidWorks instance via `win32com.client.Dispatch("SldWorks.Application")`. Raises `ConnectionError` if SolidWorks is not running.
- `disconnect(session) -> None`: Releases COM references cleanly.
- `SolidWorksSession`: Frozen dataclass holding the COM application reference and active document reference.
- Platform guard: raises `RuntimeError` on non-Windows platforms with a clear message.

#### `solidworks/assembly.py` — Assembly Operations

- `create_assembly(session, name, save_path) -> AssemblyDoc`: Creates a new empty assembly document in SolidWorks and saves it to the specified path.
- `insert_component(session, assembly, step_path, position, rotation) -> ComponentRef`: Inserts a STEP file as a component into the assembly at the given 3D position and rotation.
- `add_mate(session, assembly, comp_a, comp_b, mate_type, params) -> MateRef`: Adds a mate constraint between two components. Supported mate types: `coincident`, `concentric`, `distance`.
- `save_assembly(session, assembly) -> None`: Saves the current assembly state.
- `list_components(session, assembly) -> tuple[ComponentRef, ...]`: Returns all components currently in the assembly.

**Data models (frozen dataclasses):**
- `AssemblyDoc`: name, save_path, COM reference
- `ComponentRef`: name, step_path, sku, position, com_reference
- `MateRef`: mate_type, component_a_name, component_b_name, com_reference

#### `solidworks/placement.py` — Approximate Positioning (Pure Functions)

- `SUBSYSTEM_ZONES`: Dict mapping subsystem names to 3D bounding boxes within a 457x457x457mm robot envelope (FTC size constraint):
  - `drivetrain`: bottom layer, full footprint (y=0-50mm)
  - `intake`: front zone (x=300-457mm, y=50-200mm)
  - `scorer`: center-top zone (x=100-350mm, y=200-400mm)
  - `endgame`: rear-top zone (x=0-150mm, y=200-400mm)
  - `electronics`: rear-center zone (x=0-200mm, y=50-200mm)
- `calculate_position(subsystem, part_index, part_count) -> Position`: Distributes parts evenly within the subsystem's zone. Returns a `Position` frozen dataclass.
- `Position`: Frozen dataclass with `x`, `y`, `z` (mm) and `rx`, `ry`, `rz` (degrees).

**Design for upgrade:** `placement.py` has a clear interface (`subsystem + index -> Position`). When profile-driven mating is added later, it replaces this module's logic without changing the callers in `assembly.py` or the copilot.

### Testing Strategy

- `placement.py`: Pure math, fully testable on Linux. Test zone boundaries, even distribution, edge cases (single part, many parts).
- `connection.py` and `assembly.py`: Tests mock the COM interface via a `FakeSolidWorks` class that records method calls without needing a real SolidWorks instance. Verifies correct call sequences, error handling, and data model construction.
- Manual integration tests on Windows documented in a `tests/integration/README.md` with step-by-step instructions.

## Layer 3: Copilot Orchestrator

### Purpose

Drives the interactive step-by-step design experience. Manages session state, generates subsystem recommendations from the `DesignSynthesis`, and coordinates SolidWorks assembly building.

### New Package

`src/robotics_design_advisor/copilot/`

### Files

#### `copilot/models.py` — Session State

Frozen dataclasses for copilot state:

- `SubsystemProposal`: subsystem name, recommended parts (list of BOM items with resolved STEP paths), archetype rationale, alternative part options, estimated cost and weight for this subsystem.
- `SubsystemResult`: approved parts, component refs (from SolidWorks insertion), user notes.
- `CopilotState`: current phase (which subsystem is active), approved subsystems (tuple of SubsystemResult), pending subsystem (SubsystemProposal or None), assembly reference, design synthesis reference. Phases follow build order: `drivetrain -> intake -> scorer -> endgame -> electronics`.
- `DesignSummary`: final output after all subsystems — total parts inserted, total cost, total weight, warnings, assembly file path.

#### `copilot/session.py` — Copilot Engine

The core orchestration logic. Each function takes state in, returns new state out (immutable). Side effects (SolidWorks COM calls) only happen in `approve_subsystem`.

- `start_session(season_file, team_level, solidworks_session) -> CopilotState`: Runs `synthesize_design()`, creates a new assembly in SolidWorks via the COM adapter, returns initial state with first phase set to `drivetrain`.
- `propose_subsystem(state) -> tuple[CopilotState, SubsystemProposal]`: Generates the next subsystem recommendation. Filters BOM items by the current subsystem, resolves SKUs to STEP file paths via `SkuResolver`, calculates approximate positions via `placement.py`.
- `approve_subsystem(state, proposal) -> tuple[CopilotState, SubsystemResult]`: Inserts approved parts into the SolidWorks assembly via the COM adapter. Records component references. Advances state to the next subsystem phase.
- `skip_subsystem(state) -> CopilotState`: Skips the current subsystem without inserting anything. Advances to next phase.
- `finish_session(state) -> DesignSummary`: Saves the assembly, computes totals (cost, weight, part count), collects warnings, returns the final summary.

**Subsystem build order:** drivetrain -> intake -> scorer -> endgame -> electronics. This follows physical build logic: chassis and drivetrain first (everything mounts to it), then mechanisms in order of structural dependency, then wiring last.

#### `copilot/presenter.py` — Display Formatting (Pure Functions)

- `format_proposal(proposal) -> str`: Renders a subsystem proposal as readable text — parts list with SKUs, quantities, costs, rationale, and alternatives.
- `format_progress(state) -> str`: Shows build progress indicator (e.g., `"Drivetrain [done] | Intake [done] | Scorer [current] | Endgame | Electronics"`).
- `format_summary(summary) -> str`: Renders the final design summary — total parts, cost, weight, warnings, assembly file location.

### Interaction Model

The copilot exposes functions, not a UI. Any interface (MCP tool, CLI, chat) can drive it:

```
1. state = start_session("ftc-2024-into-the-deep.json", "intermediate", sw_session)
2. loop until all subsystems processed:
   a. state, proposal = propose_subsystem(state)
   b. display format_proposal(proposal) to user
   c. user decides: approve / skip / adjust
   d. if approve: state, result = approve_subsystem(state, proposal)
   e. if skip: state = skip_subsystem(state)
3. summary = finish_session(state)
4. display format_summary(summary)
```

### Testing

- `models.py`: Creation and immutability tests (same pattern as Phase 4C models).
- `session.py`: Mock the SolidWorks COM adapter. Test the full propose -> approve -> advance cycle. Test skip behavior. Test finish with partial approvals.
- `presenter.py`: Pure string formatting, test exact output for known inputs.
- Full integration test scenario documented: start with INTO THE DEEP season, walk through all 5 subsystems, verify assembly file is created.

## Dependencies

### Python Packages

- `pywin32` (win32com) — SolidWorks COM automation. Windows-only. Already a dependency of the Solidworks-MCP fork.
- `cadquery` — STEP geometry analysis. Already used by `step/analyzer.py`.
- No new external dependencies needed.

### External Requirements

- SolidWorks 2024 or 2025 installed and running on the Windows machine
- goBILDA STEP files accessible on the local filesystem
- Part profile cache generated (one-time batch job before first copilot session)

## File Structure Summary

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

data/
  profiles/                    # GENERATED (gitignored)
    _index.json                # catalog index
    _failures.json             # failed analyses
    1101-0001-0008.json        # individual profiles
    ...

tests/
  unit/
    test_batch_profiler.py
    test_solidworks_connection.py
    test_solidworks_assembly.py
    test_placement.py
    test_copilot_models.py
    test_copilot_session.py
    test_copilot_presenter.py
  integration/
    README.md                  # manual Windows integration test instructions
```

## Global Constraints

- All dataclasses are `frozen=True` with `tuple` for sequences (immutability)
- All pure functions have no I/O, no side effects
- COM-dependent code is isolated in `solidworks/connection.py` and `solidworks/assembly.py` — everything else is testable on Linux
- Units: mm for length, degrees for angles, USD for cost, grams for weight
- Functions validate inputs and raise `ValueError` for invalid arguments
- Target: 80%+ test coverage (COM-mocked tests count)
- Profile cache is gitignored — generated artifacts, not source
- All new code goes in `robotics-design-advisor`, never in `Solidworks-MCP`

## Success Criteria

1. 910 goBILDA STEP files profiled with <5% failure rate
2. SolidWorks assembly created programmatically with parts inserted at approximate positions
3. User can walk through all 5 subsystems interactively (propose/approve/skip)
4. Assembly saves correctly and opens in SolidWorks with all parts visible
5. Full test suite passes on Linux (COM mocked), manual integration passes on Windows

## Future Upgrades (Out of Scope)

- Profile-driven mating (replace approximate placement with connection-point-based positioning)
- Real-time SolidWorks viewport sync (camera positioning, zoom-to-fit)
- Undo/rollback individual subsystem insertions
- Multi-season comparison (side-by-side assemblies)
- Export to STEP/STL from the copilot
