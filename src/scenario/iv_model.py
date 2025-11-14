"""
Beta-Weighted IV Model for scenario analysis.
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class IVModel:
    """Beta-weighted implied volatility model."""

    @staticmethod
    def get_moneyness_beta(moneyness: float) -> float:
        """
        Calculate moneyness beta factor.

        Args:
            moneyness: Moneyness ratio (spot/strike for calls, strike/spot for puts)

        Returns:
            Beta multiplier
        """
        if moneyness < 0.95:  # Deep OTM
            return 1.3
        elif moneyness < 0.98:  # OTM
            return 1.2
        elif moneyness < 1.02:  # ATM
            return 1.0
        elif moneyness < 1.05:  # ITM
            return 0.9
        else:  # Deep ITM
            return 0.8

    @staticmethod
    def get_time_beta(dte: int) -> float:
        """
        Calculate time-to-expiration beta factor.

        Args:
            dte: Days to expiration

        Returns:
            Beta multiplier
        """
        if dte <= 7:  # 0-7 days
            return 1.5
        elif dte <= 30:  # 8-30 days
            return 1.0
        elif dte <= 90:  # 31-90 days
            return 0.7
        else:  # 90+ days
            return 0.5

    @staticmethod
    def calculate_iv_shift(base_iv: float, moneyness: float, dte: int,
                          scenario_multiplier: float, option_type: str = 'ATM') -> float:
        """
        Calculate new IV based on scenario.

        Args:
            base_iv: Current implied volatility (as decimal, e.g., 0.30 for 30%)
            moneyness: Moneyness ratio
            dte: Days to expiration
            scenario_multiplier: Scenario-specific IV change (as decimal)
            option_type: 'PUT', 'CALL', or 'ATM'

        Returns:
            New implied volatility
        """
        # Get beta factors
        moneyness_beta = IVModel.get_moneyness_beta(moneyness)
        time_beta = IVModel.get_time_beta(dte)

        # Adjust multiplier based on option type for certain scenarios
        adjusted_multiplier = scenario_multiplier

        # Apply weighted change
        iv_change = adjusted_multiplier * moneyness_beta * time_beta

        # Calculate new IV
        new_iv = base_iv * (1 + iv_change)

        # Floor at 1% IV, cap at 300%
        new_iv = max(0.01, min(3.0, new_iv))

        return new_iv

    @staticmethod
    def calculate_scenario_iv(base_iv: float, dte: int, scenario_params: Dict) -> float:
        """
        Calculate IV for a specific scenario with custom parameters.

        Args:
            base_iv: Current implied volatility
            dte: Days to expiration
            scenario_params: Dictionary with scenario-specific parameters

        Returns:
            New implied volatility
        """
        iv_change_base = scenario_params.get('iv_change', 0.0)

        # Apply DTE-based scaling if specified
        dte_scaling = scenario_params.get('dte_scaling', {})
        if dte_scaling:
            if dte <= 7:
                iv_change = dte_scaling.get('0-7', iv_change_base)
            elif dte <= 30:
                iv_change = dte_scaling.get('8-30', iv_change_base)
            elif dte <= 90:
                iv_change = dte_scaling.get('31-90', iv_change_base)
            else:
                iv_change = dte_scaling.get('90+', iv_change_base)
        else:
            iv_change = iv_change_base

        # Calculate new IV
        new_iv = base_iv * (1 + iv_change)

        # Floor and cap
        new_iv = max(0.01, min(3.0, new_iv))

        return new_iv


class IVShiftCalculator:
    """Helper class for calculating IV shifts across positions."""

    def __init__(self):
        self.model = IVModel()

    def calculate_position_iv(self, position, scenario_params: Dict,
                             underlying_price: float) -> float:
        """
        Calculate new IV for a position given scenario parameters.

        Args:
            position: Position object
            scenario_params: Scenario parameters
            underlying_price: New underlying price after scenario

        Returns:
            New implied volatility
        """
        if not position.is_option:
            return 0.0

        if position.implied_volatility is None:
            logger.warning(f"No IV data for {position.symbol}, using default 30%")
            base_iv = 0.30
        else:
            base_iv = position.implied_volatility

        dte = position.days_to_expiration()
        if dte is None:
            dte = 30  # Default

        # Calculate moneyness with new underlying price
        if position.option_type == 'C':
            moneyness = underlying_price / position.strike
        else:  # Put
            moneyness = position.strike / underlying_price

        # Determine option type category for IV scaling
        if moneyness < 0.95:
            if position.option_type == 'P':
                option_category = 'OTM_PUT'
            else:
                option_category = 'OTM_CALL'
        elif moneyness < 1.05:
            option_category = 'ATM'
        else:
            if position.option_type == 'P':
                option_category = 'ITM_PUT'
            else:
                option_category = 'ITM_CALL'

        # Get IV multiplier for this option type from scenario
        iv_multipliers = scenario_params.get('iv_multipliers', {})

        if option_category in iv_multipliers:
            scenario_multiplier = iv_multipliers[option_category]
        elif 'default' in iv_multipliers:
            scenario_multiplier = iv_multipliers['default']
        else:
            # Use DTE-based scaling if available
            new_iv = self.model.calculate_scenario_iv(base_iv, dte, scenario_params)
            return new_iv

        # Calculate with beta-weighted model
        new_iv = self.model.calculate_iv_shift(
            base_iv, moneyness, dte, scenario_multiplier, option_category
        )

        return new_iv
