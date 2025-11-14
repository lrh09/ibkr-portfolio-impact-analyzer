"""
Vectorized Black-Scholes option pricing calculator.
"""
import numpy as np
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)


class BlackScholesCalculator:
    """Black-Scholes option pricing with vectorization."""

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize Black-Scholes calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_option_price(self, spot: float, strike: float, time_to_expiry: float,
                               volatility: float, option_type: str = 'C',
                               dividend_yield: float = 0.0) -> float:
        """
        Calculate option price using Black-Scholes formula.

        Args:
            spot: Current underlying price
            strike: Strike price
            time_to_expiry: Time to expiration in years
            volatility: Implied volatility (as decimal, e.g., 0.30 for 30%)
            option_type: 'C' for call, 'P' for put
            dividend_yield: Annual dividend yield

        Returns:
            Option price
        """
        if time_to_expiry <= 0:
            # Option expired - return intrinsic value
            if option_type == 'C':
                return max(0, spot - strike)
            else:
                return max(0, strike - spot)

        if volatility <= 0:
            logger.warning(f"Invalid volatility {volatility}, using 0.30")
            volatility = 0.30

        # Calculate d1 and d2
        d1 = (np.log(spot / strike) + (self.risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)

        # Calculate option price
        if option_type == 'C':
            price = (spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1) -
                    strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2))
        else:  # Put
            price = (strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) -
                    spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1))

        return max(0, price)  # Ensure non-negative

    def calculate_greeks(self, spot: float, strike: float, time_to_expiry: float,
                        volatility: float, option_type: str = 'C',
                        dividend_yield: float = 0.0) -> dict:
        """
        Calculate option Greeks.

        Args:
            spot: Current underlying price
            strike: Strike price
            time_to_expiry: Time to expiration in years
            volatility: Implied volatility
            option_type: 'C' for call, 'P' for put
            dividend_yield: Annual dividend yield

        Returns:
            Dictionary with delta, gamma, theta, vega, rho
        """
        if time_to_expiry <= 0:
            return {
                'delta': 1.0 if (option_type == 'C' and spot > strike) else 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }

        if volatility <= 0:
            volatility = 0.30

        # Calculate d1 and d2
        sqrt_t = np.sqrt(time_to_expiry)
        d1 = (np.log(spot / strike) + (self.risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiry) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t

        # Delta
        if option_type == 'C':
            delta = np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)
        else:
            delta = -np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)

        # Gamma (same for calls and puts)
        gamma = (np.exp(-dividend_yield * time_to_expiry) * norm.pdf(d1)) / (spot * volatility * sqrt_t)

        # Vega (same for calls and puts) - per 1% change in IV
        vega = spot * np.exp(-dividend_yield * time_to_expiry) * norm.pdf(d1) * sqrt_t / 100

        # Theta (per day)
        if option_type == 'C':
            theta = ((-spot * norm.pdf(d1) * volatility * np.exp(-dividend_yield * time_to_expiry)) / (2 * sqrt_t) -
                    self.risk_free_rate * strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2) +
                    dividend_yield * spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(d1)) / 365
        else:
            theta = ((-spot * norm.pdf(d1) * volatility * np.exp(-dividend_yield * time_to_expiry)) / (2 * sqrt_t) +
                    self.risk_free_rate * strike * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) -
                    dividend_yield * spot * np.exp(-dividend_yield * time_to_expiry) * norm.cdf(-d1)) / 365

        # Rho (per 1% change in interest rate)
        if option_type == 'C':
            rho = strike * time_to_expiry * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(d2) / 100
        else:
            rho = -strike * time_to_expiry * np.exp(-self.risk_free_rate * time_to_expiry) * norm.cdf(-d2) / 100

        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }

    def calculate_batch(self, spots: np.ndarray, strikes: np.ndarray,
                       times_to_expiry: np.ndarray, volatilities: np.ndarray,
                       option_types: np.ndarray, dividend_yields: np.ndarray = None) -> np.ndarray:
        """
        Vectorized batch calculation of option prices.

        Args:
            spots: Array of spot prices
            strikes: Array of strike prices
            times_to_expiry: Array of times to expiry (in years)
            volatilities: Array of implied volatilities
            option_types: Array of option types ('C' or 'P')
            dividend_yields: Array of dividend yields (optional)

        Returns:
            Array of option prices
        """
        if dividend_yields is None:
            dividend_yields = np.zeros_like(spots)

        # Handle expired options
        expired_mask = times_to_expiry <= 0
        times_to_expiry = np.maximum(times_to_expiry, 1e-10)  # Avoid division by zero

        # Handle invalid volatilities
        volatilities = np.maximum(volatilities, 0.01)

        # Calculate d1 and d2 for all options
        sqrt_t = np.sqrt(times_to_expiry)
        d1 = (np.log(spots / strikes) + (self.risk_free_rate - dividend_yields + 0.5 * volatilities**2) * times_to_expiry) / (volatilities * sqrt_t)
        d2 = d1 - volatilities * sqrt_t

        # Calculate prices for calls and puts
        call_prices = (spots * np.exp(-dividend_yields * times_to_expiry) * norm.cdf(d1) -
                      strikes * np.exp(-self.risk_free_rate * times_to_expiry) * norm.cdf(d2))

        put_prices = (strikes * np.exp(-self.risk_free_rate * times_to_expiry) * norm.cdf(-d2) -
                     spots * np.exp(-dividend_yields * times_to_expiry) * norm.cdf(-d1))

        # Select correct prices based on option type
        prices = np.where(option_types == 'C', call_prices, put_prices)

        # Handle expired options - use intrinsic value
        call_intrinsic = np.maximum(0, spots - strikes)
        put_intrinsic = np.maximum(0, strikes - spots)
        intrinsic_values = np.where(option_types == 'C', call_intrinsic, put_intrinsic)

        prices = np.where(expired_mask, intrinsic_values, prices)

        return np.maximum(0, prices)  # Ensure non-negative

    def calculate_implied_volatility(self, option_price: float, spot: float,
                                     strike: float, time_to_expiry: float,
                                     option_type: str = 'C',
                                     dividend_yield: float = 0.0,
                                     max_iterations: int = 100) -> float:
        """
        Calculate implied volatility using Newton-Raphson method.

        Args:
            option_price: Market price of option
            spot: Current underlying price
            strike: Strike price
            time_to_expiry: Time to expiration in years
            option_type: 'C' for call, 'P' for put
            dividend_yield: Annual dividend yield
            max_iterations: Maximum iterations for convergence

        Returns:
            Implied volatility
        """
        # Initial guess
        iv = 0.30

        for i in range(max_iterations):
            # Calculate price and vega with current IV
            price = self.calculate_option_price(spot, strike, time_to_expiry,
                                                iv, option_type, dividend_yield)
            greeks = self.calculate_greeks(spot, strike, time_to_expiry,
                                          iv, option_type, dividend_yield)

            vega = greeks['vega'] * 100  # Convert to per-unit vega

            # Check for convergence
            price_diff = option_price - price

            if abs(price_diff) < 0.001:
                return iv

            if vega == 0:
                return iv

            # Newton-Raphson update
            iv = iv + price_diff / vega

            # Keep IV in reasonable bounds
            iv = max(0.01, min(3.0, iv))

        logger.warning(f"IV calculation did not converge, returning {iv}")
        return iv
