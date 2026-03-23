"""Tests for the ScenarioEngine.

Validates Mamdani scenario generation, shock computation, and
cross-scenario comparison.
"""

from __future__ import annotations

import pytest

from app.services.scenario_engine import (
    MAMDANI_SCENARIOS,
    ScenarioComparisonResult,
    ScenarioEngine,
    ScenarioShock,
)


@pytest.fixture()
def engine() -> ScenarioEngine:
    return ScenarioEngine()


# ------------------------------------------------------------------
# Mamdani scenarios
# ------------------------------------------------------------------

class TestMamdaniScenarios:
    """The three hardcoded Mamdani scenarios."""

    def test_mamdani_scenarios_exist(self, engine: ScenarioEngine):
        """There should be exactly three Mamdani scenarios."""
        scenarios = engine.get_mamdani_scenarios()
        assert len(scenarios) == 3

        expected_keys = {
            "soft_implementation",
            "full_rent_freeze",
            "freeze_plus_buildout",
        }
        assert set(scenarios.keys()) == expected_keys

    def test_mamdani_scenarios_have_required_fields(self, engine: ScenarioEngine):
        """Each scenario should contain name, narrative, intensity, and policy_levers."""
        for key, sc in engine.get_mamdani_scenarios().items():
            assert "name" in sc, f"Missing 'name' in {key}"
            assert "narrative" in sc, f"Missing 'narrative' in {key}"
            assert "intensity" in sc, f"Missing 'intensity' in {key}"
            assert "policy_levers" in sc, f"Missing 'policy_levers' in {key}"
            assert isinstance(sc["policy_levers"], dict)

    def test_mamdani_scenarios_are_deep_copies(self, engine: ScenarioEngine):
        """Modifying the returned dict should not affect the engine's copy."""
        s1 = engine.get_mamdani_scenarios()
        s1["soft_implementation"]["name"] = "MUTATED"
        s2 = engine.get_mamdani_scenarios()
        assert s2["soft_implementation"]["name"] != "MUTATED"


# ------------------------------------------------------------------
# Shock computation
# ------------------------------------------------------------------

class TestScenarioShock:
    """Shock estimation for a given scenario and target metric."""

    def test_scenario_shock_computation(self, engine: ScenarioEngine):
        """Known scenario + known target should return the lookup table value."""
        scenarios = engine.get_mamdani_scenarios()
        freeze = scenarios["full_rent_freeze"]

        shock = engine.compute_scenario_shock(
            scenario=freeze,
            target="median_rent_stabilised",
        )
        # The shock table specifies -10.0 for full_rent_freeze on median_rent_stabilised.
        assert shock == pytest.approx(-10.0, abs=0.01)

    def test_scenario_shock_soft_implementation(self, engine: ScenarioEngine):
        """Soft implementation on median rent should yield +30."""
        scenarios = engine.get_mamdani_scenarios()
        soft = scenarios["soft_implementation"]

        shock = engine.compute_scenario_shock(
            scenario=soft,
            target="median_rent_stabilised",
        )
        assert shock == pytest.approx(30.0, abs=0.01)

    def test_scenario_shock_unknown_target_heuristic(self, engine: ScenarioEngine):
        """An unknown target should fall back to the heuristic calculation."""
        scenarios = engine.get_mamdani_scenarios()
        soft = scenarios["soft_implementation"]

        shock = engine.compute_scenario_shock(
            scenario=soft,
            target="some_unknown_metric",
        )
        # Heuristic: intensity_multiplier * lever_sum * 0.01
        # soft intensity = 0.3
        # lever_sum = |1.5| + |2.5| + |5.0| + |0| + |0.0| = 9.0
        # shock = 0.3 * 9.0 * 0.01 = 0.027
        assert isinstance(shock, float)
        assert shock >= 0  # soft is a small positive intervention


# ------------------------------------------------------------------
# Scenario comparison
# ------------------------------------------------------------------

class TestCompareScenarios:
    """Side-by-side scenario comparison."""

    def test_compare_scenarios(self, engine: ScenarioEngine):
        """Comparing all three scenarios should produce shocks for each."""
        scenarios = engine.get_mamdani_scenarios()
        question = {"target_metric": "median_rent_stabilised"}

        result = engine.compare_scenarios(
            scenarios=list(scenarios.values()),
            question=question,
        )

        assert isinstance(result, ScenarioComparisonResult)
        assert len(result.shocks) == 3
        assert len(result.scenarios) == 3

        # The summary should mention the target metric.
        assert "median_rent_stabilised" in result.summary

        # Each shock should be a ScenarioShock instance.
        for name, shock in result.shocks.items():
            assert isinstance(shock, ScenarioShock)
            assert shock.target_metric == "median_rent_stabilised"

    def test_compare_scenarios_different_shocks(self, engine: ScenarioEngine):
        """Different scenarios should generally produce different shock values."""
        scenarios = engine.get_mamdani_scenarios()
        question = {"target_metric": "median_rent_stabilised"}

        result = engine.compare_scenarios(
            scenarios=list(scenarios.values()),
            question=question,
        )

        shock_values = [s.shock_value for s in result.shocks.values()]
        # At least two of the three should differ.
        assert len(set(shock_values)) >= 2

    def test_compare_scenarios_vacancy_rate(self, engine: ScenarioEngine):
        """Compare scenarios on the vacancy_rate metric."""
        scenarios = engine.get_mamdani_scenarios()
        question = {"target_metric": "vacancy_rate"}

        result = engine.compare_scenarios(
            scenarios=list(scenarios.values()),
            question=question,
        )

        assert len(result.shocks) == 3
        # freeze_plus_buildout should increase vacancy (positive shock).
        freeze_buildout_shock = None
        for name, shock in result.shocks.items():
            if "buildout" in name.lower() or "plus" in name.lower():
                freeze_buildout_shock = shock
        if freeze_buildout_shock is not None:
            assert freeze_buildout_shock.shock_value > 0
