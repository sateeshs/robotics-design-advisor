# Phase 3: STEP Intelligence Layer — Design Spec

## Purpose

Build a CadQuery-based pipeline that reads goBILDA STEP files and produces
the JSON part profiles consumed by the Parts Intelligence MCP server.

Currently the profile JSON files (e.g. `1120-0001-0288.json`) are hand-crafted.
This phase automates their generation from raw CAD geometry so the system can
scale to 900+ parts.

## Data Flow

```
STEP file (.STEP)
    │
    ▼
┌──────────────┐
│  analyzer.py │  Load shape, extract bounding box, volume, mass, faces
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ hole_detector.py │  Find cylindrical holes, measure diameters, detect grid patterns
└──────┬───────────┘
       │
       ▼
┌───────────────────────────┐
│ connection_classifier.py  │  Classify connections (bolt grid, shaft bore, motor mount),
│                           │  assign compatibility tags
└──────┬────────────────────┘
       │
       ▼
┌─────────────────────┐
│  profile_builder.py │  Assemble into PartProfile JSON, write to disk
└─────────────────────┘
```

Batch scripts orchestrate this across all 910 STEP files and build the
catalog/category indexes.

## Architecture

### New package: `src/robotics_design_advisor/step/`

| Module | Responsibility |
|--------|---------------|
| `__init__.py` | Package exports |
| `analyzer.py` | Core geometry extraction: load STEP, bounding box, volume, mass estimate, enumerate planar faces with normals/areas/centers |
| `hole_detector.py` | Detect cylindrical through-holes on faces, measure diameters, cluster into regular grid patterns (pitch detection), map to bolt sizes |
| `connection_classifier.py` | Classify each detected feature into a `ConnectionType`, assign `compatible_with` tags using goBILDA knowledge (8mm pitch → `gobilda_8mm_pattern`, 4.2mm hole → `M4_bolt`, 8mm D-bore → `REX_8mm_shaft`) |
| `profile_builder.py` | Orchestrate analyzer → hole_detector → classifier, assemble results into a `PartProfile` dict matching the existing JSON schema, write to disk |

### New: `scripts/`

| Script | Purpose |
|--------|---------|
| `analyze_gobilda.py` | CLI: batch-process a directory of STEP files → individual profile JSON files |
| `build_catalog.py` | CLI: read all profile JSONs → generate `catalog.json` + `categories.json` |

### Dependency

Add `cadquery` to `pyproject.toml` under a new `[project.optional-dependencies] step` group.

## Module Details

### analyzer.py

**Input:** Path to a `.STEP` file.

**Output:** `StepAnalysis` frozen dataclass:

```python
@dataclass(frozen=True)
class FaceInfo:
    face_id: str            # "face_0", "face_1", ...
    normal: tuple[float, float, float]
    area_mm2: float
    center: tuple[float, float, float]
    face_type: str          # "planar" | "cylindrical" | "conical" | "other"
    outer_wire_edge_count: int

@dataclass(frozen=True)
class StepAnalysis:
    bounding_box: tuple[float, float, float]  # (x, y, z) in mm
    volume_mm3: float
    center_of_mass: tuple[float, float, float]
    faces: tuple[FaceInfo, ...]
```

**Key logic:**
- `cadquery.importers.importStep(path)` to load
- `shape.BoundingBox()` for dimensions
- `shape.Volume()` for volume (convert to cm³ in profile_builder)
- Iterate `shape.Faces()`, classify each by surface type (plane/cylinder/cone)
- For planar faces: compute normal via `face.normalAt()`, area via `face.Area()`, center via `face.Center()`
- Mass estimated from volume × aluminum density (2.7 g/cm³)

### hole_detector.py

**Input:** `StepAnalysis` + the loaded CadQuery shape.

**Output:** `HoleDetection` frozen dataclass:

```python
@dataclass(frozen=True)
class DetectedHole:
    face_id: str          # ID of the parent planar face
    center: tuple[float, float, float]
    diameter_mm: float
    depth_mm: float       # 0 = through-hole
    hole_type: str        # "through" | "blind"

@dataclass(frozen=True)
class DetectedPattern:
    pattern_id: str
    face_ref: str
    holes: tuple[DetectedHole, ...]
    hole_diameter_mm: float
    pitch_x_mm: float
    pitch_y_mm: float
    grid: tuple[int, int]
    count: int

@dataclass(frozen=True)
class HoleDetection:
    holes: tuple[DetectedHole, ...]
    patterns: tuple[DetectedPattern, ...]
```

**Key logic:**
- Find cylindrical faces where the radius is in the bolt-hole range (1.5–6mm diameter)
- For each cylindrical face, compute center and diameter from the cylinder radius
- Associate holes with the nearest parent planar face
- **Pattern detection:** for holes on the same face with the same diameter, project centers onto the face plane, find the dominant spacing in X and Y directions (pitch), verify regularity (tolerance ±0.5mm), compute grid dimensions
- A cluster of ≥4 holes with regular spacing → pattern; isolated holes stay as individual holes

### connection_classifier.py

**Input:** `HoleDetection` + `StepAnalysis`.

**Output:** Lists of `ConnectionPoint` and compatibility tags.

**Classification rules (goBILDA domain knowledge):**

| Feature | Classification | Tags |
|---------|---------------|------|
| Hole pattern: 4.2mm dia, 8mm pitch | `bolt_hole_grid` | `gobilda_8mm_pattern`, `M4_bolt` |
| Hole pattern: 4.2mm dia, non-8mm pitch | `bolt_hole_grid` | `M4_bolt` |
| Hole pattern: 3.4mm dia, 8mm pitch | `bolt_hole_grid` | `gobilda_8mm_pattern`, `M3_bolt` |
| Single hole: 8mm dia, D-shaped profile | `shaft_bore` | `REX_8mm_shaft` |
| Single hole: 8mm dia, round | `shaft_bore` | `8mm_shaft` |
| Hole pattern: 4×M3 on 31mm circle | `motor_mount_pattern` | `yellow_jacket_mount` |
| Single hole: 6mm dia | `shaft_bore` | `6mm_shaft` |
| Single hole: 5mm dia | `pin_hole` | `5mm_pin` |

**Bolt size mapping:**

| Hole diameter (mm) | Bolt size |
|---------------------|-----------|
| 2.5–2.7 | M2.5 |
| 3.2–3.5 | M3 |
| 4.0–4.3 | M4 |
| 5.0–5.5 | M5 |

**`can_mate_with` inference:** derived from the connection types found:
- Has `bolt_hole_grid` → can mate with brackets, plates, channels
- Has `shaft_bore` → can mate with shafts, hubs, wheels
- Has `motor_mount_pattern` → can mate with motors

### profile_builder.py

**Input:** STEP file path + SKU + category + name.

**Output:** `PartProfile`-compatible dict, written as JSON.

**Logic:**
1. Call `analyzer.analyze(path)` → `StepAnalysis`
2. Call `hole_detector.detect(analysis, shape)` → `HoleDetection`
3. Call `connection_classifier.classify(analysis, detection)` → connections + tags
4. Convert volume_mm3 → volume_cm3, estimate mass
5. Build mounting_faces from planar faces that have hole patterns
6. Assemble into the profile JSON schema (matching existing `PartProfile` fields)
7. Write `{output_dir}/{category}/{sku}.json`

### scripts/analyze_gobilda.py

CLI batch processor:

```
python scripts/analyze_gobilda.py \
    --input-dir /path/to/STEP/files \
    --output-dir ./profiles/gobilda \
    --sku-map ./sku_categories.json \
    --workers 4
```

- Walks input directory for `.STEP` files
- Extracts SKU from filename (e.g., `1101-0001-0008.STEP` → `1101-0001-0008`)
- SKU category map: JSON mapping SKU prefix → category (e.g., `{"1101": "structure/beam", "1120": "structure/channel"}`)
- Processes each file through `profile_builder`
- Parallel processing with `concurrent.futures.ProcessPoolExecutor`
- Progress reporting to stderr
- Writes individual `{category}/{sku}.json` profiles

### scripts/build_catalog.py

Catalog index builder:

```
python scripts/build_catalog.py \
    --profiles-dir ./profiles/gobilda \
    --output-dir ./profiles/gobilda
```

