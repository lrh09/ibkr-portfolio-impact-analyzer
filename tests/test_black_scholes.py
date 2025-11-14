"""
Unit tests for Black-Scholes calculator.
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.valuation.black_scholes import BlackScholesCalculator


class TestBlackScholesCalculator(unittest.TestCase):
    """Test Black-Scholes calculator."""

    def setUp(self):
        """Set up test calculator."""
        self.calc = BlackScholesCalculator(risk_free_rate=0.05)

    def test_call_option_pricing(self):
        """Test call option pricing."""
        price = self.calc.calculate_option_price(
            spot=100,
            strike=100,
            time_to_expiry=1.0,  # 1 year
            volatility=0.30,
            option_type='C'
        )

        # ATM call with 30% IV should be roughly 10-15% of spot
        self.assertGreater(price, 10)
        self.assertLess(price, 20)

    def test_put_option_pricing(self):
        """Test put option pricing."""
        price = self.calc.calculate_option_price(
            spot=100,
            strike=100,
            time_to_expiry=1.0,
            volatility=0.30,
            option_type='P'
        )

        # ATM put should be similar to call (put-call parity)
        self.assertGreater(price, 8)
        self.assertLess(price, 18)

    def test_expired_option(self):
        """Test expired option returns intrinsic value."""
        # ITM call
        price = self.calc.calculate_option_price(
            spot=110,
            strike=100,
            time_to_expiry=0,
            volatility=0.30,
            option_type='C'
        )
        self.assertEqual(price, 10)

        # OTM call
        price = self.calc.calculate_option_price(
            spot=90,
            strike=100,
            time_to_expiry=0,
            volatility=0.30,
            option_type='C'
        )
        self.assertEqual(price, 0)

    def test_greeks_calculation(self):
        """Test Greeks calculation."""
        greeks = self.calc.calculate_greeks(
            spot=100,
            strike=100,
            time_to_expiry=1.0,
            volatility=0.30,
            option_type='C'
        )

        # ATM call delta should be around 0.5
        self.assertGreater(greeks['delta'], 0.4)
        self.assertLess(greeks['delta'], 0.6)

        # Gamma should be positive
        self.assertGreater(greeks['gamma'], 0)

        # Vega should be positive
        self.assertGreater(greeks['vega'], 0)

        # Theta should be negative (time decay)
        self.assertLess(greeks['theta'], 0)


if __name__ == '__main__':
    unittest.main()
