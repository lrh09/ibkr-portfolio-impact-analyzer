"""
Market Data Manager with caching and historical storage.
"""
import logging
import sqlite3
import time
from typing import Dict, Optional, List
from datetime import datetime
from ib_insync import IB, Contract
from .position import Position

logger = logging.getLogger(__name__)


class MarketDataCache:
    """Cache for market data with TTL."""

    def __init__(self, ttl: int = 1):
        """
        Initialize cache.

        Args:
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl
        self.cache: Dict[str, tuple] = {}  # key -> (data, timestamp)

    def get(self, key: str) -> Optional[dict]:
        """Get cached data if not expired."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key: str, data: dict):
        """Store data in cache."""
        self.cache[key] = (data, time.time())

    def clear(self):
        """Clear all cached data."""
        self.cache.clear()


class MarketDataManager:
    """Manages market data subscriptions and storage."""

    def __init__(self, ib: IB, db_path: str, cache_ttl: int = 1,
                 snapshot_interval: int = 300):
        """
        Initialize market data manager.

        Args:
            ib: Connected IB instance
            db_path: Path to SQLite database
            cache_ttl: Cache time-to-live in seconds
            snapshot_interval: Snapshot storage interval in seconds
        """
        self.ib = ib
        self.db_path = db_path
        self.cache = MarketDataCache(ttl=cache_ttl)
        self.snapshot_interval = snapshot_interval
        self.subscriptions: Dict[str, object] = {}
        self.last_snapshot_time = 0

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create market data snapshots table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    symbol TEXT NOT NULL,
                    price REAL,
                    bid REAL,
                    ask REAL,
                    volume INTEGER,
                    implied_volatility REAL,
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    rho REAL
                )
            ''')

            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp
                ON market_snapshots(symbol, timestamp)
            ''')

            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    async def subscribe_positions(self, positions: List[Position]):
        """
        Subscribe to real-time data for all positions.

        Args:
            positions: List of positions to subscribe to
        """
        # Get unique underlyings
        underlyings = set()
        for position in positions:
            if position.is_option and position.underlying:
                underlyings.add(position.underlying)
            elif not position.is_option:
                underlyings.add(position.symbol)

        logger.info(f"Subscribing to market data for {len(underlyings)} underlyings")

        # Subscribe to each underlying
        for symbol in underlyings:
            await self.subscribe_underlying(symbol)

        # Subscribe to options Greeks
        for position in positions:
            if position.is_option and position.contract:
                await self.subscribe_option_greeks(position)

    async def subscribe_underlying(self, symbol: str):
        """
        Subscribe to underlying stock data.

        Args:
            symbol: Stock symbol
        """
        try:
            if symbol not in self.subscriptions:
                from ib_insync import Stock
                contract = Stock(symbol, 'SMART', 'USD')
                ticker = self.ib.reqMktData(contract, '', snapshot=False)
                self.subscriptions[symbol] = ticker
                logger.debug(f"Subscribed to {symbol}")

        except Exception as e:
            logger.error(f"Error subscribing to {symbol}: {e}")

    async def subscribe_option_greeks(self, position: Position):
        """
        Subscribe to option Greeks.

        Args:
            position: Option position
        """
        try:
            if position.contract:
                # Use genericTickList='13,106' for IV and Greeks
                ticker = self.ib.reqMktData(position.contract, '13,106', snapshot=False)
                key = self._get_position_key(position)
                self.subscriptions[key] = ticker
                logger.debug(f"Subscribed to Greeks for {key}")

        except Exception as e:
            logger.error(f"Error subscribing to Greeks for {position.symbol}: {e}")

    def get_market_data(self, symbol: str) -> Optional[dict]:
        """
        Get market data for a symbol (cached or live).

        Args:
            symbol: Symbol to get data for

        Returns:
            Dictionary with market data or None
        """
        # Check cache first
        cached = self.cache.get(symbol)
        if cached:
            return cached

        # Get from subscription
        if symbol in self.subscriptions:
            ticker = self.subscriptions[symbol]
            data = {
                'symbol': symbol,
                'price': ticker.marketPrice() or ticker.last,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'volume': ticker.volume,
                'timestamp': datetime.now()
            }
            self.cache.set(symbol, data)
            return data

        return None

    def get_option_data(self, position: Position) -> Optional[dict]:
        """
        Get option data including Greeks.

        Args:
            position: Option position

        Returns:
            Dictionary with option data or None
        """
        key = self._get_position_key(position)

        # Check cache
        cached = self.cache.get(key)
        if cached:
            return cached

        # Get from subscription
        if key in self.subscriptions:
            ticker = self.subscriptions[key]
            data = {
                'symbol': position.symbol,
                'price': ticker.marketPrice() or ticker.last,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'volume': ticker.volume,
                'implied_volatility': ticker.impliedVolatility,
                'delta': ticker.modelGreeks.delta if ticker.modelGreeks else None,
                'gamma': ticker.modelGreeks.gamma if ticker.modelGreeks else None,
                'theta': ticker.modelGreeks.theta if ticker.modelGreeks else None,
                'vega': ticker.modelGreeks.vega if ticker.modelGreeks else None,
                'rho': ticker.modelGreeks.rho if ticker.modelGreeks else None,
                'timestamp': datetime.now()
            }
            self.cache.set(key, data)
            return data

        return None

    async def update_positions_data(self, positions: List[Position]):
        """
        Update market data for all positions.

        Args:
            positions: List of positions to update
        """
        for position in positions:
            try:
                if position.is_option:
                    data = self.get_option_data(position)
                    if data:
                        position.update_price(data['price'])
                        if data.get('implied_volatility'):
                            position.update_greeks(
                                delta=data.get('delta'),
                                gamma=data.get('gamma'),
                                theta=data.get('theta'),
                                vega=data.get('vega'),
                                rho=data.get('rho'),
                                iv=data.get('implied_volatility')
                            )
                else:
                    data = self.get_market_data(position.symbol)
                    if data:
                        position.update_price(data['price'])

            except Exception as e:
                logger.error(f"Error updating data for {position.symbol}: {e}")

    def save_snapshot(self, positions: List[Position]):
        """
        Save current market data snapshot to database.

        Args:
            positions: List of positions to snapshot
        """
        current_time = time.time()
        if current_time - self.last_snapshot_time < self.snapshot_interval:
            return  # Too soon for next snapshot

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for position in positions:
                cursor.execute('''
                    INSERT INTO market_snapshots
                    (symbol, price, implied_volatility, delta, gamma, theta, vega, rho)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    position.symbol,
                    position.current_price,
                    position.implied_volatility,
                    position.delta,
                    position.gamma,
                    position.theta,
                    position.vega,
                    position.rho
                ))

            conn.commit()
            conn.close()
            self.last_snapshot_time = current_time
            logger.debug(f"Saved snapshot for {len(positions)} positions")

        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")

    def get_historical_snapshots(self, symbol: str, hours: int = 24) -> List[dict]:
        """
        Retrieve historical snapshots for a symbol.

        Args:
            symbol: Symbol to query
            hours: Hours of history to retrieve

        Returns:
            List of snapshot dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT timestamp, price, implied_volatility, delta, gamma, theta, vega, rho
                FROM market_snapshots
                WHERE symbol = ? AND timestamp >= datetime('now', ? || ' hours')
                ORDER BY timestamp DESC
            ''', (symbol, -hours))

            rows = cursor.fetchall()
            conn.close()

            snapshots = []
            for row in rows:
                snapshots.append({
                    'timestamp': row[0],
                    'price': row[1],
                    'implied_volatility': row[2],
                    'delta': row[3],
                    'gamma': row[4],
                    'theta': row[5],
                    'vega': row[6],
                    'rho': row[7]
                })

            return snapshots

        except Exception as e:
            logger.error(f"Error retrieving historical data: {e}")
            return []

    def _get_position_key(self, position: Position) -> str:
        """Generate unique key for position."""
        if position.is_option:
            exp_str = position.expiration.strftime('%Y%m%d') if position.expiration else 'NOEXP'
            return f"{position.underlying}_{position.option_type}_{position.strike}_{exp_str}"
        else:
            return position.symbol

    def unsubscribe_all(self):
        """Unsubscribe from all market data."""
        for ticker in self.subscriptions.values():
            self.ib.cancelMktData(ticker.contract)
        self.subscriptions.clear()
        logger.info("Unsubscribed from all market data")