- Reads all profile JSON files
- Generates `catalog.json` — array of `CatalogEntry`-compatible dicts
- Generates `categories.json` — array of `CategorySummary`-compatible dicts

## SKU Category Map

Initial mapping based on goBILDA SKU prefix conventions:

```json
{
    "1101": "structure/beam",
    "1102": "structure/beam",
    "1103": "structure/beam",
    "1104": "structure/channel",
    "1105": "structure/channel",
    "1106": "structure/channel",
    "1107": "structure/plate",
    "1108": "structure/plate",
    "1109": "structure/plate",
    "1110": "structure/rail",
    "1111": "structure/rail",
    "1112": "structure/standoff",
    "1113": "structure/standoff",
    "1114": "structure/standoff",
    "1115": "structure/standoff",
    "1116": "structure/spacer",
    "1117": "structure/spacer",
    "1118": "structure/spacer",
    "1119": "structure/spacer",
    "1120": "structure/channel",
    "1121": "structure/channel",
    "1130": "structure/bracket",
    "1131": "structure/bracket",
    "1140": "structure/bracket",
    "1141": "structure/bracket",
    "1142": "structure/bracket",
    "1143": "structure/bracket",
    "1144": "structure/bracket",
    "1145": "structure/bracket",
    "1200": "structure/plate",
    "1201": "structure/plate",
    "1300": "structure/connector",
    "1301": "structure/connector",
    "1310": "motion/shaft",
    "1400": "motion/hub",
    "1401": "motion/hub",
    "1500": "motion/gear",
    "1501": "motion/gear",
    "1502": "motion/gear",
    "1600": "motion/bearing",
    "1601": "motion/bearing",
    "2000": "motion/linear",
    "2100": "motion/linear",
    "2800": "motion/wheel",
    "2900": "motion/wheel",
    "2901": "motion/wheel",
    "2905": "motion/wheel",
    "2906": "motion/wheel",
    "3400": "electronics/servo",
    "3500": "electronics/sensor",
    "3600": "electronics/hub",
    "3601": "electronics/hub",
    "3604": "electronics/hub",
    "4000": "electronics/controller",
    "5200": "motion/motor",
    "5201": "motion/motor",
    "5202": "motion/motor",
    "5203": "motion/motor"
}
```

This map ships as `src/robotics_design_advisor/step/sku_categories.json` and can be
extended as new parts are encountered.

## Testing Strategy

### Unit tests (mocked CadQuery)

- `test_analyzer.py` — Mock CadQuery shape objects; verify bounding box, volume, face extraction
- `test_hole_detector.py` — Mock cylindrical faces; verify diameter measurement, pattern detection (pitch, grid)
- `test_connection_classifier.py` — Feed known hole patterns; verify correct classification and tags
- `test_profile_builder.py` — Mock analyzer + detector; verify JSON output matches schema

### Integration tests (real STEP files)

- `test_step_integration.py` — Load a small real STEP file (e.g., `1101-0001-0008.STEP`), run full pipeline, verify output is valid `PartProfile` JSON
- Mark with `@pytest.mark.integration` so they can be skipped in CI without CadQuery

### Test data

- Copy 2-3 small STEP files into `tests/fixtures/step/` for integration tests
- Use the goBILDA folder's smallest files

## Error Handling

- **STEP load failure:** Log warning, skip file, continue batch
- **No holes detected:** Valid — some parts (wheels, gears) have no bolt patterns
- **Pattern detection ambiguity:** Fall back to individual holes if grid is irregular
- **Unknown SKU prefix:** Log warning, use category `"uncategorized"`

## Performance

- Batch processing uses `ProcessPoolExecutor` with configurable worker count
- Each STEP file takes ~0.5-2s to analyze (estimated)
- 910 files × 1s avg = ~15 minutes with 1 worker, ~4 minutes with 4 workers
- Profile JSON files are small (~1-3 KB each)

## Dependencies

```toml
[project.optional-dependencies]
step = [
    "cadquery>=2.4",
]
```

CadQuery pulls in `OCP` (OpenCASCADE Python bindings) automatically.
Install with: `pip install -e ".[step]"`
