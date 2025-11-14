"""
Risk metrics calculation module.
"""
import logging
from typing import List, Dict
import pandas as pd
import numpy as np
from ..data_collection.position import Position

logger = logging.getLogger(__name__)


class RiskMetrics:
    """Calculate portfolio risk metrics."""

    @staticmethod
    def calculate_position_metrics(position: Position, portfolio_value: float) -> Dict:
        """
        Calculate metrics for a single position.

        Args:
            position: Position object
            portfolio_value: Total portfolio value

        Returns:
            Dictionary with position metrics
        """
        position_pnl = position.get_pnl()
        position_pnl_percent = position.get_pnl_percent()

        # Calculate position concentration
        concentration = (position.position_value / portfolio_value * 100) if portfolio_value > 0 else 0

        metrics = {
            'symbol': position.symbol,
            'type': 'OPTION' if position.is_option else 'STOCK',
            'quantity': position.quantity,
            'entry_price': position.entry_price,
            'current_price': position.current_price,
            'position_value': position.position_value,
            'pnl': position_pnl,
            'pnl_percent': position_pnl_percent,
            'concentration': concentration,
            'days_to_expiration': position.days_to_expiration() if position.is_option else None
        }

        # Add Greeks for options
        if position.is_option:
            metrics.update({
                'delta': position.delta,
                'gamma': position.gamma,
                'theta': position.theta,
                'vega': position.vega,
                'rho': position.rho,
                'implied_volatility': position.implied_volatility,
                'strike': position.strike,
                'option_type': position.option_type,
                'underlying': position.underlying,
                'moneyness': position.moneyness() if position.strike else None,
                'is_itm': position.is_itm() if position.strike else None
            })

        return metrics

    @staticmethod
    def calculate_portfolio_metrics(positions: List[Position]) -> Dict:
        """
        Calculate portfolio-level metrics.

        Args:
            positions: List of positions

        Returns:
            Dictionary with portfolio metrics
        """
        total_value = sum(p.position_value for p in positions)
        total_pnl = sum(p.get_pnl() for p in positions)

        # Aggregate Greeks
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0

        stock_value = 0.0
        option_value = 0.0

        for position in positions:
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

        # Calculate concentration risk
        position_values = [p.position_value for p in positions]
        max_position = max(position_values) if position_values else 0
        max_concentration = (max_position / total_value * 100) if total_value > 0 else 0

        return {
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_pnl_percent': (total_pnl / (total_value - total_pnl) * 100) if (total_value - total_pnl) > 0 else 0,
            'stock_value': stock_value,
            'option_value': option_value,
            'num_positions': len(positions),
            'num_stock_positions': len([p for p in positions if not p.is_option]),
            'num_option_positions': len([p for p in positions if p.is_option]),
            'delta': total_delta,
            'gamma': total_gamma,
            'theta': total_theta,
            'vega': total_vega,
            'rho': total_rho,
            'max_concentration': max_concentration
        }

    @staticmethod
    def calculate_var(scenario_results: Dict[str, Dict], confidence: float = 0.95) -> Dict:
        """
        Calculate Value at Risk.

        Args:
            scenario_results: Dictionary of scenario results
            confidence: Confidence level (default 95%)

        Returns:
            Dictionary with VaR metrics
        """
        pnls = [result['portfolio_pnl'] for result in scenario_results.values()]

        if not pnls:
            return {'var_95': 0.0, 'var_99': 0.0}

        pnls_sorted = sorted(pnls)

        # 95% VaR
        index_95 = int(0.05 * len(pnls_sorted))
        var_95 = pnls_sorted[index_95] if index_95 < len(pnls_sorted) else pnls_sorted[0]

        # 99% VaR
        index_99 = int(0.01 * len(pnls_sorted))
        var_99 = pnls_sorted[index_99] if index_99 < len(pnls_sorted) else pnls_sorted[0]

        return {
            'var_95': var_95,
            'var_95_percent': (var_95 / scenario_results[list(scenario_results.keys())[0]]['current_portfolio_value'] * 100)
                             if scenario_results else 0,
            'var_99': var_99,
            'var_99_percent': (var_99 / scenario_results[list(scenario_results.keys())[0]]['current_portfolio_value'] * 100)
                             if scenario_results else 0
        }

    @staticmethod
    def calculate_iv_rank(position: Position, historical_ivs: List[float]) -> Dict:
        """
        Calculate IV rank and percentile.

        Args:
            position: Position object
            historical_ivs: List of historical IV values

        Returns:
            Dictionary with IV rank metrics
        """
        if not position.is_option or position.implied_volatility is None:
            return {'iv_rank': None, 'iv_percentile': None}

        if not historical_ivs:
            return {'iv_rank': None, 'iv_percentile': None}

        current_iv = position.implied_volatility
        min_iv = min(historical_ivs)
        max_iv = max(historical_ivs)

        # IV Rank (0-100)
        if max_iv - min_iv > 0:
            iv_rank = ((current_iv - min_iv) / (max_iv - min_iv)) * 100
        else:
            iv_rank = 50

        # IV Percentile
        below_current = sum(1 for iv in historical_ivs if iv < current_iv)
        iv_percentile = (below_current / len(historical_ivs)) * 100

        return {
            'iv_rank': iv_rank,
            'iv_percentile': iv_percentile,
            'current_iv': current_iv,
            'min_iv': min_iv,
            'max_iv': max_iv
        }

    @staticmethod
    def calculate_correlation_matrix(positions: List[Position],
                                     scenario_results: Dict[str, Dict]) -> pd.DataFrame:
        """
        Calculate correlation matrix between positions based on scenario results.

        Args:
            positions: List of positions
            scenario_results: Dictionary of scenario results

        Returns:
            DataFrame with correlation matrix
        """
        # Extract P&L for each position across scenarios
        position_pnls = {}

        for position in positions:
            symbol = position.symbol
            position_pnls[symbol] = []

        for scenario_name, result in scenario_results.items():
            for pos_result in result['position_results']:
                symbol = pos_result['symbol']
                if symbol in position_pnls:
                    position_pnls[symbol].append(pos_result['pnl'])

        # Create DataFrame
        df = pd.DataFrame(position_pnls)

        # Calculate correlation
        if not df.empty:
            corr_matrix = df.corr()
            return corr_matrix
        else:
            return pd.DataFrame()

    @staticmethod
    def identify_risk_concentrations(positions: List[Position],
                                     portfolio_value: float,
                                     threshold: float = 0.25) -> List[Dict]:
        """
        Identify positions exceeding concentration threshold.

        Args:
            positions: List of positions
            portfolio_value: Total portfolio value
            threshold: Concentration threshold (default 25%)

        Returns:
            List of positions exceeding threshold
        """
        concentrations = []

        for position in positions:
            concentration = (position.position_value / portfolio_value) if portfolio_value > 0 else 0

            if concentration > threshold:
                concentrations.append({
                    'symbol': position.symbol,
                    'concentration': concentration * 100,
                    'value': position.position_value,
                    'threshold': threshold * 100
                })

        return sorted(concentrations, key=lambda x: x['concentration'], reverse=True)

    @staticmethod
    def calculate_greeks_exposure(positions: List[Position]) -> Dict:
        """
        Calculate portfolio Greeks exposure metrics.

        Args:
            positions: List of positions

        Returns:
            Dictionary with Greeks exposure
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0

        delta_long = 0.0
        delta_short = 0.0
        gamma_long = 0.0
        gamma_short = 0.0

        for position in positions:
            if position.is_option:
                if position.delta is not None:
                    pos_delta = position.delta * position.quantity * position.contract_multiplier
                    total_delta += pos_delta
                    if pos_delta > 0:
                        delta_long += pos_delta
                    else:
                        delta_short += pos_delta

                if position.gamma is not None:
                    pos_gamma = position.gamma * position.quantity * position.contract_multiplier
                    total_gamma += pos_gamma
                    if pos_gamma > 0:
                        gamma_long += pos_gamma
                    else:
                        gamma_short += pos_gamma

                if position.theta is not None:
                    total_theta += position.theta * position.quantity * position.contract_multiplier

                if position.vega is not None:
                    total_vega += position.vega * position.quantity * position.contract_multiplier
            else:
                # Stock delta
                total_delta += position.quantity
                if position.quantity > 0:
                    delta_long += position.quantity
                else:
                    delta_short += position.quantity

        return {
            'total_delta': total_delta,
            'delta_long': delta_long,
            'delta_short': delta_short,
            'net_delta': total_delta,
            'total_gamma': total_gamma,
            'gamma_long': gamma_long,
            'gamma_short': gamma_short,
            'total_theta': total_theta,
            'total_vega': total_vega
        }
