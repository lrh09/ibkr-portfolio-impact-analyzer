# Portfolio Risk Analyzer for Interactive Brokers

A comprehensive portfolio risk analysis tool for Interactive Brokers (IBKR) that performs scenario analysis, monitors Greeks, tracks market events, and generates detailed risk reports.

## Features

### 1. **Data Collection Module**
- **IBKR Connection Manager**: Automatic connection to TWS/Gateway with exponential backoff retry logic
- **Position Tracker**: Real-time tracking of stocks and options with full Greeks support
- **Market Data Manager**: Live market data with 1-second TTL caching and SQLite historical storage

### 2. **Calendar Integration**
- **Event Calendar**: Tracks FOMC meetings, earnings dates, option expirations, and economic events
- **Event Detection**: Identifies upcoming events affecting your positions (T+0, T+1, T+5, T+30)
- **Auto-detection**: Automatically loads earnings dates using yfinance
- **Earnings Warnings**: Flags options with earnings before expiration

### 3. **Scenario Engine**
- **Beta-Weighted IV Model**: Advanced implied volatility modeling based on moneyness and time to expiration
- **16 Pre-built Scenarios**:
  - Normal Day
  - Earnings (Beat, Miss, Inline)
  - Market Stress (Panic, Flash Crash, Black Swan)
  - Fed Events (Hawkish, Dovish, Neutral)
  - Rallies (Short Squeeze, FOMO Rally, Relief Rally)
  - Time Decay (1 Day, Weekend, 1 Week)
- **Custom Scenarios**: Create your own scenarios with custom spot/IV changes

### 4. **Valuation Engine**
- **Vectorized Black-Scholes**: Fast option pricing using numpy arrays
- **Greeks Calculation**: Delta, Gamma, Theta, Vega, Rho
- **Portfolio Aggregation**: Calculate total portfolio value and risk across all positions

### 5. **Risk Metrics**
- **Position-Level**: P&L, Greeks, IV rank, concentration, moneyness
- **Portfolio-Level**: Total value, aggregate Greeks, VaR (95%, 99%), max drawdown
- **Correlation Analysis**: Position correlation matrix based on scenario results

### 6. **Risk Alerts**
- Scenario losses exceeding threshold (default 10%)
- Position concentration exceeding 25%
- Earnings before expiration warnings
- IV extremes (>80% or <20%)
- Excessive Vega/Gamma exposure
- Short gamma warnings
- Stale data alerts

### 7. **Reporting & Visualization**
- **Scenario Summary Report**: P&L across all scenarios with best/worst positions
- **Position Detail Report**: Per-position P&L across scenarios
- **Greeks Summary**: Portfolio Greeks exposure
- **Risk Alerts**: Real-time risk warnings
- **Export Formats**: CSV, JSON, Excel (multi-sheet)

### 8. **Automation**
- **Real-time Monitoring**: Continuous portfolio monitoring during market hours
- **Scheduled Tasks**: Start-of-day, every-minute updates, 5-minute scenarios, end-of-day reports
- **Market Hours Detection**: Automatic handling of market hours, pre-market, and after-hours

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd ibkr-portfolio-impact-analyzer

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p data logs data/reports
```

## Configuration

Edit `config/config.yaml` to customize settings:

```yaml
ibkr:
  host: "127.0.0.1"
  port: 7497  # 7497 for paper trading, 7496 for live

risk_limits:
  max_portfolio_loss: 0.15  # 15%
  position_concentration: 0.25  # 25%
  vega_limit: 10000
  gamma_limit: 5000

scenarios:
  use_calendar: true
  auto_detect_earnings: true
```

## Usage

### Quick Start

```bash
# Run single analysis
python src/main.py
```

### Running Tests

```bash
# Run unit tests
python -m pytest tests/

# Run specific test
python tests/test_black_scholes.py
```

### Example: Programmatic Usage

```python
import asyncio
from src.main import PortfolioRiskAnalyzer

async def analyze():
    analyzer = PortfolioRiskAnalyzer()
    await analyzer.run_once()

asyncio.run(analyze())
```

## Project Structure

```
ibkr-portfolio-impact-analyzer/
├── config/
│   └── config.yaml              # Configuration file
├── src/
│   ├── data_collection/         # IBKR connection, positions, market data
│   ├── calendar/                # Event calendar and detection
│   ├── scenario/                # IV model and scenario templates
│   ├── valuation/               # Black-Scholes and portfolio aggregation
│   ├── risk/                    # Risk metrics and alerts
│   ├── output/                  # Report generation and exports
│   ├── automation/              # Scheduler and monitoring
│   ├── utils/                   # Utilities and config loader
│   └── main.py                  # Main entry point
├── tests/                       # Unit tests
├── data/                        # Database and reports (created at runtime)
├── logs/                        # Log files (created at runtime)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Key Components

### Position Class
Represents a stock or option position with:
- Current price, entry price, quantity
- For options: strike, expiration, Greeks, IV
- Automatic P&L calculation

### Black-Scholes Calculator
- Vectorized pricing for batch calculations
- Greeks calculation (Delta, Gamma, Theta, Vega, Rho)
- Implied volatility solver using Newton-Raphson

### IV Model
Beta-weighted IV shifts based on:
- **Moneyness Beta**: OTM puts (1.3), ATM (1.0), OTM calls (0.8)
- **Time Beta**: 0-7 DTE (1.5), 8-30 DTE (1.0), 31-90 DTE (0.7), 90+ DTE (0.5)
- **Scenario Multipliers**: Custom IV changes per scenario

### Scenario Templates
Pre-built scenarios with realistic parameters:
- **Earnings Beat**: +5% spot, -35% IV (0-7 DTE)
- **Market Panic**: -5% spot, +60% IV on OTM puts
- **Black Swan**: -20% spot, +150% IV across all options

## Performance Targets

- Load 100 positions in <5 seconds
- Run 10 scenarios in <2 seconds
- Real-time updates with <1 second lag
- Handle 500+ positions without degradation

## Risk Disclaimers

⚠️ **Important Warnings**:

1. This tool is for **analysis purposes only** and does not execute trades
2. Past performance does not guarantee future results
3. Scenario analysis is based on theoretical models and may not reflect actual market behavior
4. Always verify calculations independently before making trading decisions
5. Options trading involves significant risk of loss
6. Consult with a financial advisor before making investment decisions

## Requirements

- Python 3.8+
- Interactive Brokers TWS or IB Gateway
- Active IBKR account (paper or live)
- See `requirements.txt` for Python package dependencies

## Troubleshooting

### Connection Issues
- Ensure TWS/Gateway is running
- Check that the correct port is configured (7497 for paper, 7496 for live)
- Verify API connections are enabled in TWS (File → Global Configuration → API → Settings)
- Check that the client ID doesn't conflict with other connections

### Missing Greeks
- Greeks require market data subscriptions in IBKR
- Ensure you have real-time or delayed data for the underlying
- Greeks are requested with genericTickList='13,106'

### Performance Issues
- Reduce the number of scenarios
- Increase cache TTL in config
- Reduce update frequency
- Use snapshot mode instead of real-time for large portfolios

## Future Enhancements

- Web dashboard with real-time charts
- Machine learning for IV prediction
- Backtesting against historical events
- Portfolio optimization suggestions
- Multi-account support
- Mobile alerts via Telegram/SMS
- Integration with additional brokers

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project is provided as-is for educational and analysis purposes.

## Support

For issues and questions:
- Open an issue on GitHub
- Review the requirements.md for detailed specifications
- Check IBKR API documentation for connection issues

## Acknowledgments

- Built using [ib_insync](https://github.com/erdewit/ib_insync) for IBKR connectivity
- Black-Scholes implementation based on standard finance literature
- Scenario parameters inspired by real market events and option trading strategies

---

**Disclaimer**: This software is for informational purposes only. It is not investment advice. Trading options and other financial instruments involves risk. You can lose money. Always do your own research and consult with licensed financial professionals.
