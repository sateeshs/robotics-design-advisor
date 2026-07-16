# Windows Integration Tests — SolidWorks Design Copilot

Manual integration tests for the SolidWorks COM adapter and copilot session engine.
These tests require a Windows machine with SolidWorks 2024/2025 installed.

## Prerequisites

- Windows 10/11
- SolidWorks 2024 or 2025 installed and running
- Python 3.10+ with `pywin32` installed (`pip install pywin32`)
- goBILDA STEP files accessible on the local filesystem
- Profile cache generated (run batch profiler first)

## Setup

```bash
# 1. Clone the repo and install
git clone git@github.com:sateeshs/robotics-design-advisor.git
cd robotics-design-advisor
pip install -e ".[dev]"

# 2. Install pywin32 (Windows-only)
pip install pywin32

# 3. Generate the profile cache (one-time, ~30-75 minutes)
python -c "
from robotics_design_advisor.step.batch_profiler import run_batch
import json
from pathlib import Path

categories = json.loads(
    (Path('src/robotics_design_advisor/step/sku_categories.json')).read_text()
)
result = run_batch(
    step_dirs=('C:/path/to/goBILDA-CAD-STEP-with-images',),
    output_dir='data/profiles',
    sku_categories=categories,
)
print(f'Profiled: {result.profiled}, Skipped: {result.skipped}, Failed: {result.failed}')
"
```

## Test 1: COM Connection

Verify SolidWorks COM connection works.

```python
from robotics_design_advisor.solidworks.connection import connect, disconnect

# SolidWorks must be running
session = connect()
print(f"Connected: {session.app is not None}")
print(f"Active doc: {session.active_doc}")
disconnect(session)
print("Disconnected successfully")
```

**Expected:**
- `Connected: True`
- `Active doc: None` (no document open)
- `Disconnected successfully`
- No exceptions

## Test 2: Create Empty Assembly

```python
import os
from robotics_design_advisor.solidworks.connection import connect, disconnect
from robotics_design_advisor.solidworks.assembly import create_assembly, save_assembly

session = connect()
save_path = os.path.expanduser("~/Desktop/test_robot.SLDASM")
asm = create_assembly(session, "test_robot", save_path)
save_assembly(session, asm)
print(f"Assembly created: {asm.name}")
print(f"Saved to: {asm.save_path}")
disconnect(session)
```

**Expected:**
- Assembly file created at `~/Desktop/test_robot.SLDASM`
- File opens in SolidWorks with an empty assembly
- No exceptions

**Cleanup:** Delete `test_robot.SLDASM` from Desktop after verifying.

## Test 3: Insert Single Component

```python
import os
from robotics_design_advisor.solidworks.connection import connect, disconnect
from robotics_design_advisor.solidworks.assembly import (
    create_assembly, insert_component, save_assembly,
)
from robotics_design_advisor.solidworks.placement import Position

session = connect()
save_path = os.path.expanduser("~/Desktop/test_insert.SLDASM")
asm = create_assembly(session, "test_insert", save_path)

# Use a known goBILDA STEP file
step_path = "C:/path/to/goBILDA-CAD-STEP-with-images/1101-0001-0008.STEP"
pos = Position(x=100.0, y=50.0, z=25.0, rx=0.0, ry=0.0, rz=0.0)

comp = insert_component(session, asm, step_path, pos)
print(f"Inserted: {comp.sku} at ({pos.x}, {pos.y}, {pos.z})mm")
print(f"Component name: {comp.name}")

save_assembly(session, asm)
disconnect(session)
```

**Expected:**
- STEP file imported into assembly
- Part visible in SolidWorks viewport at approximate position
- No exceptions

## Test 4: Insert Multiple Components (Placement Distribution)

```python
import os
from robotics_design_advisor.solidworks.connection import connect, disconnect
from robotics_design_advisor.solidworks.assembly import (
    create_assembly, insert_component, save_assembly,
)
from robotics_design_advisor.solidworks.placement import calculate_position

session = connect()
save_path = os.path.expanduser("~/Desktop/test_multi.SLDASM")
asm = create_assembly(session, "test_multi", save_path)

step_path = "C:/path/to/goBILDA-CAD-STEP-with-images/1101-0001-0008.STEP"

# Insert 4 copies distributed across the drivetrain zone
for i in range(4):
    pos = calculate_position("drivetrain", i, 4)
    comp = insert_component(session, asm, step_path, pos)
    print(f"  [{i}] {comp.sku} at ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})mm")

save_assembly(session, asm)
print("4 components inserted and distributed")
disconnect(session)
```

**Expected:**
- 4 copies of the same part inserted
- Parts spread along the x-axis within the drivetrain zone (0-457mm x, 0-457mm y, 0-50mm z)
- Parts are NOT stacked on top of each other
- No exceptions

## Test 5: Full Copilot Session (All Subsystems)

This is the end-to-end test for the interactive copilot flow.

