"""Tests for mechanism recommendation engine (Phase 2D.3)."""

import pytest

from robotics_design_advisor.engineering.electrical import load_motor_specs
from robotics_design_advisor.engineering.models import (
    DrivetrainChoice,
    IntakeChoice,
    MotorRecommendation,
    ScorerChoice,
)
from robotics_design_advisor.engineering.recommendations import (
    recommend_drivetrain,
    recommend_intake,
    recommend_scorer,
    suggest_motor_for_application,
)


@pytest.fixture()
def motors():
    return load_motor_specs()


# ---------------------------------------------------------------------------
# recommend_drivetrain
# ---------------------------------------------------------------------------

class TestRecommendDrivetrain:
    def test_returns_drivetrain_choice(self) -> None:
        result = recommend_drivetrain(speed_priority=0.8, push_priority=0.2, agility=0.7)
        assert isinstance(result, DrivetrainChoice)

    def test_high_speed_high_agility_prefers_mecanum(self) -> None:
        result = recommend_drivetrain(speed_priority=0.8, push_priority=0.2, agility=0.9)
        assert result.drivetrain_type == "mecanum"

    def test_high_push_prefers_differential(self) -> None:
        result = recommend_drivetrain(speed_priority=0.3, push_priority=0.9, agility=0.3)
        assert result.drivetrain_type == "differential"

    def test_extreme_agility_prefers_swerve_or_mecanum(self) -> None:
        result = recommend_drivetrain(speed_priority=0.5, push_priority=0.1, agility=1.0)
        assert result.drivetrain_type in ("swerve", "mecanum")

    def test_motor_count_is_positive(self) -> None:
        result = recommend_drivetrain(speed_priority=0.5, push_priority=0.5, agility=0.5)
        assert result.motor_count >= 2

    def test_has_rationale(self) -> None:
        result = recommend_drivetrain(speed_priority=0.5, push_priority=0.5, agility=0.5)
        assert len(result.rationale) > 0

    def test_has_pros_and_cons(self) -> None:
        result = recommend_drivetrain(speed_priority=0.5, push_priority=0.5, agility=0.5)
        assert len(result.pros) > 0
        assert len(result.cons) > 0

    def test_recommended_motor_skus_not_empty(self) -> None:
        result = recommend_drivetrain(speed_priority=0.5, push_priority=0.5, agility=0.5)
        assert len(result.recommended_motor_skus) > 0

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValueError, match="speed_priority"):
            recommend_drivetrain(speed_priority=1.5, push_priority=0.5, agility=0.5)

    def test_negative_priority_raises(self) -> None:
        with pytest.raises(ValueError, match="push_priority"):
            recommend_drivetrain(speed_priority=0.5, push_priority=-0.1, agility=0.5)


# ---------------------------------------------------------------------------
# recommend_intake
# ---------------------------------------------------------------------------

class TestRecommendIntake:
    def test_returns_intake_choice(self) -> None:
        result = recommend_intake(
            element_size_mm=100.0, element_shape="sphere", intake_speed=0.7,
        )
        assert isinstance(result, IntakeChoice)

    def test_small_sphere_prefers_roller(self) -> None:
        result = recommend_intake(
            element_size_mm=80.0, element_shape="sphere", intake_speed=0.8,
        )
        assert result.intake_type == "front_roller"

    def test_large_cube_prefers_claw(self) -> None:
        result = recommend_intake(
            element_size_mm=200.0, element_shape="cube", intake_speed=0.3,
        )
        assert result.intake_type == "claw_gripper"

    def test_motor_and_servo_counts_positive(self) -> None:
        result = recommend_intake(
            element_size_mm=100.0, element_shape="sphere", intake_speed=0.5,
        )
        assert result.motor_count >= 0
        assert result.servo_count >= 0
        assert result.motor_count + result.servo_count > 0

    def test_has_rationale(self) -> None:
        result = recommend_intake(
            element_size_mm=100.0, element_shape="sphere", intake_speed=0.5,
        )
        assert len(result.rationale) > 0

    def test_invalid_element_size_raises(self) -> None:
        with pytest.raises(ValueError, match="element_size_mm"):
            recommend_intake(element_size_mm=0.0, element_shape="sphere", intake_speed=0.5)

    def test_high_speed_dual_intake(self) -> None:
        result = recommend_intake(
            element_size_mm=100.0, element_shape="sphere", intake_speed=1.0,
        )
        assert result.intake_type in ("front_roller", "dual_side_intake")


