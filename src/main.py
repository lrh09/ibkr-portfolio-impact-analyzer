"""
Main execution flow for Portfolio Risk Analyzer.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import load_config, setup_logging
from src.data_collection import IBKRConnectionManager, PositionTracker, MarketDataManager
from src.calendar import EventCalendar, EventDetector
from src.scenario import ScenarioTemplates
from src.valuation import PortfolioAggregator
from src.risk import RiskMetrics, RiskAlertSystem
from src.output import ReportGenerator
from src.automation import RealTimeMonitor, MarketHoursChecker

logger = logging.getLogger(__name__)


class PortfolioRiskAnalyzer:
    """Main application class for portfolio risk analysis."""

    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        Initialize portfolio risk analyzer.

        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)

        # Initialize components
        self.connection_manager = None
        self.position_tracker = None
        self.market_data_manager = None
        self.event_calendar = None
        self.event_detector = None
        self.portfolio_aggregator = None
        self.risk_alert_system = None
        self.report_generator = None
        self.monitor = None

        self.positions = []
        self.scenario_results = {}

    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Portfolio Risk Analyzer")

        # Setup IBKR connection
        ibkr_config = self.config.get('ibkr', {})
        self.connection_manager = IBKRConnectionManager(
            host=ibkr_config.get('host', '127.0.0.1'),
            port=ibkr_config.get('port', 7497),
            client_id=ibkr_config.get('client_id', 1),
            reconnect_attempts=ibkr_config.get('reconnect_attempts', 5),
            reconnect_delay=ibkr_config.get('reconnect_delay', 2.0)
        )

        # Connect to IBKR
        logger.info("Connecting to IBKR...")
        connected = await self.connection_manager.connect()

        if not connected:
            logger.error("Failed to connect to IBKR")
            return False

        # Initialize position tracker
        ib = self.connection_manager.get_ib()
        self.position_tracker = PositionTracker(ib)

        # Initialize market data manager
        db_path = self.config.get('data', {}).get('database_path', 'data/portfolio.db')
        self.market_data_manager = MarketDataManager(
            ib=ib,
            db_path=db_path,
            cache_ttl=self.config.get('data', {}).get('cache_ttl', 1),
            snapshot_interval=self.config.get('data', {}).get('snapshot_interval', 300)
        )

        # Initialize event calendar
        self.event_calendar = EventCalendar(db_path)
        self.event_detector = EventDetector(self.event_calendar)

        # Initialize valuation engine
        risk_free_rate = self.config.get('risk_free_rate', 0.05)
        self.portfolio_aggregator = PortfolioAggregator(risk_free_rate)

        # Initialize risk alert system
        self.risk_alert_system = RiskAlertSystem(self.config)

        # Initialize report generator
        export_path = self.config.get('reporting', {}).get('export_path', 'data/reports/')
        self.report_generator = ReportGenerator(export_path)

        # Initialize monitor
        self.monitor = RealTimeMonitor(self.config)

        logger.info("Initialization complete")
        return True

    async def load_positions(self):
        """Load portfolio positions."""
        logger.info("Loading positions from IBKR")
        positions_dict = await self.position_tracker.load_positions()
        self.positions = list(positions_dict.values())
        logger.info(f"Loaded {len(self.positions)} positions")

        # Subscribe to market data
        if self.positions:
            await self.market_data_manager.subscribe_positions(self.positions)

        return self.positions

    async def update_market_data(self):
        """Update market data for all positions."""
        logger.debug("Updating market data")
        await self.market_data_manager.update_positions_data(self.positions)

    async def run_scenario_analysis(self):
        """Run scenario analysis on portfolio."""
        logger.info("Running scenario analysis")

        if not self.positions:
            logger.warning("No positions to analyze")
            return {}

        # Get relevant scenarios based on calendar events
        if self.config.get('scenarios', {}).get('use_calendar', True):
            events = self.event_detector.check_events(self.positions)
            scenario_names = self.event_detector.get_relevant_scenarios(events)
            logger.info(f"Running {len(scenario_names)} scenarios based on calendar events")
        else:
            scenario_names = list(ScenarioTemplates.get_all_scenarios().keys())

        # Get scenario parameters
        all_scenarios = ScenarioTemplates.get_all_scenarios()
        scenarios_to_run = {name: all_scenarios[name] for name in scenario_names if name in all_scenarios}

        # Run scenarios
        self.scenario_results = self.portfolio_aggregator.run_multiple_scenarios(
            self.positions, scenarios_to_run
        )

        logger.info(f"Completed {len(self.scenario_results)} scenarios")
        return self.scenario_results

    async def check_risk_alerts(self):
        """Check for risk alerts."""
        logger.debug("Checking risk alerts")

        # Calculate portfolio metrics
        portfolio_metrics = RiskMetrics.calculate_portfolio_metrics(self.positions)

        # Check all risks
        alerts = self.risk_alert_system.check_all_risks(
            self.positions,
            self.scenario_results,
            portfolio_metrics
        )

        if alerts:
            logger.info(f"Generated {len(alerts)} risk alerts")

            # Log to file if configured
            if self.config.get('alerts', {}).get('enabled', True):
                log_file = self.config.get('alerts', {}).get('log_file')
                if log_file:
                    self.risk_alert_system.log_alerts(log_file)

                # Print to console if configured
                if self.config.get('alerts', {}).get('console', True):
                    print("\n" + self.risk_alert_system.format_alert_summary())

        return alerts

    async def generate_report(self):
        """Generate and display portfolio report."""
        logger.info("Generating portfolio report")

        # Calculate portfolio metrics
        portfolio_metrics = RiskMetrics.calculate_portfolio_metrics(self.positions)

        # Get risk alerts
        alerts = self.risk_alert_system.alerts

        # Generate full report
        report = self.report_generator.generate_full_report(
            self.positions,
            self.scenario_results,
            portfolio_metrics,
            alerts
        )

        # Print to console
        self.report_generator.print_report(report)

        # Save to files
        saved_files = self.report_generator.save_full_report(report)
        logger.info(f"Report saved to: {saved_files}")

        return report

    async def save_snapshot(self):
        """Save current portfolio snapshot."""
        logger.debug("Saving portfolio snapshot")
        self.market_data_manager.save_snapshot(self.positions)

    async def start_of_day_tasks(self):
        """Execute start-of-day tasks."""
        logger.info("=== START OF DAY TASKS ===")

        # Load positions
        await self.load_positions()

        # Update calendar if enabled
        if self.config.get('scenarios', {}).get('auto_detect_earnings', True):
            logger.info("Updating earnings calendar")
            symbols = list(set([p.underlying if p.is_option else p.symbol for p in self.positions]))
            self.event_calendar.load_earnings_dates(symbols)

        logger.info("Start-of-day tasks complete")

    async def end_of_day_tasks(self):
        """Execute end-of-day tasks."""
        logger.info("=== END OF DAY TASKS ===")

        # Run final analysis
        await self.run_scenario_analysis()
        await self.check_risk_alerts()

        # Generate daily report
        await self.generate_report()

        # Save final snapshot
        await self.save_snapshot()

        logger.info("End-of-day tasks complete")

    async def run_once(self):
        """Run analysis once (for manual execution)."""
        logger.info("=== RUNNING SINGLE ANALYSIS ===")

        # Initialize
        if not await self.initialize():
            logger.error("Initialization failed")
            return

        try:
            # Load positions
            await self.load_positions()

            # Update market data
            await self.update_market_data()

            # Run scenario analysis
            await self.run_scenario_analysis()

            # Check alerts
            await self.check_risk_alerts()

            # Generate report
            await self.generate_report()

        finally:
            # Disconnect
            self.connection_manager.disconnect()

    async def run_monitoring(self):
        """Run continuous monitoring."""
        logger.info("=== STARTING CONTINUOUS MONITORING ===")

        # Initialize
        if not await self.initialize():
            logger.error("Initialization failed")
            return

        try:
            # Check if market is open
            if MarketHoursChecker.is_market_hours():
                logger.info("Market is open - starting monitoring")
            else:
                minutes_until_open = MarketHoursChecker.time_until_market_open()
                logger.info(f"Market is closed - opens in {minutes_until_open} minutes")

            # Start monitoring
            await self.monitor.start_monitoring(
                update_callback=self.update_market_data,
                scenario_callback=self.run_scenario_analysis,
                snapshot_callback=self.save_snapshot
            )

        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        finally:
            # Stop monitoring
            self.monitor.stop_monitoring()
            self.connection_manager.disconnect()


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging(log_level='INFO', log_file='logs/portfolio_analyzer.log')

    logger.info("="*80)
    logger.info("PORTFOLIO RISK ANALYZER")
    logger.info("="*80)

    # Create analyzer
    analyzer = PortfolioRiskAnalyzer()

    # Run once (can be changed to run_monitoring() for continuous operation)
    await analyzer.run_once()


if __name__ == "__main__":
    asyncio.run(main())