```python
import os
from robotics_design_advisor.solidworks.connection import connect, disconnect
from robotics_design_advisor.copilot.session import (
    start_session, propose_subsystem, approve_subsystem,
    skip_subsystem, finish_session,
)
from robotics_design_advisor.copilot.presenter import (
    format_proposal, format_progress, format_summary,
)

session = connect()
save_path = os.path.expanduser("~/Desktop/test_copilot.SLDASM")

# Start session — generates DesignSynthesis + creates assembly
state = start_session(
    season_file="ftc-2024-into-the-deep.json",
    team_level="intermediate",
    sw_session=session,
    save_path=save_path,
)
print(f"Session started: {state.design_synthesis.archetype_name}")
print(format_progress(state))
print()

# Walk through each subsystem
while state.current_phase < len(state.target_subsystems):
    state, proposal = propose_subsystem(state)
    print(format_proposal(proposal))
    print()

    # Auto-approve for testing (in real use, user decides)
    response = input(f"Approve {proposal.subsystem}? [y/n/s(kip)] ").strip().lower()
    if response == "s":
        state = skip_subsystem(state)
        print(f"  Skipped {proposal.subsystem}")
    elif response == "n":
        state = skip_subsystem(state)
        print(f"  Declined {proposal.subsystem}")
    else:
        state, result = approve_subsystem(state, proposal)
        print(f"  Approved: {len(result.component_names)} components inserted")

    print(format_progress(state))
    print()

# Finish
summary = finish_session(state)
print(format_summary(summary))
disconnect(session)
```

**Expected:**
- Assembly created in SolidWorks
- 5 subsystem proposals presented in order: drivetrain, intake, scorer, endgame, electronics
- Approved subsystems have parts inserted into the assembly
- Skipped subsystems show as `[skipped]` in progress
- Assembly saved at the end
- Final summary shows correct totals

## Test 6: Single Subsystem Session

Test independent subsystem work.

```python
import os
from robotics_design_advisor.solidworks.connection import connect, disconnect
from robotics_design_advisor.copilot.session import (
    start_session, propose_subsystem, approve_subsystem, finish_session,
)
from robotics_design_advisor.copilot.presenter import format_progress, format_summary

session = connect()
save_path = os.path.expanduser("~/Desktop/test_single.SLDASM")

# Start session for drivetrain only
state = start_session(
    season_file="ftc-2024-into-the-deep.json",
    team_level="intermediate",
    sw_session=session,
    save_path=save_path,
    subsystems=("drivetrain",),
)
print(f"Target subsystems: {state.target_subsystems}")
print(format_progress(state))

# Propose and approve drivetrain
state, proposal = propose_subsystem(state)
state, result = approve_subsystem(state, proposal)
print(f"Inserted {len(result.component_names)} drivetrain components")

# Finish — should be done after 1 subsystem
summary = finish_session(state)
print(format_summary(summary))
disconnect(session)
```

**Expected:**
- Only drivetrain subsystem proposed
- Session completes after 1 subsystem (not 5)
- Assembly contains only drivetrain parts

## Test 7: Add to Existing Assembly

Test adding subsystems to an existing assembly incrementally.

```python
import os
from robotics_design_advisor.solidworks.connection import connect, disconnect
from robotics_design_advisor.solidworks.assembly import create_assembly
from robotics_design_advisor.copilot.session import (
    start_session, propose_subsystem, approve_subsystem, finish_session,
)

session = connect()
save_path = os.path.expanduser("~/Desktop/test_incremental.SLDASM")

# Create assembly and add drivetrain
asm = create_assembly(session, "incremental_robot", save_path)

state = start_session(
    season_file="ftc-2024-into-the-deep.json",
    team_level="intermediate",
    sw_session=session,
    save_path=save_path,
    subsystems=("drivetrain",),
    existing_assembly=asm,
)
state, proposal = propose_subsystem(state)
state, result = approve_subsystem(state, proposal)
summary1 = finish_session(state)
print(f"Round 1: {summary1.total_parts_inserted} parts")

# Later: add electronics to the SAME assembly
state2 = start_session(
    season_file="ftc-2024-into-the-deep.json",
    team_level="intermediate",
    sw_session=session,
    save_path=save_path,
    subsystems=("electronics",),
    existing_assembly=asm,
)
state2, proposal2 = propose_subsystem(state2)
state2, result2 = approve_subsystem(state2, proposal2)
summary2 = finish_session(state2)
print(f"Round 2: {summary2.total_parts_inserted} parts")
print("Assembly now contains both drivetrain and electronics")

disconnect(session)
```

**Expected:**
- Assembly created once, reused across two sessions
- Drivetrain parts inserted in first session
- Electronics parts added in second session (not replacing drivetrain)
- Both sets of parts visible in SolidWorks

## Troubleshooting

### SolidWorks not detected
- Ensure SolidWorks is running before calling `connect()`
- Check that `win32com` can find the COM registration: `python -c "import win32com.client; print(win32com.client.Dispatch('SldWorks.Application'))"`

### STEP file import fails
- Verify the STEP file path is absolute and uses forward slashes or raw strings
- Check SolidWorks can manually import the same STEP file (File > Open)

### Parts not visible
- Use View > Zoom to Fit in SolidWorks after insertion
- Check the FeatureManager tree for imported components

### COM errors
- Restart SolidWorks and try again
- Ensure no other COM clients are connected to SolidWorks
