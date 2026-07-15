"""Tests for mechanism physics dataclasses."""

from robotics_design_advisor.mechanisms.models import (
    GrabberAnalysis,
    LauncherAnalysis,
    LiftAnalysis,
    MotionProfile,
    MotorMatch,
)


class TestGrabberAnalysis:
    def test_creation(self):
        g = GrabberAnalysis(
            required_grip_force_n=5.0,
            required_torque_nmm=250.0,
            recommended_servo="goBILDA Torque Servo",
            jaw_opening_mm=45.0,
            grip_type="claw",
            hold_current_ma=200.0,
            notes=("Use rubber pads for grip.",),
        )
        assert g.required_grip_force_n == 5.0
        assert g.grip_type == "claw"
        assert len(g.notes) == 1

    def test_frozen(self):
        g = GrabberAnalysis(
            required_grip_force_n=5.0,
            required_torque_nmm=250.0,
            recommended_servo="goBILDA Torque Servo",
            jaw_opening_mm=45.0,
            grip_type="claw",
            hold_current_ma=200.0,
            notes=(),
        )
        try:
            g.grip_type = "roller_intake"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestLauncherAnalysis:
    def test_creation(self):
        la = LauncherAnalysis(
            launch_velocity_ms=5.0,
            launch_angle_deg=45.0,
            flywheel_rpm=3000.0,
            flywheel_diameter_mm=100.0,
            motor_recommendation="Yellow Jacket 5.2:1",
            spin_up_time_s=0.8,
            energy_per_shot_j=0.35,
            fire_rate_hz=2.0,
            catapult_spring_force_n=0.0,
            notes=(),
        )
        assert la.launch_velocity_ms == 5.0
        assert la.flywheel_rpm == 3000.0


class TestLiftAnalysis:
    def test_creation(self):
        li = LiftAnalysis(
            required_force_n=20.0,
            peak_force_n=30.0,
            required_torque_nmm=500.0,
            motor_recommendation="Yellow Jacket 50.9:1",
            gear_ratio=50.9,
            max_speed_mm_s=150.0,
            time_to_max_height_s=3.0,
            counterbalance_force_n=10.0,
            spool_diameter_mm=30.0,
            lift_type="elevator",
            notes=(),
        )
        assert li.required_force_n == 20.0
        assert li.lift_type == "elevator"


class TestMotionProfile:
    def test_creation(self):
        mp = MotionProfile(
            total_ticks=1000,
            cruise_velocity_tps=500.0,
            accel_ticks=200,
            decel_ticks=200,
            cruise_ticks=600,
            total_time_s=2.5,
            accel_time_s=0.5,
            suggested_kp=0.01,
            suggested_ki=0.0,
            suggested_kd=0.001,
            notes=(),
        )
        assert mp.total_ticks == 1000
        assert mp.accel_ticks + mp.decel_ticks + mp.cruise_ticks == mp.total_ticks


class TestMotorMatch:
    def test_creation(self):
        mm = MotorMatch(
            motor_name="Yellow Jacket 50.9:1",
            motor_sku="5202-0002-0051",
            base_rpm=117.0,
            stall_torque_nmm=6326.0,
            gear_ratio=50.9,
            output_rpm=117.0,
            output_torque_nmm=6326.0,
            torque_margin_pct=35.0,
            current_draw_a=3.0,
            notes=(),
        )
        assert mm.motor_sku == "5202-0002-0051"
        assert mm.torque_margin_pct == 35.0
