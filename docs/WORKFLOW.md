# Portfolio Manager Workflow

## System Overview

This automated trading system consists of three main components:

1. **screener.py** - Email monitoring and stock validation
2. **main.py** - Portfolio monitoring and order execution
3. **watchlist.txt** - Bridge between screener and order placement

## Workflow Diagram

```
Email Alert (BBAuto)
    ↓
screener.py monitors email
    ↓
Validates ticker with EMA & Bollinger Bands
    ↓
Adds to watchlist.txt (TICKER LIMIT_PRICE)
    ↓
main.py detects watchlist.txt change
    ↓
Places limit orders via Schwab API
    ↓
Clears watchlist.txt
    ↓
Updates portfolio display
```

## File Formats

### watchlist.txt
```
TICKER LIMIT_PRICE
RANI 1.83
SKYX 1.41
WHWK 2.08
```

### openpositions.txt
```
TICKER
AAPL
TSLA
```

## Components

### screener.py
- **Purpose**: Monitor email for scanner alerts, validate stocks, populate watchlist
- **Monitors**: Email inbox (alerts@thinkorswim.com)
- **Validates**:
  - 21 EMA > 100 EMA
  - Current bar is bullish (Close > Open)
  - Price above upper Bollinger Band
- **Output**: watchlist.txt with ticker and limit price (current low)
- **Refresh**: Every 10 seconds

### main.py
- **Purpose**: Portfolio monitoring and automated order execution
- **Monitors**: watchlist.txt for changes
- **Displays**:
  - Account balance and liquidation value
  - Open positions with real-time P&L
- **Executes**: Limit buy orders from watchlist
- **Order Size**: 100 shares per ticker (default)
- **Refresh**: Every 60 seconds

## Order Placement Details

### Order Type: Limit Buy
- **Session**: NORMAL (regular trading hours)
- **Duration**: DAY (expires at market close)
- **Quantity**: 100 shares
- **Price**: Limit price from watchlist (current day's low)

### API Payload Example
```json
{
  "orderType": "LIMIT",
  "session": "NORMAL",
  "duration": "DAY",
  "orderStrategyType": "SINGLE",
  "price": "1.83",
  "orderLegCollection": [{
    "instruction": "BUY",
    "quantity": 100,
    "instrument": {
      "symbol": "RANI",
      "assetType": "EQUITY"
    }
  }]
}
```

## Validation Criteria

### Entry Requirements (screener.py)
1. ✓ 21 EMA > 100 EMA (bullish trend)
2. ✓ Bullish bar (Close > Open)
3. ✓ Price > Upper Bollinger Band (momentum breakout)

### Exclusions
- Tickers already in open positions
- Tickers already in watchlist (no duplicates)

## Running the System

### Start Screener
```bash
cd "/home/j0shusmc/Projects/Portfolio Manager"
source venv/bin/activate
python screener.py
```

### Start Main Portfolio Manager
```bash
cd "/home/j0shusmc/Projects/Portfolio Manager"
source venv/bin/activate
python main.py
```

## Logging

### screener.py
- **File**: scanner_processor.log
- **Contains**: Validation results, ticker processing, email checks

### main.py
- **File**: portfolio_manager.log
- **Contains**: Order placement, API responses, account updates

## Error Handling

### Authentication Errors
If you see refresh token errors:
```bash
rm tokens.json
# Re-run main.py to re-authenticate
python main.py
```

### Order Failures
- Logged to portfolio_manager.log
- Non-blocking: continues processing remaining tickers
- Failed orders remain in watchlist for retry

## Safety Features

1. **Duplicate Prevention**: Skips tickers already in open positions
2. **Validation Before Order**: Only validated stocks reach watchlist
3. **Comprehensive Logging**: All actions logged for audit trail
4. **Error Recovery**: Graceful handling of API failures
5. **File Clearing**: Watchlist cleared after processing to prevent duplicate orders

## Configuration

### env.py
```python
app_key = "YOUR_APP_KEY"
app_secret = "YOUR_APP_SECRET"
callback_url = "https://127.0.0.1"
account_nbr = "YOUR_ACCOUNT_NUMBER"
mail_username = "YOUR_EMAIL"
mail_password = "YOUR_APP_PASSWORD"
```

## Customization

### Change Order Quantity
Edit `create_limit_order()` in [main.py:191](../main.py#L191):
```python
def create_limit_order(symbol, limit_price, quantity=100):  # Change default here
```

### Change Refresh Intervals
- **screener.py**: Line 462 - `check_interval=10`
- **main.py**: Line 42 - `countdown_timer(60)`

### Modify Validation Criteria
Edit `validate_ema_criteria()` in [screener.py:294](../screener.py#L294)
