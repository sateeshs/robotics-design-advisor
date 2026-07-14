"""goBILDA mechanical pattern constants.

Standard dimensions, pitches, and bolt patterns used across the
goBILDA ecosystem.  These constants drive compatibility matching
in the query engine and smart mate suggestions.

All dimensions are in **millimeters** unless noted otherwise.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Hole pattern pitch
# ---------------------------------------------------------------------------

PITCH_MM: float = 8.0
"""Standard goBILDA hole spacing — 8 mm center-to-center."""

HALF_PITCH_MM: float = 4.0
"""Half-pitch for offset patterns."""

# ---------------------------------------------------------------------------
# M4 fastener specs
# ---------------------------------------------------------------------------

M4_THREAD_DIAMETER_MM: float = 4.0
"""M4 nominal thread diameter."""

M4_CLEARANCE_HOLE_MM: float = 4.2
"""M4 clearance hole diameter (standard fit)."""

M4_CLOSE_FIT_HOLE_MM: float = 4.1
"""M4 close-fit clearance hole diameter."""

M4_TAP_DRILL_MM: float = 3.3
"""M4 tap drill diameter (0.7 mm pitch thread)."""

M4_SOCKET_HEAD_DIAMETER_MM: float = 7.0
"""M4 socket head cap screw head diameter."""

M4_SOCKET_HEAD_HEIGHT_MM: float = 4.0
"""M4 socket head cap screw head height."""

M4_NUT_WIDTH_MM: float = 7.0
"""M4 nut width across flats."""

M4_NUT_HEIGHT_MM: float = 3.2
"""M4 nut height."""

# ---------------------------------------------------------------------------
# REX shaft system
# ---------------------------------------------------------------------------

REX_SHAFT_DIAMETER_MM: float = 8.0
"""REX shaft outer diameter."""

REX_D_BORE_FLAT_DEPTH_MM: float = 0.5
"""Depth of the D-bore flat on the REX shaft."""

REX_SHAFT_BORE_MM: float = 8.0
"""Bore diameter for REX shaft mounting."""

# ---------------------------------------------------------------------------
# Channel dimensions
# ---------------------------------------------------------------------------

CHANNEL_WIDTH_MM: float = 48.0
"""Standard U-channel cross-section width."""

CHANNEL_HEIGHT_MM: float = 48.0
"""Standard U-channel cross-section height."""

CHANNEL_WALL_THICKNESS_MM: float = 3.0
"""Standard U-channel wall thickness."""

CHANNEL_STANDARD_LENGTHS_MM: tuple[float, ...] = (
    48.0, 96.0, 144.0, 192.0, 240.0, 288.0, 336.0,
    384.0, 432.0, 480.0, 528.0, 576.0,
)
"""Standard goBILDA U-channel lengths."""

# ---------------------------------------------------------------------------
# Motor mount bolt patterns
# ---------------------------------------------------------------------------

YELLOW_JACKET_BOLT_CIRCLE_DIAMETER_MM: float = 33.0
"""Yellow Jacket motor face bolt circle diameter (M4, 4 holes)."""

YELLOW_JACKET_BOLT_COUNT: int = 4
"""Number of mounting bolts on Yellow Jacket face."""

YELLOW_JACKET_SHAFT_DIAMETER_MM: float = 6.0
"""Yellow Jacket output shaft diameter (6mm D-shaft)."""

YELLOW_JACKET_PILOT_DIAMETER_MM: float = 16.0
"""Yellow Jacket front pilot diameter for centering."""

# ---------------------------------------------------------------------------
# Servo mount patterns
# ---------------------------------------------------------------------------

SERVO_MOUNT_HOLE_SPACING_MM: float = 10.0
"""Standard servo mounting tab hole spacing."""

SERVO_MOUNT_HOLE_DIAMETER_MM: float = 4.2
"""Standard servo mounting hole diameter (M4 clearance)."""

# ---------------------------------------------------------------------------
# Compatibility tags
# ---------------------------------------------------------------------------

TAG_GOBILDA_8MM_PATTERN: str = "gobilda_8mm_pattern"
"""Tag for parts with standard 8mm-pitch hole grids."""

TAG_M4_BOLT: str = "M4_bolt"
"""Tag for M4 bolt-compatible holes."""

TAG_M4_SOCKET_HEAD: str = "M4_socket_head"
"""Tag for M4 socket head cap screw clearance."""

TAG_REX_8MM_SHAFT: str = "REX_8mm_shaft"
"""Tag for REX 8mm shaft-compatible bores."""

TAG_YELLOW_JACKET_MOUNT: str = "yellow_jacket_mount"
"""Tag for Yellow Jacket motor mount bolt pattern."""

ALL_TAGS: tuple[str, ...] = (
    TAG_GOBILDA_8MM_PATTERN,
    TAG_M4_BOLT,
    TAG_M4_SOCKET_HEAD,
    TAG_REX_8MM_SHAFT,
    TAG_YELLOW_JACKET_MOUNT,
)
"""All defined compatibility tags."""

# ---------------------------------------------------------------------------
# Category prefixes (SKU → category mapping)
# ---------------------------------------------------------------------------

SKU_CATEGORY_MAP: dict[str, str] = {
    "1100": "structure/bracket",
    "1101": "structure/bracket",
    "1120": "structure/channel",
    "1121": "structure/channel",
    "1200": "structure/plate",
    "1301": "structure/bracket",
    "1309": "motion/shaft",
    "1310": "motion/shaft",
    "2800": "motion/gear",
    "2801": "motion/gear",
    "2900": "motion/wheel",
    "3200": "motion/linear",
    "3201": "motion/linear",
    "3400": "motion/servo",
    "5201": "motion/motor",
    "5202": "motion/motor",
}
"""Maps the first 4 digits of a goBILDA SKU to a category path."""
