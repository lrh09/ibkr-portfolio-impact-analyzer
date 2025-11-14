"""
IBKR Connection Manager with reconnection logic and rate limiting.
"""
import asyncio
import logging
import time
from typing import Optional
from ib_insync import IB, util

logger = logging.getLogger(__name__)


class IBKRConnectionManager:
    """Manages connection to TWS/Gateway with reconnection logic."""

    def __init__(self, host: str, port: int, client_id: int,
                 reconnect_attempts: int = 5, reconnect_delay: float = 2.0):
        """
        Initialize IBKR connection manager.

        Args:
            host: TWS/Gateway host address
            port: TWS/Gateway port (7497 for paper, 7496 for live)
            client_id: Client ID for connection
            reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Base delay for exponential backoff (seconds)
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self.ib = IB()
        self._connected = False
        self._last_message_time = 0
        self._message_count = 0
        self._rate_limit = 50  # messages per second

    async def connect(self) -> bool:
        """
        Connect to IBKR with exponential backoff retry logic.

        Returns:
            True if connection successful, False otherwise
        """
        for attempt in range(self.reconnect_attempts):
            try:
                if not self.ib.isConnected():
                    logger.info(f"Connecting to IBKR at {self.host}:{self.port} (attempt {attempt + 1}/{self.reconnect_attempts})")
                    await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=20)
                    self._connected = True
                    logger.info("Successfully connected to IBKR")

                    # Set up disconnection handler
                    self.ib.disconnectedEvent += self._on_disconnect
                    return True

            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.reconnect_attempts - 1:
                    delay = self.reconnect_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max reconnection attempts reached")
                    return False

        return False

    def _on_disconnect(self):
        """Handle disconnection event."""
        logger.warning("Disconnected from IBKR")
        self._connected = False

    async def ensure_connected(self) -> bool:
        """
        Ensure connection is active, reconnect if necessary.

        Returns:
            True if connected, False otherwise
        """
        if not self.ib.isConnected():
            logger.warning("Connection lost, attempting to reconnect...")
            return await self.connect()
        return True

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib.isConnected():
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check if connected to IBKR."""
        return self._connected and self.ib.isConnected()

    async def rate_limit(self):
        """
        Enforce rate limiting (max 50 messages/second).
        """
        current_time = time.time()

        # Reset counter every second
        if current_time - self._last_message_time >= 1.0:
            self._message_count = 0
            self._last_message_time = current_time

        # Check if rate limit exceeded
        if self._message_count >= self._rate_limit:
            sleep_time = 1.0 - (current_time - self._last_message_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self._message_count = 0
            self._last_message_time = time.time()

        self._message_count += 1

    def get_ib(self) -> IB:
        """Get the IB instance."""
        return self.ib

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.disconnect()
