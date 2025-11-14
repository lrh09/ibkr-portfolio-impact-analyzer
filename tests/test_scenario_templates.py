"""
Unit tests for scenario templates.
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scenario.scenario_templates import ScenarioTemplates


class TestScenarioTemplates(unittest.TestCase):
    """Test scenario templates."""

    def test_get_all_scenarios(self):
        """Test getting all scenarios."""
        scenarios = ScenarioTemplates.get_all_scenarios()

        # Should have at least 15 scenarios
        self.assertGreaterEqual(len(scenarios), 15)

        # Check for key scenarios
        self.assertIn('Normal Day', scenarios)
        self.assertIn('Market Panic', scenarios)
        self.assertIn('Earnings Beat', scenarios)

    def test_normal_day_scenario(self):
        """Test normal day scenario."""
        scenario = ScenarioTemplates.normal_day()

        self.assertEqual(scenario['spot_change'], 0.0)
        self.assertEqual(scenario['iv_change'], 0.0)
        self.assertEqual(scenario['days_pass'], 0)

    def test_market_panic_scenario(self):
        """Test market panic scenario."""
        scenario = ScenarioTemplates.market_panic()

        self.assertEqual(scenario['spot_change'], -0.05)
        self.assertIn('iv_multipliers', scenario)
        self.assertGreater(scenario['iv_multipliers']['OTM_PUT'], 0)

    def test_earnings_scenarios(self):
        """Test earnings scenarios have IV crush."""
        beat = ScenarioTemplates.earnings_beat()
        miss = ScenarioTemplates.earnings_miss()
        inline = ScenarioTemplates.earnings_inline()

        # All should have DTE-based IV scaling
        self.assertIn('dte_scaling', beat)
        self.assertIn('dte_scaling', miss)
        self.assertIn('dte_scaling', inline)

        # Short-dated options should have most IV crush
        self.assertLess(beat['dte_scaling']['0-7'], 0)
        self.assertLess(inline['dte_scaling']['0-7'], beat['dte_scaling']['0-7'])

    def test_custom_scenario(self):
        """Test custom scenario creation."""
        scenario = ScenarioTemplates.create_custom_scenario(
            name='Test Scenario',
            spot_change=0.10,
            iv_change=-0.20,
            days_pass=1
        )

        self.assertEqual(scenario['name'], 'Test Scenario')
        self.assertEqual(scenario['spot_change'], 0.10)
        self.assertEqual(scenario['iv_change'], -0.20)
        self.assertEqual(scenario['days_pass'], 1)


if __name__ == '__main__':
    unittest.main()
