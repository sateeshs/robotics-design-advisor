"""Tests for Phase 4C design advisor dataclasses."""

from robotics_design_advisor.engineering.models import (
    BillOfMaterials,
    BOMItem,
    DesignSynthesis,
    GameAnalysis,
    ScoringStrategy,
)


class TestScoringStrategy:
    def test_creation(self):
        s = ScoringStrategy(
            name="high_basket_focused",
            expected_auto_points=16,
            expected_teleop_points=40,
            expected_endgame_points=15,
            total_expected_points=71,
            required_mechanisms=("elevator", "grabber", "drivetrain"),
            difficulty="intermediate",
            rationale="Focus on high basket scoring for maximum points per cycle",
        )
        assert s.name == "high_basket_focused"
        assert s.total_expected_points == 71
        assert len(s.required_mechanisms) == 3

    def test_frozen(self):
        s = ScoringStrategy(
            name="test",
            expected_auto_points=0,
            expected_teleop_points=0,
            expected_endgame_points=0,
            total_expected_points=0,
            required_mechanisms=(),
            difficulty="beginner",
            rationale="test",
        )
        try:
            s.name = "changed"  # type: ignore[misc]
            assert False, "Should raise"
        except AttributeError:
            pass


class TestGameAnalysis:
    def test_creation(self):
        strategy = ScoringStrategy(
            name="net_zone",
            expected_auto_points=4,
            expected_teleop_points=20,
            expected_endgame_points=3,
            total_expected_points=27,
            required_mechanisms=("grabber", "drivetrain"),
            difficulty="beginner",
            rationale="Simple net zone scoring",
        )
        ga = GameAnalysis(
            season="INTO THE DEEP",
            competition="FTC",
            strategies=(strategy,),
            recommended_strategy="net_zone",
            game_pieces=({"name": "sample", "weight_g": 28},),
            field_config={"width_mm": 3658, "length_mm": 3658},
        )
        assert ga.season == "INTO THE DEEP"
        assert ga.competition == "FTC"
        assert len(ga.strategies) == 1
        assert ga.recommended_strategy == "net_zone"


class TestBOMItem:
    def test_creation(self):
        item = BOMItem(
            sku="5202-0002-0019",
            name="goBILDA Yellow Jacket 19.2:1",
            quantity=4,
            unit_price_usd=19.99,
            category="motion",
            subsystem="drivetrain",
            notes="Drivetrain motors",
        )
        assert item.sku == "5202-0002-0019"
        assert item.quantity == 4
        assert item.unit_price_usd == 19.99


class TestBillOfMaterials:
    def test_creation(self):
        item = BOMItem(
            sku="5202-0002-0019",
            name="goBILDA Yellow Jacket 19.2:1",
            quantity=4,
            unit_price_usd=19.99,
            category="motion",
            subsystem="drivetrain",
            notes="",
        )
        bom = BillOfMaterials(
            items=(item,),
            total_cost_usd=79.96,
            total_weight_g=1200.0,
            warnings=(),
            subsystem_breakdown={"drivetrain": (79.96, 1200.0, 1)},
        )
        assert bom.total_cost_usd == 79.96
        assert len(bom.items) == 1
        assert "drivetrain" in bom.subsystem_breakdown


class TestDesignSynthesis:
    def test_creation(self):
        strategy = ScoringStrategy(
            name="test",
            expected_auto_points=0,
            expected_teleop_points=0,
            expected_endgame_points=0,
            total_expected_points=0,
            required_mechanisms=(),
            difficulty="beginner",
            rationale="test",
        )
        item = BOMItem(
            sku="TEST-001",
            name="Test Part",
            quantity=1,
            unit_price_usd=10.0,
            category="structure",
            subsystem="chassis",
            notes="",
        )
        bom = BillOfMaterials(
            items=(item,),
            total_cost_usd=10.0,
            total_weight_g=100.0,
            warnings=(),
            subsystem_breakdown={},
        )
        ds = DesignSynthesis(
            season="INTO THE DEEP",
            competition="FTC",
            strategy=strategy,
            archetype_name="Speed Shooter",
            bom=bom,
            mechanism_notes=("Grabber: claw grip, 2.0N force",),
            autonomous_notes=("30s auto budget, 25s margin",),
            warnings=(),
        )
        assert ds.season == "INTO THE DEEP"
        assert ds.archetype_name == "Speed Shooter"
        assert ds.bom.total_cost_usd == 10.0
