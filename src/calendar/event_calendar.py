"""
Event Calendar Builder for market events.
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
try:
    import pandas_market_calendars as mcal
except ImportError:
    mcal = None

logger = logging.getLogger(__name__)


class MarketEvent:
    """Represents a market event."""

    def __init__(self, event_type: str, date: datetime, symbol: str = 'MARKET',
                 impact: str = 'medium', description: str = ''):
        """
        Initialize market event.

        Args:
            event_type: Type of event (FOMC, earnings, expiration, economic)
            date: Event date and time
            symbol: Affected symbol or 'MARKET' for broad events
            impact: Expected volatility impact (high/medium/low)
            description: Event description
        """
        self.event_type = event_type
        self.date = date
        self.symbol = symbol
        self.impact = impact
        self.description = description

    def __repr__(self):
        return f"MarketEvent({self.event_type}, {self.date}, {self.symbol}, {self.impact})"


class EventCalendar:
    """Manages market event calendar."""

    def __init__(self, db_path: str):
        """
        Initialize event calendar.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize events database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_date DATETIME NOT NULL,
                    symbol TEXT DEFAULT 'MARKET',
                    impact TEXT DEFAULT 'medium',
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_event_date
                ON events(event_date, symbol)
            ''')

            conn.commit()
            conn.close()
            logger.info(f"Events database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing events database: {e}")

    def add_event(self, event: MarketEvent):
        """Add event to calendar."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO events (event_type, event_date, symbol, impact, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (event.event_type, event.date, event.symbol, event.impact, event.description))

            conn.commit()
            conn.close()
            logger.debug(f"Added event: {event}")

        except Exception as e:
            logger.error(f"Error adding event: {e}")

    def get_upcoming_events(self, days: int = 30, symbol: Optional[str] = None) -> List[MarketEvent]:
        """
        Get upcoming events.

        Args:
            days: Number of days to look ahead
            symbol: Filter by symbol (None for all)

        Returns:
            List of upcoming events
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            end_date = datetime.now() + timedelta(days=days)

            if symbol:
                cursor.execute('''
                    SELECT event_type, event_date, symbol, impact, description
                    FROM events
                    WHERE event_date BETWEEN datetime('now') AND ?
                    AND (symbol = ? OR symbol = 'MARKET')
                    ORDER BY event_date
                ''', (end_date, symbol))
            else:
                cursor.execute('''
                    SELECT event_type, event_date, symbol, impact, description
                    FROM events
                    WHERE event_date BETWEEN datetime('now') AND ?
                    ORDER BY event_date
                ''', (end_date,))

            rows = cursor.fetchall()
            conn.close()

            events = []
            for row in rows:
                event = MarketEvent(
                    event_type=row[0],
                    date=datetime.fromisoformat(row[1]),
                    symbol=row[2],
                    impact=row[3],
                    description=row[4]
                )
                events.append(event)

            return events

        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            return []

    def load_fomc_meetings(self, year: int):
        """
        Load FOMC meeting dates for a year.
        Typically 8 meetings per year on predictable schedule.

        Args:
            year: Year to load meetings for
        """
        # Typical FOMC meeting schedule (approximate dates)
        # Meetings are usually every 6-7 weeks
        fomc_dates = [
            datetime(year, 1, 31, 14, 0),   # End of January
            datetime(year, 3, 21, 14, 0),   # Mid March
            datetime(year, 5, 2, 14, 0),    # Early May
            datetime(year, 6, 13, 14, 0),   # Mid June
            datetime(year, 7, 25, 14, 0),   # Late July
            datetime(year, 9, 19, 14, 0),   # Mid September
            datetime(year, 11, 7, 14, 0),   # Early November
            datetime(year, 12, 12, 14, 0),  # Mid December
        ]

        for date in fomc_dates:
            if date > datetime.now():  # Only add future dates
                event = MarketEvent(
                    event_type='FOMC',
                    date=date,
                    symbol='MARKET',
                    impact='high',
                    description=f'FOMC Meeting {date.strftime("%B %Y")}'
                )
                self.add_event(event)

        logger.info(f"Loaded FOMC meetings for {year}")

    def load_earnings_dates(self, symbols: List[str]):
        """
        Load earnings dates using yfinance.

        Args:
            symbols: List of stock symbols
        """
        try:
            import yfinance as yf

            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    calendar = ticker.calendar

                    if calendar is not None and 'Earnings Date' in calendar:
                        earnings_dates = calendar['Earnings Date']
                        if isinstance(earnings_dates, pd.Series):
                            for earnings_date in earnings_dates:
                                if pd.notna(earnings_date):
                                    event = MarketEvent(
                                        event_type='EARNINGS',
                                        date=earnings_date.to_pydatetime() if hasattr(earnings_date, 'to_pydatetime') else earnings_date,
                                        symbol=symbol,
                                        impact='high',
                                        description=f'{symbol} Earnings Report'
                                    )
                                    self.add_event(event)

                    logger.debug(f"Loaded earnings for {symbol}")

                except Exception as e:
                    logger.warning(f"Could not load earnings for {symbol}: {e}")

            logger.info(f"Loaded earnings dates for {len(symbols)} symbols")

        except ImportError:
            logger.error("yfinance not installed, cannot load earnings dates")

    def generate_option_expirations(self, year: int):
        """
        Generate option expiration dates.

        Args:
            year: Year to generate expirations for
        """
        # Third Friday of each month
        for month in range(1, 13):
            # Find first day of month
            first_day = datetime(year, month, 1)
            # Find first Friday
            days_until_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_until_friday)
            # Third Friday is 14 days after first Friday
            third_friday = first_friday + timedelta(days=14)

            if third_friday > datetime.now():
                event = MarketEvent(
                    event_type='EXPIRATION',
                    date=third_friday.replace(hour=16, minute=0),  # Market close
                    symbol='MARKET',
                    impact='medium',
                    description=f'Monthly Options Expiration'
                )
                self.add_event(event)

        # Add weekly expirations (every Friday)
        current_date = datetime.now()
        for week in range(52):
            friday = current_date + timedelta(days=(4 - current_date.weekday() + 7 * week) % 7 + 7 * week)
            if friday.year == year:
                event = MarketEvent(
                    event_type='EXPIRATION',
                    date=friday.replace(hour=16, minute=0),
                    symbol='MARKET',
                    impact='low',
                    description='Weekly Options Expiration'
                )
                self.add_event(event)

        logger.info(f"Generated option expiration dates for {year}")

    def load_from_csv(self, csv_path: str):
        """
        Load events from CSV file.

        CSV format: event_type,date,symbol,impact,description

        Args:
            csv_path: Path to CSV file
        """
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                event = MarketEvent(
                    event_type=row['event_type'],
                    date=pd.to_datetime(row['date']),
                    symbol=row.get('symbol', 'MARKET'),
                    impact=row.get('impact', 'medium'),
                    description=row.get('description', '')
                )
                self.add_event(event)

            logger.info(f"Loaded events from {csv_path}")

        except Exception as e:
            logger.error(f"Error loading events from CSV: {e}")

    def get_market_hours(self, date: datetime) -> Optional[tuple]:
        """
        Get market hours for a specific date using pandas_market_calendars.

        Args:
            date: Date to check

        Returns:
            Tuple of (market_open, market_close) or None if market closed
        """
        if mcal is None:
            logger.warning("pandas_market_calendars not installed")
            return None

        try:
            nyse = mcal.get_calendar('NYSE')
            schedule = nyse.schedule(start_date=date, end_date=date)

            if not schedule.empty:
                market_open = schedule.iloc[0]['market_open']
                market_close = schedule.iloc[0]['market_close']
                return (market_open, market_close)

            return None

        except Exception as e:
            logger.error(f"Error getting market hours: {e}")
            return None

    def is_market_open(self, date: Optional[datetime] = None) -> bool:
        """
        Check if market is open at a specific time.

        Args:
            date: Date/time to check (default: now)

        Returns:
            True if market is open
        """
        if date is None:
            date = datetime.now()

        hours = self.get_market_hours(date.date())
        if hours:
            market_open, market_close = hours
            return market_open <= date <= market_close

        return False
