"""
Pre-built scenario templates for portfolio analysis.
"""
from typing import Dict


class ScenarioTemplates:
    """Pre-defined market scenario templates."""

    @staticmethod
    def get_all_scenarios() -> Dict[str, Dict]:
        """
        Get all predefined scenarios.

        Returns:
            Dictionary of scenario name -> parameters
        """
        return {
            'Normal Day': ScenarioTemplates.normal_day(),
            'Earnings Beat': ScenarioTemplates.earnings_beat(),
            'Earnings Miss': ScenarioTemplates.earnings_miss(),
            'Earnings Inline': ScenarioTemplates.earnings_inline(),
            'Market Panic': ScenarioTemplates.market_panic(),
            'Flash Crash': ScenarioTemplates.flash_crash(),
            'Black Swan': ScenarioTemplates.black_swan(),
            'Fed Hawkish': ScenarioTemplates.fed_hawkish(),
            'Fed Dovish': ScenarioTemplates.fed_dovish(),
            'Fed Neutral': ScenarioTemplates.fed_neutral(),
            'Short Squeeze': ScenarioTemplates.short_squeeze(),
            'FOMO Rally': ScenarioTemplates.fomo_rally(),
            'Relief Rally': ScenarioTemplates.relief_rally(),
            '1 Day Pass': ScenarioTemplates.one_day_pass(),
            'Weekend': ScenarioTemplates.weekend(),
            '1 Week': ScenarioTemplates.one_week(),
        }

    @staticmethod
    def normal_day() -> Dict:
        """No change scenario."""
        return {
            'name': 'Normal Day',
            'spot_change': 0.0,
            'iv_change': 0.0,
            'days_pass': 0,
            'description': 'Baseline - no changes'
        }

    @staticmethod
    def earnings_beat() -> Dict:
        """Earnings beat expectations."""
        return {
            'name': 'Earnings Beat',
            'spot_change': 0.05,  # +5%
            'dte_scaling': {
                '0-7': -0.35,    # -35% IV for 0-7 DTE
                '8-30': -0.15,   # -15% IV for 8-30 DTE
                '31-90': -0.05,  # -5% IV for 31-90 DTE
                '90+': 0.0       # No change for 90+ DTE
            },
            'days_pass': 1,
            'description': 'Stock beats earnings, IV crush'
        }

    @staticmethod
    def earnings_miss() -> Dict:
        """Earnings miss expectations."""
        return {
            'name': 'Earnings Miss',
            'spot_change': -0.08,  # -8%
            'dte_scaling': {
                '0-7': -0.30,    # -30% IV for 0-7 DTE
                '8-30': -0.10,   # -10% IV for 8-30 DTE
                '31-90': 0.0,    # No change for 31-90 DTE
                '90+': 0.0       # No change for 90+ DTE
            },
            'days_pass': 1,
            'description': 'Stock misses earnings, IV crush with drop'
        }

    @staticmethod
    def earnings_inline() -> Dict:
        """Earnings inline with expectations."""
        return {
            'name': 'Earnings Inline',
            'spot_change': 0.0,  # ±1% (using 0 for simplicity)
            'dte_scaling': {
                '0-7': -0.40,    # -40% IV for 0-7 DTE
                '8-30': -0.20,   # -20% IV for 8-30 DTE
                '31-90': -0.05,  # -5% IV for 31-90 DTE
                '90+': 0.0       # No change for 90+ DTE
            },
            'days_pass': 1,
            'description': 'Earnings meet expectations, max IV crush'
        }

    @staticmethod
    def market_panic() -> Dict:
        """Market panic scenario."""
        return {
            'name': 'Market Panic',
            'spot_change': -0.05,  # -5%
            'iv_multipliers': {
                'OTM_PUT': 0.60,   # +60% IV for OTM puts
                'ATM': 0.35,       # +35% IV for ATM
                'OTM_CALL': 0.25,  # +25% IV for OTM calls
                'default': 0.35
            },
            'days_pass': 0,
            'description': 'Market selloff with volatility spike'
        }

    @staticmethod
    def flash_crash() -> Dict:
        """Flash crash scenario."""
        return {
            'name': 'Flash Crash',
            'spot_change': -0.08,  # -8%
            'iv_multipliers': {
                'OTM_PUT': 1.00,   # +100% IV for OTM puts
                'ATM': 0.50,       # +50% IV for ATM
                'OTM_CALL': 0.30,  # +30% IV for OTM calls
                'default': 0.50
            },
            'days_pass': 0,
            'description': 'Severe market drop with extreme vol spike'
        }

    @staticmethod
    def black_swan() -> Dict:
        """Black swan event."""
        return {
            'name': 'Black Swan',
            'spot_change': -0.20,  # -20%
            'iv_multipliers': {
                'OTM_PUT': 1.50,   # +150% IV
                'ATM': 1.50,       # +150% IV
                'OTM_CALL': 1.50,  # +150% IV
                'ITM_PUT': 1.50,
                'ITM_CALL': 1.50,
                'default': 1.50
            },
            'days_pass': 0,
            'description': 'Catastrophic event with extreme volatility'
        }

    @staticmethod
    def fed_hawkish() -> Dict:
        """Hawkish Fed decision."""
        return {
            'name': 'Fed Hawkish',
            'spot_change': -0.02,  # -2%
            'iv_change': 0.20,     # +20% uniform
            'days_pass': 0,
            'description': 'Fed more hawkish than expected'
        }

    @staticmethod
    def fed_dovish() -> Dict:
        """Dovish Fed decision."""
        return {
            'name': 'Fed Dovish',
            'spot_change': 0.015,  # +1.5%
            'iv_change': -0.10,    # -10% uniform
            'days_pass': 0,
            'description': 'Fed more dovish than expected'
        }

    @staticmethod
    def fed_neutral() -> Dict:
        """Neutral Fed decision."""
        return {
            'name': 'Fed Neutral',
            'spot_change': 0.0,    # ±0.5% (using 0)
            'iv_change': -0.05,    # -5% uniform
            'days_pass': 0,
            'description': 'Fed meets expectations'
        }

    @staticmethod
    def short_squeeze() -> Dict:
        """Short squeeze scenario."""
        return {
            'name': 'Short Squeeze',
            'spot_change': 0.10,  # +10%
            'iv_multipliers': {
                'OTM_CALL': 0.30,  # +30% IV for calls
                'ATM': 0.10,       # +10% IV for ATM
                'OTM_PUT': -0.10,  # -10% IV for puts
                'default': 0.10
            },
            'days_pass': 0,
            'description': 'Rapid upward move with call IV spike'
        }

    @staticmethod
    def fomo_rally() -> Dict:
        """FOMO rally scenario."""
        return {
            'name': 'FOMO Rally',
            'spot_change': 0.05,  # +5%
            'iv_multipliers': {
                'OTM_CALL': 0.15,  # +15% IV for calls
                'ATM': 0.05,       # +5% IV for ATM
                'OTM_PUT': -0.20,  # -20% IV for puts
                'default': 0.0
            },
            'days_pass': 0,
            'description': 'Fear of missing out rally'
        }

    @staticmethod
    def relief_rally() -> Dict:
        """Relief rally scenario."""
        return {
            'name': 'Relief Rally',
            'spot_change': 0.03,   # +3%
            'iv_change': -0.15,    # -15% uniform
            'days_pass': 0,
            'description': 'Relief rally with vol crush'
        }

    @staticmethod
    def one_day_pass() -> Dict:
        """One day passes (theta decay)."""
        return {
            'name': '1 Day Pass',
            'spot_change': 0.0,
            'dte_scaling': {
                '0-7': -0.01,      # -1% IV for weeklies
                '8-30': -0.01,     # -1% IV for monthlies
                '31-90': 0.0,      # No change
                '90+': 0.0
            },
            'days_pass': 1,
            'description': 'One day of theta decay'
        }

    @staticmethod
    def weekend() -> Dict:
        """Weekend passes (3 days theta)."""
        return {
            'name': 'Weekend',
            'spot_change': 0.0,
            'dte_scaling': {
                '0-7': -0.02,      # -2% IV for weeklies
                '8-30': -0.01,     # -1% IV for monthlies
                '31-90': 0.0,
                '90+': 0.0
            },
            'days_pass': 3,
            'description': 'Weekend theta decay'
        }

    @staticmethod
    def one_week() -> Dict:
        """One week passes."""
        return {
            'name': '1 Week',
            'spot_change': 0.0,
            'dte_scaling': {
                '0-7': -0.05,      # -5% IV
                '8-30': -0.03,     # -3% IV
                '31-90': -0.01,    # -1% IV
                '90+': 0.0
            },
            'days_pass': 7,
            'description': 'One week of theta decay'
        }

    @staticmethod
    def create_custom_scenario(name: str, spot_change: float,
                              iv_change: float = None,
                              iv_multipliers: Dict = None,
                              days_pass: int = 0) -> Dict:
        """
        Create a custom scenario.

        Args:
            name: Scenario name
            spot_change: Spot price change (as decimal, e.g., 0.05 for 5%)
            iv_change: Uniform IV change (optional)
            iv_multipliers: Dictionary of option type -> IV multiplier (optional)
            days_pass: Number of days passing

        Returns:
            Scenario parameters dictionary
        """
        scenario = {
            'name': name,
            'spot_change': spot_change,
            'days_pass': days_pass,
            'description': f'Custom: {spot_change:+.1%} spot'
        }

        if iv_change is not None:
            scenario['iv_change'] = iv_change
            scenario['description'] += f', {iv_change:+.1%} IV'

        if iv_multipliers:
            scenario['iv_multipliers'] = iv_multipliers

        return scenario
