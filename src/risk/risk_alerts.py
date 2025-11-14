"""
Risk alert system for monitoring portfolio risks.
"""
import logging
from typing import List, Dict
from datetime import datetime
from ..data_collection.position import Position

logger = logging.getLogger(__name__)


class RiskAlert:
    """Represents a risk alert."""

    def __init__(self, alert_type: str, severity: str, message: str, details: Dict = None):
        """
        Initialize risk alert.

        Args:
            alert_type: Type of alert
            severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
            message: Alert message
            details: Additional details
        """
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()

    def __repr__(self):
        return f"[{self.severity}] {self.alert_type}: {self.message}"


class RiskAlertSystem:
    """Monitor and generate risk alerts."""

    def __init__(self, config: Dict):
        """
        Initialize risk alert system.

        Args:
            config: Configuration dictionary with risk limits
        """
        self.config = config
        self.alerts = []

    def check_all_risks(self, positions: List[Position],
                       scenario_results: Dict[str, Dict],
                       portfolio_metrics: Dict) -> List[RiskAlert]:
        """
        Check all risk conditions and generate alerts.

        Args:
            positions: List of positions
            scenario_results: Dictionary of scenario results
            portfolio_metrics: Portfolio metrics dictionary

        Returns:
            List of RiskAlert objects
        """
        self.alerts = []

        # Check scenario losses
        self._check_scenario_losses(scenario_results)

        # Check position concentration
        self._check_position_concentration(positions, portfolio_metrics)

        # Check earnings before expiration
        self._check_earnings_exposure(positions)

        # Check IV rank extremes
        self._check_iv_extremes(positions)

        # Check Greeks exposure
        self._check_greeks_exposure(portfolio_metrics)

        # Check stale data
        self._check_stale_data(positions)

        return self.alerts

    def _check_scenario_losses(self, scenario_results: Dict[str, Dict]):
        """Check for scenarios with excessive losses."""
        max_loss_threshold = self.config.get('risk_limits', {}).get('max_portfolio_loss', 0.15)

        for scenario_name, result in scenario_results.items():
            pnl_percent = result['portfolio_pnl_percent'] / 100  # Convert to decimal

            if pnl_percent < -max_loss_threshold:
                alert = RiskAlert(
                    alert_type='SCENARIO_LOSS',
                    severity='HIGH' if pnl_percent < -max_loss_threshold * 1.5 else 'MEDIUM',
                    message=f"Scenario '{scenario_name}' shows {pnl_percent:.1%} loss (threshold: {max_loss_threshold:.1%})",
                    details={
                        'scenario': scenario_name,
                        'pnl_percent': pnl_percent,
                        'pnl_dollar': result['portfolio_pnl'],
                        'threshold': max_loss_threshold
                    }
                )
                self.alerts.append(alert)
                logger.warning(alert)

    def _check_position_concentration(self, positions: List[Position], portfolio_metrics: Dict):
        """Check for excessive position concentration."""
        threshold = self.config.get('risk_limits', {}).get('position_concentration', 0.25)
        total_value = portfolio_metrics.get('total_value', 0)

        for position in positions:
            if total_value > 0:
                concentration = position.position_value / total_value

                if concentration > threshold:
                    alert = RiskAlert(
                        alert_type='CONCENTRATION',
                        severity='HIGH' if concentration > threshold * 1.5 else 'MEDIUM',
                        message=f"Position {position.symbol} represents {concentration:.1%} of portfolio (threshold: {threshold:.1%})",
                        details={
                            'symbol': position.symbol,
                            'concentration': concentration,
                            'position_value': position.position_value,
                            'threshold': threshold
                        }
                    )
                    self.alerts.append(alert)
                    logger.warning(alert)

    def _check_earnings_exposure(self, positions: List[Position]):
        """Check for options with earnings before expiration."""
        # This would integrate with calendar events
        # Simplified version here
        for position in positions:
            if position.is_option and position.days_to_expiration():
                dte = position.days_to_expiration()

                # Placeholder: In real implementation, check against calendar
                # For now, flag short-dated options as potential earnings risk
                if dte < 7:
                    alert = RiskAlert(
                        alert_type='EARNINGS_RISK',
                        severity='MEDIUM',
                        message=f"Option {position.symbol} expires in {dte} days - check for earnings",
                        details={
                            'symbol': position.symbol,
                            'days_to_expiration': dte,
                            'expiration_date': position.expiration
                        }
                    )
                    # Only add if significant position
                    if abs(position.position_value) > 1000:
                        self.alerts.append(alert)
                        logger.info(alert)

    def _check_iv_extremes(self, positions: List[Position]):
        """Check for extreme IV rank positions."""
        for position in positions:
            if position.is_option and position.implied_volatility:
                iv = position.implied_volatility

                # Simplified: flag very high or very low IV
                # In real implementation, calculate IV rank from historical data
                if iv > 0.80:  # 80% IV
                    alert = RiskAlert(
                        alert_type='HIGH_IV',
                        severity='LOW',
                        message=f"Position {position.symbol} has high IV: {iv:.1%} - consider selling",
                        details={
                            'symbol': position.symbol,
                            'iv': iv,
                            'recommendation': 'Consider selling premium'
                        }
                    )
                    self.alerts.append(alert)

                elif iv < 0.15:  # 15% IV
                    alert = RiskAlert(
                        alert_type='LOW_IV',
                        severity='LOW',
                        message=f"Position {position.symbol} has low IV: {iv:.1%} - consider buying",
                        details={
                            'symbol': position.symbol,
                            'iv': iv,
                            'recommendation': 'Consider buying premium'
                        }
                    )
                    self.alerts.append(alert)

    def _check_greeks_exposure(self, portfolio_metrics: Dict):
        """Check for excessive Greeks exposure."""
        vega_limit = self.config.get('risk_limits', {}).get('vega_limit', 10000)
        gamma_limit = self.config.get('risk_limits', {}).get('gamma_limit', 5000)

        total_vega = abs(portfolio_metrics.get('vega', 0))
        total_gamma = abs(portfolio_metrics.get('gamma', 0))

        if total_vega > vega_limit:
            alert = RiskAlert(
                alert_type='VEGA_EXPOSURE',
                severity='MEDIUM',
                message=f"Total vega exposure ${total_vega:,.0f} exceeds limit ${vega_limit:,.0f}",
                details={
                    'total_vega': total_vega,
                    'limit': vega_limit,
                    'excess': total_vega - vega_limit
                }
            )
            self.alerts.append(alert)
            logger.warning(alert)

        if total_gamma > gamma_limit:
            alert = RiskAlert(
                alert_type='GAMMA_EXPOSURE',
                severity='MEDIUM',
                message=f"Total gamma exposure {total_gamma:,.2f} exceeds limit {gamma_limit:,.2f}",
                details={
                    'total_gamma': total_gamma,
                    'limit': gamma_limit,
                    'excess': total_gamma - gamma_limit
                }
            )
            self.alerts.append(alert)
            logger.warning(alert)

        # Check for short gamma in stressed market
        if portfolio_metrics.get('gamma', 0) < -1000:
            alert = RiskAlert(
                alert_type='SHORT_GAMMA',
                severity='HIGH',
                message=f"Portfolio is short gamma: {portfolio_metrics['gamma']:,.2f}",
                details={
                    'gamma': portfolio_metrics['gamma'],
                    'warning': 'High risk in volatile markets'
                }
            )
            self.alerts.append(alert)
            logger.warning(alert)

    def _check_stale_data(self, positions: List[Position]):
        """Check for stale market data."""
        max_age = self.config.get('data', {}).get('max_data_age', 60)

        for position in positions:
            if position.last_update:
                age = (datetime.now() - position.last_update).total_seconds()

                if age > max_age:
                    alert = RiskAlert(
                        alert_type='STALE_DATA',
                        severity='LOW',
                        message=f"Data for {position.symbol} is {age:.0f}s old (max: {max_age}s)",
                        details={
                            'symbol': position.symbol,
                            'age_seconds': age,
                            'last_update': position.last_update,
                            'max_age': max_age
                        }
                    )
                    self.alerts.append(alert)

    def get_alerts_by_severity(self, severity: str) -> List[RiskAlert]:
        """
        Get alerts filtered by severity.

        Args:
            severity: Severity level to filter

        Returns:
            List of alerts matching severity
        """
        return [alert for alert in self.alerts if alert.severity == severity]

    def get_critical_alerts(self) -> List[RiskAlert]:
        """Get all critical alerts."""
        return self.get_alerts_by_severity('CRITICAL')

    def has_critical_alerts(self) -> bool:
        """Check if there are any critical alerts."""
        return len(self.get_critical_alerts()) > 0

    def format_alert_summary(self) -> str:
        """
        Format alert summary for display.

        Returns:
            Formatted string with alert summary
        """
        if not self.alerts:
            return "No alerts"

        summary = [f"Total Alerts: {len(self.alerts)}"]

        # Count by severity
        severity_counts = {}
        for alert in self.alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1

        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                summary.append(f"  {severity}: {count}")

        # List critical and high alerts
        important = [a for a in self.alerts if a.severity in ['CRITICAL', 'HIGH']]
        if important:
            summary.append("\nImportant Alerts:")
            for alert in important:
                summary.append(f"  - {alert}")

        return "\n".join(summary)

    def log_alerts(self, log_file: str = None):
        """
        Log alerts to file.

        Args:
            log_file: Path to log file (optional)
        """
        if log_file:
            try:
                with open(log_file, 'a') as f:
                    f.write(f"\n=== Alert Log: {datetime.now()} ===\n")
                    for alert in self.alerts:
                        f.write(f"{alert}\n")
                        f.write(f"  Details: {alert.details}\n")
                    f.write("\n")
            except Exception as e:
                logger.error(f"Error writing to alert log: {e}")

    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts = []
