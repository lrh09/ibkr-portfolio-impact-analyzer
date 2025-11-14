"""
Position class for tracking stocks and options.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    """
    Represents a position (stock or option) in the portfolio.
    """
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    last_update: datetime = field(default_factory=datetime.now)

    # Option-specific fields
    is_option: bool = False
    underlying: Optional[str] = None
    strike: Optional[float] = None
    expiration: Optional[datetime] = None
    option_type: Optional[str] = None  # 'C' for call, 'P' for put
    contract_multiplier: int = 100

    # Greeks (for options)
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    implied_volatility: Optional[float] = None

    # Position metadata
    contract: Optional[object] = None  # IB contract object
    position_value: float = 0.0

    def __post_init__(self):
        """Calculate initial position value."""
        self.update_position_value()

    def update_position_value(self):
        """Update the position value based on current price and quantity."""
        if self.is_option:
            self.position_value = self.current_price * self.quantity * self.contract_multiplier
        else:
            self.position_value = self.current_price * self.quantity

    def update_price(self, price: float):
        """Update current price and recalculate position value."""
        self.current_price = price
        self.last_update = datetime.now()
        self.update_position_value()

    def update_greeks(self, delta: float = None, gamma: float = None,
                      theta: float = None, vega: float = None,
                      rho: float = None, iv: float = None):
        """Update option Greeks."""
        if delta is not None:
            self.delta = delta
        if gamma is not None:
            self.gamma = gamma
        if theta is not None:
            self.theta = theta
        if vega is not None:
            self.vega = vega
        if rho is not None:
            self.rho = rho
        if iv is not None:
            self.implied_volatility = iv
        self.last_update = datetime.now()

    def days_to_expiration(self) -> Optional[int]:
        """Calculate days to expiration for options."""
        if self.is_option and self.expiration:
            delta = self.expiration - datetime.now()
            return delta.days
        return None

    def get_pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.is_option:
            return (self.current_price - self.entry_price) * self.quantity * self.contract_multiplier
        else:
            return (self.current_price - self.entry_price) * self.quantity

    def get_pnl_percent(self) -> float:
        """Calculate unrealized P&L percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100

    def moneyness(self, spot_price: Optional[float] = None) -> Optional[float]:
        """
        Calculate moneyness for options.

        Args:
            spot_price: Current underlying price (uses current_price if option)

        Returns:
            Moneyness ratio (spot/strike for calls, strike/spot for puts)
        """
        if not self.is_option or not self.strike:
            return None

        if spot_price is None:
            spot_price = self.current_price

        if self.option_type == 'C':
            return spot_price / self.strike
        else:  # Put
            return self.strike / spot_price

    def is_itm(self, spot_price: Optional[float] = None) -> Optional[bool]:
        """Check if option is in-the-money."""
        if not self.is_option or not self.strike:
            return None

        if spot_price is None:
            spot_price = self.current_price

        if self.option_type == 'C':
            return spot_price > self.strike
        else:  # Put
            return spot_price < self.strike

    def __repr__(self) -> str:
        """String representation of position."""
        if self.is_option:
            return (f"Position({self.symbol} {self.option_type} {self.strike} "
                    f"exp:{self.expiration.date() if self.expiration else 'N/A'}, "
                    f"qty:{self.quantity}, price:{self.current_price:.2f}, "
                    f"IV:{self.implied_volatility:.2%} if self.implied_volatility else 'N/A')")
        else:
            return (f"Position({self.symbol}, qty:{self.quantity}, "
                    f"price:{self.current_price:.2f}, "
                    f"value:{self.position_value:.2f})")
