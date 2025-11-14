"""
Scheduler for automated portfolio monitoring and analysis.
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Callable, Dict
import schedule

logger = logging.getLogger(__name__)


class PortfolioScheduler:
    """Scheduler for automated portfolio tasks."""

    def __init__(self, config: Dict):
        """
        Initialize scheduler.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.update_interval = config.get('performance', {}).get('update_interval', 60)
        self.snapshot_interval = config.get('data', {}).get('snapshot_interval', 300)
        self.running = False

    def schedule_tasks(self, tasks: Dict[str, Callable]):
        """
        Schedule tasks based on configuration.

        Args:
            tasks: Dictionary of task_name -> callable
        """
        # Start-of-day tasks
        if 'start_of_day' in tasks:
            schedule.every().day.at("09:00").do(tasks['start_of_day'])
            logger.info("Scheduled start-of-day task for 09:00")

        # Real-time update tasks
        if 'update_data' in tasks:
            schedule.every(self.update_interval).seconds.do(tasks['update_data'])
            logger.info(f"Scheduled data updates every {self.update_interval}s")

        # Scenario analysis tasks
        if 'run_scenarios' in tasks:
            scenario_interval = self.snapshot_interval  # Every 5 minutes by default
            schedule.every(scenario_interval).seconds.do(tasks['run_scenarios'])
            logger.info(f"Scheduled scenario analysis every {scenario_interval}s")

        # Snapshot tasks
        if 'save_snapshot' in tasks:
            schedule.every(self.snapshot_interval).seconds.do(tasks['save_snapshot'])
            logger.info(f"Scheduled snapshots every {self.snapshot_interval}s")

        # End-of-day tasks
        if 'end_of_day' in tasks:
            schedule.every().day.at("16:30").do(tasks['end_of_day'])
            logger.info("Scheduled end-of-day task for 16:30")

    async def run_scheduled_tasks(self):
        """Run scheduled tasks in async loop."""
        self.running = True
        logger.info("Scheduler started")

        while self.running:
            schedule.run_pending()
            await asyncio.sleep(1)

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        logger.info("Scheduler stopped")


class RealTimeMonitor:
    """Real-time portfolio monitoring."""

    def __init__(self, config: Dict):
        """
        Initialize real-time monitor.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.monitoring = False
        self.last_update = None
        self.last_scenario_run = None
        self.last_snapshot = None

    async def start_monitoring(self, update_callback: Callable,
                              scenario_callback: Callable,
                              snapshot_callback: Callable):
        """
        Start real-time monitoring loop.

        Args:
            update_callback: Async function to update market data
            scenario_callback: Async function to run scenarios
            snapshot_callback: Async function to save snapshots
        """
        self.monitoring = True
        update_interval = self.config.get('performance', {}).get('update_interval', 60)
        scenario_interval = self.config.get('data', {}).get('snapshot_interval', 300)

        logger.info("Real-time monitoring started")

        while self.monitoring:
            try:
                current_time = datetime.now()

                # Update market data
                if (self.last_update is None or
                    (current_time - self.last_update).total_seconds() >= update_interval):
                    logger.debug("Running market data update")
                    await update_callback()
                    self.last_update = current_time

                # Run scenarios
                if (self.last_scenario_run is None or
                    (current_time - self.last_scenario_run).total_seconds() >= scenario_interval):
                    logger.debug("Running scenario analysis")
                    await scenario_callback()
                    self.last_scenario_run = current_time

                # Save snapshot
                if (self.last_snapshot is None or
                    (current_time - self.last_snapshot).total_seconds() >= scenario_interval):
                    logger.debug("Saving data snapshot")
                    await snapshot_callback()
                    self.last_snapshot = current_time

                # Sleep for a bit before next iteration
                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying

    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
        logger.info("Real-time monitoring stopped")


class MarketHoursChecker:
    """Check if market is open."""

    @staticmethod
    def is_market_hours(current_time: datetime = None) -> bool:
        """
        Check if current time is during market hours.

        Args:
            current_time: Time to check (default: now)

        Returns:
            True if market is open
        """
        if current_time is None:
            current_time = datetime.now()

        # Check if weekday
        if current_time.weekday() >= 5:  # Saturday or Sunday
            return False

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = time(9, 30)
        market_close = time(16, 0)

        current_time_only = current_time.time()

        return market_open <= current_time_only <= market_close

    @staticmethod
    def is_pre_market(current_time: datetime = None) -> bool:
        """
        Check if pre-market hours.

        Args:
            current_time: Time to check (default: now)

        Returns:
            True if pre-market
        """
        if current_time is None:
            current_time = datetime.now()

        if current_time.weekday() >= 5:
            return False

        pre_market_start = time(4, 0)
        market_open = time(9, 30)

        current_time_only = current_time.time()

        return pre_market_start <= current_time_only < market_open

    @staticmethod
    def is_after_hours(current_time: datetime = None) -> bool:
        """
        Check if after-hours.

        Args:
            current_time: Time to check (default: now)

        Returns:
            True if after-hours
        """
        if current_time is None:
            current_time = datetime.now()

        if current_time.weekday() >= 5:
            return False

        market_close = time(16, 0)
        after_hours_end = time(20, 0)

        current_time_only = current_time.time()

        return market_close < current_time_only <= after_hours_end

    @staticmethod
    def time_until_market_open(current_time: datetime = None) -> int:
        """
        Calculate minutes until market open.

        Args:
            current_time: Time to check (default: now)

        Returns:
            Minutes until market open (0 if market is open)
        """
        if current_time is None:
            current_time = datetime.now()

        if MarketHoursChecker.is_market_hours(current_time):
            return 0

        # Calculate next market open
        next_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)

        # If past market open today, move to tomorrow
        if current_time.time() > time(9, 30):
            next_open = next_open.replace(day=next_open.day + 1)

        # Skip weekends
        while next_open.weekday() >= 5:
            next_open = next_open.replace(day=next_open.day + 1)

        minutes_until = int((next_open - current_time).total_seconds() / 60)
        return minutes_until
