"""Sensor recommendations for autonomous tasks.

Maps common FTC/FRC autonomous tasks to recommended sensors with
mounting locations and rationale. Pure functions, no I/O.
"""

from __future__ import annotations

from .models import SensorRecommendation

SENSOR_DATABASE: dict[str, SensorRecommendation] = {
    "piece_detection": SensorRecommendation(
        task="piece_detection",
        sensor_type="distance_tof",
        sensor_name="REV 2m Distance Sensor (Time of Flight)",
        mounting_location="claw_interior",
        rationale="Detects game piece presence in grabber via short-range distance reading. "
                  "Beam break alternative: mount across jaw opening.",
    ),
    "distance_to_wall": SensorRecommendation(
        task="distance_to_wall",
        sensor_type="distance_tof",
        sensor_name="REV 2m Distance Sensor",
        mounting_location="front_bumper",
        rationale="Measures distance to field walls for positioning. "
                  "Mount facing forward for approach control.",
    ),
    "field_position": SensorRecommendation(
        task="field_position",
        sensor_type="encoder",
        sensor_name="Dead wheel odometry (3x REV Through Bore Encoder)",
        mounting_location="chassis_underside",
        rationale="Three dead wheels (2 parallel + 1 perpendicular) track X/Y position. "
                  "Fuse with IMU heading for full field localization.",
    ),
    "heading": SensorRecommendation(
        task="heading",
        sensor_type="imu",
        sensor_name="REV Control Hub Built-in IMU (BNO055/BHI260AP)",
        mounting_location="chassis_center",
        rationale="Built into REV Control/Expansion Hub — no extra wiring. "
                  "Provides heading for turn control and odometry fusion.",
    ),
    "line_detection": SensorRecommendation(
        task="line_detection",
        sensor_type="color",
        sensor_name="REV Color Sensor V3",
        mounting_location="chassis_underside_front",
        rationale="Downward-facing color sensor detects field lines and tape. "
                  "Use for autonomous alignment at scoring positions.",
    ),
    "target_alignment": SensorRecommendation(
        task="target_alignment",
        sensor_type="camera",
        sensor_name="Logitech C270 or C920 + AprilTag pipeline",
        mounting_location="robot_front_upper",
        rationale="Webcam with AprilTag detection for target alignment. "
                  "Use EOCV or Limelight for processing. Mount high for clear sightlines.",
    ),
}


def recommend_sensors(
    tasks: tuple[str, ...],
) -> tuple[SensorRecommendation, ...]:
    """Recommend sensors for the given autonomous tasks.

    Unknown tasks are silently skipped. Duplicate tasks are deduplicated.

    Parameters
    ----------
    tasks : tuple of str
        Task names to get sensor recommendations for.
    """
    seen: set[str] = set()
    results: list[SensorRecommendation] = []
    for task in tasks:
        if task in SENSOR_DATABASE and task not in seen:
            results.append(SENSOR_DATABASE[task])
            seen.add(task)
    return tuple(results)
