"""
Event Detection for upcoming market events.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from .event_calendar import EventCalendar, MarketEvent
from ..data_collection.position import Position

logger = logging.getLogger(__name__)


class EventDetector:
    """Detects relevant events for portfolio positions."""

    def __init__(self, calendar: EventCalendar):
        """
        Initialize event detector.

        Args:
            calendar: Event calendar instance
        """
        self.calendar = calendar

    def check_events(self, positions: List[Position], lookforward_days: int = 30) -> Dict[str, List[MarketEvent]]:
        """
        Check for upcoming events affecting positions.

        Args:
            positions: List of portfolio positions
            lookforward_days: Days to look forward

        Returns:
            Dictionary mapping time periods to relevant events
        """
        results = {
            'T+0': [],  # Today
            'T+1': [],  # Tomorrow
            'T+5': [],  # Within 5 days
            'T+30': []  # Within 30 days
        }

        now = datetime.now()

        # Get unique symbols from positions
        symbols = set()
        for position in positions:
            if position.is_option and position.underlying:
                symbols.add(position.underlying)
            elif not position.is_option:
                symbols.add(position.symbol)

        # Check events for each symbol and MARKET events
        for symbol in symbols:
            events = self.calendar.get_upcoming_events(days=lookforward_days, symbol=symbol)

            for event in events:
                days_until = (event.date - now).days

                if days_until == 0:
                    results['T+0'].append(event)
                if days_until <= 1:
                    results['T+1'].append(event)
                if days_until <= 5:
                    results['T+5'].append(event)
                if days_until <= 30:
                    results['T+30'].append(event)

        # Also get broad market events
        market_events = self.calendar.get_upcoming_events(days=lookforward_days, symbol='MARKET')
        for event in market_events:
            days_until = (event.date - now).days

            if days_until == 0:
                results['T+0'].append(event)
            if days_until <= 1:
                results['T+1'].append(event)
            if days_until <= 5:
                results['T+5'].append(event)
            if days_until <= 30:
                results['T+30'].append(event)

        logger.info(f"Detected {len(results['T+0'])} events today, {len(results['T+1'])} within 1 day")
        return results

    def flag_earnings_before_expiration(self, positions: List[Position]) -> List[Dict]:
        """
        Flag options with earnings dates before expiration.

        Args:
            positions: List of positions

        Returns:
            List of flagged positions with details
        """
        flagged = []

        for position in positions:
            if not position.is_option or not position.expiration or not position.underlying:
                continue

            # Get earnings events for this underlying
            events = self.calendar.get_upcoming_events(days=365, symbol=position.underlying)
            earnings_events = [e for e in events if e.event_type == 'EARNINGS']

            for earnings_event in earnings_events:
                # Check if earnings is before expiration
                if earnings_event.date < position.expiration:
                    days_to_earnings = (earnings_event.date - datetime.now()).days
                    days_to_expiration = position.days_to_expiration()

                    flagged.append({
                        'position': position,
                        'earnings_date': earnings_event.date,
                        'expiration_date': position.expiration,
                        'days_to_earnings': days_to_earnings,
                        'days_to_expiration': days_to_expiration,
                        'warning': 'Earnings before expiration'
                    })

                    logger.warning(
                        f"{position.symbol}: Earnings on {earnings_event.date.date()} "
                        f"before expiration {position.expiration.date()}"
                    )

        return flagged

    def identify_weekly_options_near_events(self, positions: List[Position]) -> List[Dict]:
        """
        Identify weekly options near major events.

        Args:
            positions: List of positions

        Returns:
            List of positions with nearby events
        """
        results = []

        for position in positions:
            if not position.is_option or not position.expiration:
                continue

            # Check if it's a weekly (expires on non-third Friday)
            exp_day = position.expiration.day
            third_friday = 15 + (4 - datetime(position.expiration.year, position.expiration.month, 1).weekday()) % 7 + 14

            is_weekly = (exp_day != third_friday)

            if not is_weekly:
                continue

            # Get events within 3 days of expiration
            events_before = []
            events_after = []

            if position.underlying:
                nearby_events = self.calendar.get_upcoming_events(days=7, symbol=position.underlying)
            else:
                nearby_events = []

            for event in nearby_events:
                days_diff = (event.date - position.expiration).days

                if -3 <= days_diff <= 0:
                    events_before.append(event)
                elif 0 < days_diff <= 3:
                    events_after.append(event)

            if events_before or events_after:
                results.append({
                    'position': position,
                    'is_weekly': True,
                    'expiration': position.expiration,
                    'events_before': events_before,
                    'events_after': events_after
                })

                logger.info(
                    f"Weekly option {position.symbol} expires {position.expiration.date()} "
                    f"with {len(events_before)} events before and {len(events_after)} after"
                )

        return results

    def get_event_summary(self, positions: List[Position]) -> Dict:
        """
        Get comprehensive event summary for portfolio.

        Args:
            positions: List of positions

        Returns:
            Dictionary with event summary
        """
        upcoming = self.check_events(positions)
        earnings_flags = self.flag_earnings_before_expiration(positions)
        weekly_flags = self.identify_weekly_options_near_events(positions)

        summary = {
            'upcoming_events': upcoming,
            'earnings_before_expiration': earnings_flags,
            'weekly_options_near_events': weekly_flags,
            'total_positions': len(positions),
            'positions_with_warnings': len(set(
                [f['position'] for f in earnings_flags] +
                [f['position'] for f in weekly_flags]
            ))
        }

        return summary

    def get_relevant_scenarios(self, events: Dict[str, List[MarketEvent]]) -> List[str]:
        """
        Determine which scenarios to run based on upcoming events.

        Args:
            events: Dictionary of upcoming events by time period

        Returns:
            List of scenario names to execute
        """
        scenarios = ['Normal Day']  # Always run baseline

        # Check for imminent events
        if events['T+0'] or events['T+1']:
            for event in events['T+0'] + events['T+1']:
                if event.event_type == 'FOMC':
                    scenarios.extend(['Fed Hawkish', 'Fed Dovish', 'Fed Neutral'])
                elif event.event_type == 'EARNINGS':
                    scenarios.extend(['Earnings Beat', 'Earnings Miss', 'Earnings Inline'])
                elif event.event_type == 'EXPIRATION':
                    scenarios.extend(['1 Day Pass', 'Weekend'])

        # Add general stress scenarios
        scenarios.extend(['Market Panic', 'Relief Rally'])

        # Remove duplicates while preserving order
        seen = set()
        unique_scenarios = []
        for scenario in scenarios:
            if scenario not in seen:
                seen.add(scenario)
                unique_scenarios.append(scenario)

        return unique_scenarios
