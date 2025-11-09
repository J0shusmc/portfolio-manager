# Portfolio Manager

An automated trading system that integrates with Charles Schwab's API to automate watchlist scanners and execute trades automatically.

## Overview

This Portfolio Manager application connects to your Charles Schwab account to:
- Monitor and scan watchlists
- Analyze market data and stock screening criteria
- Automatically execute trades based on your predefined strategies
- Track open positions and portfolio performance
- Send email notifications for important events

## Features

- **Automated Watchlist Scanning**: Continuously monitor stocks in your watchlists
- **Smart Screener**: Filter and identify trading opportunities based on technical indicators
- **Trade Automation**: Execute buy/sell orders automatically based on your criteria
- **Position Tracking**: Monitor open positions and portfolio status
- **Email Integration**: Receive notifications and updates via email
- **Portfolio Display**: Web-based interface to view your portfolio status

## Prerequisites

- Python 3.8 or higher
- Charles Schwab brokerage account
- Charles Schwab API credentials (App Key and Secret)
- Email account for notifications (Gmail recommended)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/J0shusmc/portfolio-manager.git
cd portfolio-manager
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Set up your credentials:
```bash
cp env.example.py env.py
# Edit env.py with your actual credentials
```

## Configuration

### Charles Schwab API Setup

1. Visit [Charles Schwab Developer Portal](https://developer.schwab.com/)
2. Create a new application to get your App Key and App Secret
3. Add your credentials to `env.py`:
   - `app_key`: Your Charles Schwab App Key
   - `app_secret`: Your Charles Schwab App Secret
   - `callback_url`: Redirect URL (default: https://127.0.0.1)
   - `account_nbr`: Your Schwab account number

### Email Configuration

Configure email credentials in `env.py` for notifications:
- `mail_username`: Your email address
- `mail_password`: App password (for Gmail: [create here](https://support.google.com/accounts/answer/185833))

## Usage

### Running with DNS Override (Recommended)
```bash
./run_with_dns.sh
```

### Standard Execution
```bash
python main.py
```

### Individual Components

- **Mail Reader**: `python mailreader.py` - Read portfolio emails
- **Screener**: `python screener.py` - Run stock screener
- **Portfolio Display**: `python portfolio_display.py` - Launch web interface

## Project Structure

```
portfolio-manager/
├── main.py                 # Main application entry point
├── mailreader.py          # Email integration for portfolio updates
├── screener.py            # Stock screening and analysis
├── portfolio_display.py   # Web interface for portfolio viewing
├── openpositions.txt      # Current open positions tracker
├── watchlist.txt          # Stocks to monitor
├── scanner.txt            # Scanner results and alerts
├── env.example.py         # Configuration template
├── requirements.txt       # Python dependencies
├── run_with_dns.sh       # DNS-aware startup script
└── docs/                  # Additional documentation
    └── WORKFLOW.md        # Development workflow guide
```

## Trading Files

- **openpositions.txt**: Tracks your current open positions
- **watchlist.txt**: Maintains list of stocks to monitor
- **scanner.txt**: Stores screening results and trade signals

## Security Notes

⚠️ **IMPORTANT**:
- Never commit `env.py` to version control
- Keep your API credentials secure
- The `.gitignore` file is configured to exclude sensitive files
- Use App Passwords for email accounts, not your main password

## Dependencies

Key packages used:
- `schwab-py`: Charles Schwab API Python client
- `schwabdev`: Charles Schwab development tools
- `yfinance`: Yahoo Finance market data
- `pandas`: Data analysis and manipulation
- `imap-tools`: Email reading capabilities
- `Flask`: Web interface framework

See `requirements.txt` for complete list.

## Disclaimer

⚠️ **USE AT YOUR OWN RISK**: This is an automated trading system that can execute real trades with real money.

- Always test thoroughly in a paper trading environment first
- Monitor your automated trades regularly
- Understand the strategies and logic before enabling automation
- The authors are not responsible for any financial losses
- Trading stocks involves risk of loss

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is provided as-is for educational and personal use.

## Support

For questions or issues:
- Open an issue on GitHub
- Review the documentation in `/docs`

---

**Note**: This application is designed for personal use with Charles Schwab accounts. Ensure you comply with all applicable trading regulations and Charles Schwab's API terms of service.
