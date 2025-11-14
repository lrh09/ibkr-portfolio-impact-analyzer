Build a Portfolio Risk Analyzer with the following components:

## 1. DATA COLLECTION MODULE

### IBKR Connection Manager
- Establish connection to TWS/Gateway (ports 7497 for paper, 7496 for live)
- Use ib_insync library for cleaner async handling
- Implement reconnection logic with exponential backoff
- Handle rate limiting (no more than 50 messages/second)

### Position Tracker
Create a Position class that stores:
- Symbol, quantity, entry price, current price
- For options: underlying, strike, expiration, type, contract multiplier (100)
- Current Greeks and IV
- Last update timestamp

Pull all positions on startup and subscribe to real-time updates.

### Market Data Manager  
- Subscribe to real-time data for all position underlyings
- For options, request computed Greeks (reqMktData with genericTickList='13,106')
- Cache data with 1-second TTL to reduce API calls
- Store 5-minute snapshots in SQLite for historical analysis

## 2. CALENDAR INTEGRATION MODULE

### Event Calendar Builder
Create an events database with:
- Event type (FOMC, earnings, expiration, economic data)
- Date and time (with timezone handling)
- Expected volatility impact (high/medium/low)
- Affected symbols (specific stocks or 'MARKET' for broad events)

Sources to integrate:
- pandas_market_calendars for market hours and holidays
- yfinance for earnings dates: yf.Ticker(symbol).calendar
- Manual CSV for Fed meetings (8 per year, predictable)
- Options expiration: Third Friday calculator + 0DTE dates

### Event Detection
- Check T+0, T+1, T+5 for upcoming events
- Flag positions with earnings in next 30 days
- Identify weekly options near major events

## 3. SCENARIO ENGINE

### Beta-Weighted IV Model
Implement the core IV shift model:
```python
def calculate_iv_shift(base_iv, moneyness, dte, scenario_type, market_move):
    """
    Calculate new IV based on scenario
    
    Factors:
    - moneyness_beta: OTM puts (1.3), ATM (1.0), OTM calls (0.8)
    - time_beta: 0-7 days (1.5), 8-30 days (1.0), 31-90 days (0.7), 90+ days (0.5)
    - scenario_multiplier: Based on scenario_type
    """
    
    # Calculate betas
    moneyness_beta = get_moneyness_beta(moneyness)
    time_beta = get_time_beta(dte)
    
    # Apply scenario
    return base_iv * (1 + scenario_multiplier * moneyness_beta * time_beta)
```

### Scenario Templates
Create pre-built scenarios with these parameters:

1. **Normal Day** 
   - Spot: 0%, IV: 0%

2. **Earnings Scenarios**
   - "Earnings Beat": Spot +5%, IV: -35% (0-7 DTE), -15% (8-30 DTE), -5% (30+ DTE)
   - "Earnings Miss": Spot -8%, IV: -30% (0-7 DTE), -10% (8-30 DTE), 0% (30+ DTE)
   - "Earnings Inline": Spot ±1%, IV: -40% (0-7 DTE), -20% (8-30 DTE), -5% (30+ DTE)

3. **Market Stress Scenarios**
   - "Market Panic": Spot -5%, IV: Puts +60%, ATM +35%, Calls +25%
   - "Flash Crash": Spot -8%, IV: Puts +100%, ATM +50%, Calls +30%
   - "Black Swan": Spot -20%, IV: All +150% (proportional by moneyness)

4. **Fed/Macro Events**
   - "Fed Hawkish": Spot -2%, IV: +20% uniform
   - "Fed Dovish": Spot +1.5%, IV: -10% uniform
   - "Fed Neutral": Spot ±0.5%, IV: -5% uniform

5. **Squeeze/Rally**
   - "Short Squeeze": Spot +10%, Calls IV +30%, Puts IV -10%
   - "FOMO Rally": Spot +5%, Calls IV +15%, Puts IV -20%
   - "Relief Rally": Spot +3%, IV -15% uniform

6. **Time Decay Scenarios**
   - "1 Day Pass": Theta decay, IV -1% for <30 DTE
   - "Weekend": 3 days theta, IV -2% for weeklies
   - "1 Week": 7 days theta, adjust IV by term structure

### Custom Scenario Builder
Allow user-defined scenarios with:
- Spot price change (-50% to +50%)
- IV multiplier by option type
- Correlation rules (if spot down > 5%, add extra IV to puts)

## 4. VALUATION ENGINE

### Black-Scholes Calculator
Implement vectorized Black-Scholes for fast calculation:
- Use numpy arrays for batch processing
- Cache risk-free rate (update daily from FRED or use 5%)
- Handle American options with binomial tree (for early exercise)
- Account for dividends

### Portfolio Aggregation
For each scenario, calculate:
1. New stock values = current_price * (1 + spot_change) * shares
2. New option values using Black-Scholes with adjusted spot and IV
3. Total portfolio value = sum(all positions)
4. Position-level P&L = new_value - current_value
5. Portfolio P&L = new_portfolio_value - current_portfolio_value
6. Greeks aggregation (portfolio Delta, Vega, etc.)

## 5. RISK METRICS MODULE

### Calculate Key Metrics
- **Position Level:**
  - $ P&L and % change per scenario
  - Contribution to portfolio risk
  - Greeks exposure
  - Days to expiration
  - IV rank/percentile

- **Portfolio Level:**
  - Total $ P&L per scenario
  - % portfolio change
  - Aggregate Greeks
  - VaR (95% and 99%)
  - Max drawdown across scenarios
  - Correlation matrix between positions

### Risk Alerts
Flag when:
- Any scenario shows >10% portfolio loss
- Position concentration >25% of portfolio
- Earnings inside option expiration
- IV rank >80% (consider selling) or <20% (consider buying)
- Short gamma exposure exceeds threshold

## 6. OUTPUT & VISUALIZATION

### Reports Structure
Generate DataFrames with:

1. **Scenario Summary Report**
ScenarioPortfolio P&L% ChangeWorst PositionBest PositionPanic-$25,000-12.5%TSLA Put -$5KVIX Call +$2K

2. **Position Detail Report**
PositionCurrentPanicEarningsRallyMax LossMax GainTSLA Call$5,000-$2K-$3K+$8K-$4K+$10K

3. **Risk Matrix (Heat Map Data)**
- Rows: Spot moves (-20% to +20%)
- Columns: IV changes (-50% to +100%)
- Values: Portfolio P&L

### Export Functions
- CSV export for all reports
- JSON export for scenario results
- Pickle DataFrame for later analysis
- PDF report generation with charts

## 7. AUTOMATION & MONITORING

### Scheduled Tasks
- Start-of-day: Pull positions, update calendars
- Every minute: Update prices and Greeks
- Every 5 minutes: Run all scenarios, check alerts
- End-of-day: Generate risk report, store snapshot

### Alert System
- Console warnings for immediate risks
- Log file for all scenario runs
- Optional: Email/SMS for critical alerts
- Dashboard with traffic light indicators

## 8. CONFIGURATION

Create config.yaml for:
```yaml
ibkr:
  host: "127.0.0.1"
  port: 7497  # paper trading
  client_id: 1

scenarios:
  use_calendar: true
  auto_detect_earnings: true
  default_iv_model: "beta_weighted"
  
risk_limits:
  max_portfolio_loss: 0.15
  position_concentration: 0.25
  vega_limit: 10000
  
data:
  cache_ttl: 1  # seconds
  snapshot_interval: 300  # 5 minutes
  
alerts:
  enabled: true
  email: null
  console: true
```

## 9. MAIN EXECUTION FLOW
```python
# Pseudocode for main loop
def main():
    # Initialize
    ib = connect_to_ibkr()
    positions = load_positions(ib)
    calendar = load_market_calendar()
    
    # Real-time loop
    while market_is_open():
        # Update market data
        update_prices_and_greeks(positions)
        
        # Check for upcoming events
        events = check_calendar_events(calendar, positions)
        
        # Run scenarios
        results = {}
        for scenario in get_relevant_scenarios(events):
            results[scenario] = run_scenario(positions, scenario)
        
        # Calculate risk metrics
        risk_report = calculate_risk_metrics(results)
        
        # Check alerts
        check_risk_alerts(risk_report)
        
        # Update dashboard/display
        update_display(risk_report)
        
        sleep(60)  # Run every minute
    
    # End of day
    generate_daily_report(results)
    save_snapshot_to_db(positions, results)
```

## 10. ERROR HANDLING

- Wrap all IBKR calls in try/except with retry logic
- Handle missing IV data (use ATM IV or interpolate)
- Validate option pricing (no negative values)
- Check for stale data (timestamp > 60 seconds)
- Fallback to last known values if connection lost
- Log all errors with context for debugging

Start by building the IBKR connection and position loader, then add scenario engine, and finally the visualization layer.


Testing & Validation Requirements

Unit Tests:

Black-Scholes calculation accuracy
IV shift model logic
Calendar event detection


Integration Tests:

IBKR paper trading connection
Full scenario execution
Report generation


Validation:

Compare to IBKR Risk Navigator
Backtest against historical events
Verify against real market moves



Performance Targets

Load 100 positions in <5 seconds
Run 10 scenarios in <2 seconds
Real-time updates with <1 second lag
Handle 500+ positions without degradation


Continue to think of the possibility to enhance.