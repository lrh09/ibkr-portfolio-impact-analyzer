"""
Portfolio aggregation and scenario valuation.
"""
import logging
from typing import List, Dict
import pandas as pd
from datetime import datetime, timedelta
from .black_scholes import BlackScholesCalculator
from ..data_collection.position import Position
from ..scenario.iv_model import IVShiftCalculator

logger = logging.getLogger(__name__)


class PortfolioAggregator:
    """Aggregates portfolio values and runs scenario analysis."""

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize portfolio aggregator.

        Args:
            risk_free_rate: Annual risk-free rate
        """
        self.bs_calculator = BlackScholesCalculator(risk_free_rate)
        self.iv_calculator = IVShiftCalculator()

    def calculate_current_portfolio_value(self, positions: List[Position]) -> Dict:
        """
        Calculate current portfolio value and metrics.

        Args:
            positions: List of positions

        Returns:
            Dictionary with portfolio metrics
        """
        total_value = 0.0
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0

        stock_value = 0.0
        option_value = 0.0

        for position in positions:
            total_value += position.position_value

            if position.is_option:
                option_value += position.position_value

                # Aggregate Greeks (accounting for quantity and multiplier)
                if position.delta is not None:
                    total_delta += position.delta * position.quantity * position.contract_multiplier
                if position.gamma is not None:
                    total_gamma += position.gamma * position.quantity * position.contract_multiplier
                if position.theta is not None:
                    total_theta += position.theta * position.quantity * position.contract_multiplier
                if position.vega is not None:
                    total_vega += position.vega * position.quantity * position.contract_multiplier
                if position.rho is not None:
                    total_rho += position.rho * position.quantity * position.contract_multiplier
            else:
                stock_value += position.position_value
                # Stock has delta of 1 per share
                total_delta += position.quantity

        return {
            'total_value': total_value,
            'stock_value': stock_value,
            'option_value': option_value,
            'delta': total_delta,
            'gamma': total_gamma,
            'theta': total_theta,
            'vega': total_vega,
            'rho': total_rho
        }

    def run_scenario(self, positions: List[Position], scenario: Dict) -> Dict:
        """
        Run a scenario on the portfolio.

        Args:
            positions: List of positions
            scenario: Scenario parameters

        Returns:
            Dictionary with scenario results
        """
        scenario_name = scenario.get('name', 'Unknown')
        spot_change = scenario.get('spot_change', 0.0)
        days_pass = scenario.get('days_pass', 0)

        logger.debug(f"Running scenario: {scenario_name}")

        # Calculate current portfolio value
        current_metrics = self.calculate_current_portfolio_value(positions)
        current_value = current_metrics['total_value']

        # Calculate new values for each position
        new_total_value = 0.0
        position_results = []

        # Group positions by underlying for price changes
        underlying_prices = {}

        for position in positions:
            try:
                if position.is_option:
                    underlying = position.underlying
                    if underlying not in underlying_prices:
                        # Get current underlying price (use position data or estimate)
                        current_underlying = position.current_price  # Simplified
                        underlying_prices[underlying] = current_underlying * (1 + spot_change)
                else:
                    underlying_prices[position.symbol] = position.current_price * (1 + spot_change)

            except Exception as e:
                logger.error(f"Error calculating price for {position.symbol}: {e}")

        # Calculate new values
        for position in positions:
            try:
                if position.is_option:
                    new_value = self._calculate_option_scenario_value(
                        position, scenario, underlying_prices.get(position.underlying)
                    )
                else:
                    new_value = self._calculate_stock_scenario_value(
                        position, scenario, underlying_prices.get(position.symbol)
                    )

                pnl = new_value - position.position_value
                pnl_percent = (pnl / position.position_value * 100) if position.position_value != 0 else 0

                position_results.append({
                    'symbol': position.symbol,
                    'type': 'OPTION' if position.is_option else 'STOCK',
                    'current_value': position.position_value,
                    'scenario_value': new_value,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent
                })

                new_total_value += new_value

            except Exception as e:
                logger.error(f"Error in scenario for {position.symbol}: {e}")
                new_total_value += position.position_value  # Use current value as fallback

        # Portfolio-level metrics
        portfolio_pnl = new_total_value - current_value
        portfolio_pnl_percent = (portfolio_pnl / current_value * 100) if current_value != 0 else 0

        # Find best and worst positions
        sorted_results = sorted(position_results, key=lambda x: x['pnl'])
        worst_position = sorted_results[0] if sorted_results else None
        best_position = sorted_results[-1] if sorted_results else None

        return {
            'scenario_name': scenario_name,
            'current_portfolio_value': current_value,
            'scenario_portfolio_value': new_total_value,
            'portfolio_pnl': portfolio_pnl,
            'portfolio_pnl_percent': portfolio_pnl_percent,
            'worst_position': worst_position,
            'best_position': best_position,
            'position_results': position_results,
            'current_metrics': current_metrics
        }

    def _calculate_stock_scenario_value(self, position: Position, scenario: Dict,
                                        new_price: float) -> float:
        """Calculate new stock value in scenario."""
        if new_price is None:
            new_price = position.current_price * (1 + scenario.get('spot_change', 0.0))

        return new_price * position.quantity

    def _calculate_option_scenario_value(self, position: Position, scenario: Dict,
                                         new_underlying_price: float) -> float:
        """Calculate new option value in scenario."""
        if new_underlying_price is None:
            new_underlying_price = position.current_price * (1 + scenario.get('spot_change', 0.0))

        # Calculate new IV
        new_iv = self.iv_calculator.calculate_position_iv(
            position, scenario, new_underlying_price
        )

        # Calculate new time to expiration
        days_pass = scenario.get('days_pass', 0)
        dte = position.days_to_expiration()
        if dte is None:
            dte = 30  # Default

        new_dte = max(0, dte - days_pass)
        time_to_expiry = new_dte / 365.0

        # Calculate new option price
        new_price = self.bs_calculator.calculate_option_price(
            spot=new_underlying_price,
            strike=position.strike,
            time_to_expiry=time_to_expiry,
            volatility=new_iv,
            option_type=position.option_type
        )

        # Calculate position value
        new_value = new_price * position.quantity * position.contract_multiplier

        return new_value

    def run_multiple_scenarios(self, positions: List[Position],
                               scenarios: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Run multiple scenarios on the portfolio.

        Args:
            positions: List of positions
            scenarios: Dictionary of scenario name -> parameters

        Returns:
            Dictionary of scenario name -> results
        """
        results = {}

        for scenario_name, scenario_params in scenarios.items():
            try:
                result = self.run_scenario(positions, scenario_params)
                results[scenario_name] = result
                logger.debug(f"Completed scenario: {scenario_name}")

            except Exception as e:
                logger.error(f"Error running scenario {scenario_name}: {e}")

        return results

    def calculate_var(self, scenario_results: Dict[str, Dict],
                     confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk from scenario results.

        Args:
            scenario_results: Dictionary of scenario results
            confidence: Confidence level (e.g., 0.95 for 95% VaR)

        Returns:
            VaR value (negative for loss)
        """
        pnls = [result['portfolio_pnl'] for result in scenario_results.values()]

        if not pnls:
            return 0.0

        pnls_sorted = sorted(pnls)
        index = int((1 - confidence) * len(pnls_sorted))
        var = pnls_sorted[index] if index < len(pnls_sorted) else pnls_sorted[0]

        return var

    def calculate_max_drawdown(self, scenario_results: Dict[str, Dict]) -> Dict:
        """
        Calculate maximum drawdown across scenarios.

        Args:
            scenario_results: Dictionary of scenario results

        Returns:
            Dictionary with max drawdown info
        """
        worst_scenario = None
        worst_pnl = 0.0

        for scenario_name, result in scenario_results.values():
            pnl = result['portfolio_pnl']
            if pnl < worst_pnl:
                worst_pnl = pnl
                worst_scenario = scenario_name

        return {
            'max_drawdown': worst_pnl,
            'worst_scenario': worst_scenario
        }

    def create_scenario_summary_df(self, scenario_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        Create scenario summary DataFrame.

        Args:
            scenario_results: Dictionary of scenario results

        Returns:
            DataFrame with scenario summary
        """
        rows = []

        for scenario_name, result in scenario_results.items():
            worst_pos = result.get('worst_position', {})
            best_pos = result.get('best_position', {})

            rows.append({
                'Scenario': scenario_name,
                'Portfolio P&L': result['portfolio_pnl'],
                '% Change': result['portfolio_pnl_percent'],
                'Worst Position': worst_pos.get('symbol', 'N/A') if worst_pos else 'N/A',
                'Worst P&L': worst_pos.get('pnl', 0) if worst_pos else 0,
                'Best Position': best_pos.get('symbol', 'N/A') if best_pos else 'N/A',
                'Best P&L': best_pos.get('pnl', 0) if best_pos else 0
            })

        df = pd.DataFrame(rows)
        return df.sort_values('Portfolio P&L')

    def create_position_detail_df(self, scenario_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        Create position detail DataFrame.

        Args:
            scenario_results: Dictionary of scenario results

        Returns:
            DataFrame with position details across scenarios
        """
        # Collect all positions
        all_positions = set()
        for result in scenario_results.values():
            for pos_result in result['position_results']:
                all_positions.add(pos_result['symbol'])

        rows = []

        for symbol in all_positions:
            row = {'Position': symbol}

            # Get current value (from any scenario)
            for result in scenario_results.values():
                for pos_result in result['position_results']:
                    if pos_result['symbol'] == symbol:
                        row['Current'] = pos_result['current_value']
                        break
                if 'Current' in row:
                    break

            # Get scenario values
            max_gain = 0
            max_loss = 0

            for scenario_name, result in scenario_results.items():
                for pos_result in result['position_results']:
                    if pos_result['symbol'] == symbol:
                        pnl = pos_result['pnl']
                        row[scenario_name] = pnl

                        max_gain = max(max_gain, pnl)
                        max_loss = min(max_loss, pnl)

            row['Max Loss'] = max_loss
            row['Max Gain'] = max_gain

            rows.append(row)

        df = pd.DataFrame(rows)
        return df