# ---------------------------------------------------------------------------
# recommend_scorer
# ---------------------------------------------------------------------------

class TestRecommendScorer:
    def test_returns_scorer_choice(self) -> None:
        result = recommend_scorer(range_mm=2000.0, accuracy=0.8, rate=0.5)
        assert isinstance(result, ScorerChoice)

    def test_long_range_high_accuracy_prefers_flywheel(self) -> None:
        result = recommend_scorer(range_mm=3000.0, accuracy=0.9, rate=0.7)
        assert "flywheel" in result.scorer_type

    def test_short_range_high_accuracy_prefers_placer(self) -> None:
        result = recommend_scorer(range_mm=200.0, accuracy=0.9, rate=0.3)
        assert result.scorer_type == "elevator_placer"

    def test_high_rate_prefers_flywheel_or_catapult(self) -> None:
        result = recommend_scorer(range_mm=1500.0, accuracy=0.3, rate=0.9)
        assert result.scorer_type in ("dual_flywheel", "catapult")

    def test_motor_count_positive(self) -> None:
        result = recommend_scorer(range_mm=1000.0, accuracy=0.5, rate=0.5)
        assert result.motor_count >= 1

    def test_has_pros_and_cons(self) -> None:
        result = recommend_scorer(range_mm=1000.0, accuracy=0.5, rate=0.5)
        assert len(result.pros) > 0
        assert len(result.cons) > 0

    def test_invalid_range_raises(self) -> None:
        with pytest.raises(ValueError, match="range_mm"):
            recommend_scorer(range_mm=-100.0, accuracy=0.5, rate=0.5)


# ---------------------------------------------------------------------------
# suggest_motor_for_application
# ---------------------------------------------------------------------------

class TestSuggestMotorForApplication:
    def test_returns_list_of_recommendations(self, motors) -> None:
        result = suggest_motor_for_application(motors, "drivetrain")
        assert isinstance(result, list)
        assert all(isinstance(r, MotorRecommendation) for r in result)

    def test_drivetrain_recommendations_sorted_by_score(self, motors) -> None:
        result = suggest_motor_for_application(motors, "drivetrain")
        scores = [r.suitability_score for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_arm_prefers_high_torque(self, motors) -> None:
        result = suggest_motor_for_application(motors, "arm")
        # Top recommendation should have high gear ratio (high torque)
        assert result[0].gear_ratio >= 50.0

    def test_shooter_prefers_high_speed(self, motors) -> None:
        result = suggest_motor_for_application(motors, "shooter")
        # Top recommendation should have low gear ratio (high speed)
        assert result[0].gear_ratio <= 10.0

    def test_all_have_rationale(self, motors) -> None:
        result = suggest_motor_for_application(motors, "drivetrain")
        for r in result:
            assert len(r.rationale) > 0

    def test_scores_in_range(self, motors) -> None:
        result = suggest_motor_for_application(motors, "intake")
        for r in result:
            assert 0 <= r.suitability_score <= 100

    def test_top_n_limits_results(self, motors) -> None:
        result = suggest_motor_for_application(motors, "drivetrain", top_n=3)
        assert len(result) <= 3

    def test_invalid_application_raises(self, motors) -> None:
        with pytest.raises(ValueError, match="Unknown application"):
            suggest_motor_for_application(motors, "teleporter")

    def test_empty_motors_returns_empty(self) -> None:
        result = suggest_motor_for_application([], "drivetrain")
        assert result == []

    def test_elevator_prefers_medium_torque(self, motors) -> None:
        result = suggest_motor_for_application(motors, "elevator")
        # Elevator needs moderate torque — ratio between 20 and 100
        assert 15.0 <= result[0].gear_ratio <= 100.0
