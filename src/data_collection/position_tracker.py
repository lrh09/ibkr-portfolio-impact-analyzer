"""
Position Tracker for loading and managing portfolio positions.
"""
import logging
from typing import Dict, List
from datetime import datetime
from ib_insync import IB, Stock, Option, Contract
from .position import Position

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks and manages portfolio positions."""

    def __init__(self, ib: IB):
        """
        Initialize position tracker.

        Args:
            ib: Connected IB instance
        """
        self.ib = ib
        self.positions: Dict[str, Position] = {}

    async def load_positions(self) -> Dict[str, Position]:
        """
        Load all positions from IBKR account.

        Returns:
            Dictionary of positions keyed by position identifier
        """
        try:
            # Request portfolio positions
            portfolio_items = self.ib.portfolio()

            logger.info(f"Loading {len(portfolio_items)} positions from IBKR")

            for item in portfolio_items:
                try:
                    position = await self._create_position_from_item(item)
                    if position:
                        position_key = self._get_position_key(position)
                        self.positions[position_key] = position
                        logger.debug(f"Loaded position: {position_key}")

                except Exception as e:
                    logger.error(f"Error creating position from {item.contract.symbol}: {e}")

            logger.info(f"Successfully loaded {len(self.positions)} positions")
            return self.positions

        except Exception as e:
            logger.error(f"Error loading positions: {e}")
            return {}

    async def _create_position_from_item(self, item) -> Optional[Position]:
        """
        Create Position object from portfolio item.

        Args:
            item: Portfolio item from IB

        Returns:
            Position object or None if creation failed
        """
        contract = item.contract
        quantity = item.position
        avg_cost = item.averageCost
        market_price = item.marketPrice if item.marketPrice else avg_cost

        # Determine if option or stock
        is_option = isinstance(contract, Option)

        if is_option:
            # Option position
            position = Position(
                symbol=contract.localSymbol,
                quantity=quantity,
                entry_price=avg_cost,
                current_price=market_price,
                is_option=True,
                underlying=contract.symbol,
                strike=contract.strike,
                expiration=datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d'),
                option_type=contract.right,  # 'C' or 'P'
                contract_multiplier=int(contract.multiplier) if contract.multiplier else 100,
                contract=contract
            )

            # Request Greeks if available
            await self._request_greeks(position)

        else:
            # Stock position
            position = Position(
                symbol=contract.symbol,
                quantity=quantity,
                entry_price=avg_cost,
                current_price=market_price,
                is_option=False,
                contract=contract
            )

        return position

    async def _request_greeks(self, position: Position):
        """
        Request option Greeks from IBKR.

        Args:
            position: Position object to update with Greeks
        """
        try:
            if position.contract:
                # Request market data with Greeks (genericTickList='13,106')
                # 13 = IV, 106 = Option Greeks
                ticker = self.ib.reqMktData(position.contract, '13,106', snapshot=False)
                await self.ib.sleepAsync(2)  # Wait for data

                if ticker.modelGreeks:
                    greeks = ticker.modelGreeks
                    position.update_greeks(
                        delta=greeks.delta,
                        gamma=greeks.gamma,
                        theta=greeks.theta,
                        vega=greeks.vega,
                        rho=greeks.rho,
                        iv=ticker.impliedVolatility
                    )
                    logger.debug(f"Updated Greeks for {position.symbol}")

        except Exception as e:
            logger.error(f"Error requesting Greeks for {position.symbol}: {e}")

    def _get_position_key(self, position: Position) -> str:
        """
        Generate unique key for position.

        Args:
            position: Position object

        Returns:
            Unique string identifier
        """
        if position.is_option:
            exp_str = position.expiration.strftime('%Y%m%d') if position.expiration else 'NOEXP'
            return f"{position.underlying}_{position.option_type}_{position.strike}_{exp_str}"
        else:
            return position.symbol

    def get_position(self, key: str) -> Optional[Position]:
        """Get position by key."""
        return self.positions.get(key)

    def get_all_positions(self) -> List[Position]:
        """Get all positions as a list."""
        return list(self.positions.values())

    def get_stock_positions(self) -> List[Position]:
        """Get only stock positions."""
        return [p for p in self.positions.values() if not p.is_option]

    def get_option_positions(self) -> List[Position]:
        """Get only option positions."""
        return [p for p in self.positions.values() if p.is_option]

    def get_positions_by_underlying(self, underlying: str) -> List[Position]:
        """
        Get all positions for a specific underlying.

        Args:
            underlying: Underlying symbol

        Returns:
            List of positions for that underlying
        """
        positions = []
        for position in self.positions.values():
            if position.is_option and position.underlying == underlying:
                positions.append(position)
            elif not position.is_option and position.symbol == underlying:
                positions.append(position)
        return positions

    def get_total_portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        return sum(p.position_value for p in self.positions.values())

    def subscribe_realtime_updates(self):
        """Subscribe to real-time position updates."""
        # Set up event handlers for real-time updates
        self.ib.updatePortfolioEvent += self._on_portfolio_update

    def _on_portfolio_update(self, item):
        """Handle real-time portfolio updates."""
        try:
            # Update existing position or create new one
            contract = item.contract
            market_price = item.marketPrice

            # Find matching position
            for position in self.positions.values():
                if position.contract == contract:
                    position.update_price(market_price)
                    logger.debug(f"Updated price for {position.symbol}: {market_price}")
                    break

        except Exception as e:
            logger.error(f"Error in portfolio update handler: {e}")
