"""Tests for sensor recommendation engine."""

import pytest

from robotics_design_advisor.autonomous.models import SensorRecommendation
from robotics_design_advisor.autonomous.sensors import (
    SENSOR_DATABASE,
    recommend_sensors,
)


class TestSensorDatabase:
    def test_has_standard_tasks(self):
        expected_tasks = [
            "piece_detection",
            "distance_to_wall",
            "field_position",
            "heading",
            "line_detection",
            "target_alignment",
        ]
        for task in expected_tasks:
            assert task in SENSOR_DATABASE, f"Missing task: {task}"

    def test_all_entries_are_sensor_recommendations(self):
        for task, rec in SENSOR_DATABASE.items():
            assert isinstance(rec, SensorRecommendation)
            assert rec.task == task

    def test_sensor_fields_non_empty(self):
        for task, rec in SENSOR_DATABASE.items():
            assert rec.sensor_type, f"{task}: sensor_type is empty"
            assert rec.sensor_name, f"{task}: sensor_name is empty"
            assert rec.mounting_location, f"{task}: mounting_location is empty"
            assert rec.rationale, f"{task}: rationale is empty"


class TestRecommendSensors:
    def test_single_task(self):
        result = recommend_sensors(("piece_detection",))
        assert len(result) == 1
        assert result[0].task == "piece_detection"

    def test_multiple_tasks(self):
        result = recommend_sensors(("piece_detection", "heading", "distance_to_wall"))
        assert len(result) == 3
        tasks = {r.task for r in result}
        assert tasks == {"piece_detection", "heading", "distance_to_wall"}

    def test_all_results_are_sensor_recommendations(self):
        result = recommend_sensors(("piece_detection", "field_position"))
        assert all(isinstance(r, SensorRecommendation) for r in result)

    def test_unknown_task_skipped(self):
        result = recommend_sensors(("piece_detection", "teleportation"))
        assert len(result) == 1
        assert result[0].task == "piece_detection"

    def test_empty_tasks_returns_empty(self):
        result = recommend_sensors(())
        assert len(result) == 0
        assert isinstance(result, tuple)

    def test_all_known_tasks(self):
        all_tasks = tuple(SENSOR_DATABASE.keys())
        result = recommend_sensors(all_tasks)
        assert len(result) == len(all_tasks)

    def test_duplicate_tasks_deduplicated(self):
        result = recommend_sensors(("heading", "heading", "heading"))
        assert len(result) == 1
