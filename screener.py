#!/usr/bin/env python3
"""
Combined Stock Screener and Watchlist Processor
1. Monitors email for stock symbols from scanner alerts
2. Validates them using EMA and Bollinger Band criteria
3. Adds valid tickers to watchlist with their low price for limit order placement
"""

import time
import logging
import os
import re
import socket
from typing import Set, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from env import mail_username, mail_password
from imap_tools import MailBox, AND

# Set global socket timeout for all network operations (yfinance, etc.)
socket.setdefaulttimeout(15)

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Setup logging - prevent duplicate handlers
logger = logging.getLogger(__name__)

# Only add handlers if they don't already exist
if not logger.handlers:
    logger.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler
    file_handler = logging.FileHandler('scanner_processor.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

# File paths
SCANNER_FILE = Path(__file__).parent / "scanner.txt"  # Input: Tickers from scanner
WATCHLIST_FILE = Path(__file__).parent / "watchlist.txt"  # Output: Validated tickers with low price
OPENPOSITIONS_FILE = Path(__file__).parent / "openpositions.txt"  # Already positioned tickers


# Email extraction functions from mailreader.py
def extract_ticker_symbols(text):
    """Extract ticker symbols from the text using regex pattern.
    Only extracts symbols from emails containing 'BBAuto' or 'BBAUTO'.
    """
    if 'bbauto' not in text.lower():
        return []

    ticker_pattern = r'\b[A-Z]{1,5}\b'
    tickers = re.findall(ticker_pattern, text)

    excluded_words = {'ALERT', 'NEW', 'SYMBOL', 'WAS', 'ADDED', 'TO', 'BBAUTO', 'FROM', 'THE', 'IN', 'AT', 'ON', 'BY', 'FOR', 'WITH'}
    return [ticker for ticker in tickers if ticker not in excluded_words]


def update_scanner_file(tickers):
    """Append unique tickers to scanner.txt without overwriting existing ones."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "scanner.txt")

    existing_tickers = set()
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            existing_tickers = set(line.strip() for line in file.readlines())

    updated_tickers = existing_tickers.union(tickers)

    try:
        with open(file_path, "w") as file:
            for ticker in updated_tickers:
                file.write(ticker + "\n")
    except Exception as e:
        logger.error(f"Error updating scanner file: {e}")


def check_email_for_tickers():
    """Check email for new ticker symbols and add them to scanner.txt"""
    import socket
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    def _check_email():
        """Inner function to check email"""
        yesterday = datetime.now().date() - timedelta(days=1)

        with MailBox("imap.gmail.com").login(mail_username, mail_password, "INBOX") as mb:
            # OPTIMIZED: Filter at IMAP level for BBAuto emails from last 24 hours only
            for msg in mb.fetch(
                criteria=AND(
                    seen=False,
                    from_='alerts@thinkorswim.com',
                    date_gte=yesterday,
                    subject='BBAuto'
                ),
                mark_seen=False
            ):
                # Mark as seen immediately to prevent duplicate processing
                mb.flag(msg.uid, ['\\Seen'], True)

                full_content = f"{msg.subject} {msg.text}"
                tickers = extract_ticker_symbols(full_content)

                if tickers:
                    update_scanner_file(tickers)
                    logger.info(f"Signal received: Ticker(s) {', '.join(tickers)} added to scanner")

                mb.move(msg.uid, '[Gmail]/Trash')

    try:
        # Set socket timeout to prevent hanging - increased from 3s to 10s
        socket.setdefaulttimeout(10)

        # Use ThreadPoolExecutor with timeout to force-kill email check if it hangs
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_check_email)
            try:
                future.result(timeout=15)  # Increased from 5s to 15s
            except TimeoutError:
                logger.warning("Email check timed out - continuing with scanner processing")
    except socket.timeout:
        logger.warning("Email socket timed out - continuing with scanner processing")
    except Exception as e:
        logger.warning(f"Email check skipped: {e}")


class ScannerProcessor:
    """Process tickers from scanner and validate them for watchlist addition."""

    def __init__(self):
        self.known_scanner_symbols: Set[str] = set()
        self.open_positions: Set[str] = set()
        self._initialize()

    def _initialize(self):
        """Initialize by loading open positions."""
        self._clear_screen()
        logger.info("Initializing Scanner...")
        # OPTIMIZED: Removed unnecessary 1 second sleep

        if OPENPOSITIONS_FILE.exists():
            self.open_positions = self._load_symbols(OPENPOSITIONS_FILE)
            logger.info(f"Loaded {len(self.open_positions)} open positions")

    def _clear_screen(self):
        """Clear the terminal screen."""
        os.system('clear' if os.name != 'nt' else 'cls')

    def _load_symbols(self, file_path: Path) -> Set[str]:
        """Load ticker symbols from a file."""
        try:
            # OPTIMIZED: Read entire file at once and process with set comprehension
            with open(file_path, 'r') as f:
                return {line.split()[0].upper() for line in f if line.strip() and line.split()}
        except Exception as e:
            logger.error(f"Error loading symbols from {file_path}: {e}")
            return set()

    def _count_scanner_tickers(self) -> int:
        """Count number of tickers in scanner file."""
        if not SCANNER_FILE.exists():
            return 0
        try:
            # OPTIMIZED: Use sum with generator expression instead of list comprehension
            with open(SCANNER_FILE, 'r') as f:
                return sum(1 for line in f if line.strip())
        except:
            return 0

    def get_first_ticker_from_scanner(self) -> Optional[str]:
        """Get the first ticker from scanner file that isn't in open positions."""
        if not SCANNER_FILE.exists():
            return None

        try:
            # OPTIMIZED: Read file once and process efficiently
            with open(SCANNER_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    ticker = line.split()[0].upper()
                    logger.info(f"Checking ticker: {ticker}")

                    if ticker not in self.open_positions:
                        logger.info(f"✓ Found ticker to process: {ticker}")
                        return ticker
                    else:
                        logger.info(f"✗ Skipping {ticker} - already in open positions")
                        self._remove_ticker_from_scanner(ticker)

            return None
        except Exception as e:
            logger.error(f"Error reading scanner file: {e}")
            return None

    def _remove_ticker_from_scanner(self, ticker_to_remove: str):
        """Remove a ticker from the scanner file."""
        try:
            # OPTIMIZED: Read, filter, and write in one efficient operation
            with open(SCANNER_FILE, 'r') as f:
                remaining_lines = [
                    line for line in f
                    if line.strip() and line.strip().split()[0].upper() != ticker_to_remove.upper()
                ]

            with open(SCANNER_FILE, 'w') as f:
                f.writelines(remaining_lines)

            logger.info(f"Removed {ticker_to_remove} from scanner.txt")
        except Exception as e:
            logger.error(f"Error removing {ticker_to_remove} from scanner: {e}")

    def download_historical_data(self, symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """
        Download historical data for ticker.

        Args:
            symbol: Ticker symbol from scanner
            period: Time period (default: 6mo to ensure enough data for 100 EMA)

        Returns:
            DataFrame with historical data or None if failed
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info(f"Downloading historical data for {symbol}... (attempt {attempt + 1}/{max_retries})")

                # OPTIMIZED: Use original Ticker().history() method - works correctly with calculations
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period)

                if df.empty:
                    logger.warning(f"No data available for {symbol}")
                    return None

                logger.info(f"Downloaded {len(df)} data points for {symbol}")
                return df

            except socket.timeout:
                logger.warning(f"Download timeout for {symbol} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
            except Exception as e:
                logger.error(f"Error downloading data for {symbol}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None

        return None

    def calculate_ema(self, df: pd.DataFrame, period: int) -> Optional[pd.Series]:
        """
        Calculate Exponential Moving Average.

        Args:
            df: DataFrame with historical data
            period: EMA period (e.g., 21 or 100)

        Returns:
            Series of EMA values or None if calculation fails
        """
        try:
            if len(df) < period:
                logger.warning(f"Not enough data points ({len(df)}) to calculate {period} EMA")
                return None

            ema = df['Close'].ewm(span=period, adjust=False).mean()

            logger.info(f"Calculated {period} EMA: {ema.iloc[-1]:.2f}")
            return ema

        except Exception as e:
            logger.error(f"Error calculating {period} EMA: {e}")
            return None

    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Optional[Dict[str, pd.Series]]:
        """
        Calculate Bollinger Bands.

        Args:
            df: DataFrame with historical data
            period: Moving average period (default: 20)
            std_dev: Number of standard deviations (default: 2)

        Returns:
            Dictionary with 'middle', 'upper', 'lower' band Series or None if calculation fails
        """
        try:
            if len(df) < period:
                logger.warning(f"Not enough data points ({len(df)}) to calculate Bollinger Bands")
                return None

            middle_band = df['Close'].rolling(window=period).mean()
            std = df['Close'].rolling(window=period).std()
            upper_band = middle_band + (std * std_dev)
            lower_band = middle_band - (std * std_dev)

            logger.info(f"Calculated Bollinger Bands - Upper: {upper_band.iloc[-1]:.2f}, Middle: {middle_band.iloc[-1]:.2f}")

            return {
                'middle': middle_band,
                'upper': upper_band,
                'lower': lower_band
            }

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None

    def calculate_bars_since_crossover(self, ema_21: pd.Series, ema_100: pd.Series) -> Optional[int]:
        """
        Calculate number of bars since 21 EMA crossed above 100 EMA.

        Args:
            ema_21: Series of 21 EMA values
            ema_100: Series of 100 EMA values

        Returns:
            Number of bars since crossover, or None if no recent crossover found
        """
        try:
            above = ema_21 > ema_100

            if not above.iloc[-1]:
                return None

            for i in range(len(above) - 1, 0, -1):
                if not above.iloc[i-1] and above.iloc[i]:
                    bars_since = len(above) - i
                    return bars_since
                elif not above.iloc[i-1]:
                    bars_since = len(above) - i
                    return bars_since

            return len(above)

        except Exception as e:
            logger.error(f"Error calculating bars since crossover: {e}")
            return None

    def validate_ema_criteria(self, symbol: str) -> Tuple[bool, Dict]:
        """
        Validate that ticker meets all criteria:
        1. 21 EMA is above 100 EMA
        2. Current bar is bullish (Close > Open)
        3. Current bar is above upper Bollinger Band

        Args:
            symbol: Ticker symbol from scanner

        Returns:
            Tuple of (is_valid, validation_values_dict) with low price for limit order
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Validating ticker {symbol} from scanner")
        logger.info(f"{'='*60}")

        df = self.download_historical_data(symbol)
        if df is None:
            return False, {}

        ema_21_series = self.calculate_ema(df, 21)
        ema_100_series = self.calculate_ema(df, 100)

        if ema_21_series is None or ema_100_series is None:
            logger.warning(f"Could not calculate EMAs for {symbol}")
            return False, {}

        bb_bands = self.calculate_bollinger_bands(df, period=20, std_dev=2)
        if bb_bands is None:
            logger.warning(f"Could not calculate Bollinger Bands for {symbol}")
            return False, {}

        ema_21 = ema_21_series.iloc[-1]
        ema_100 = ema_100_series.iloc[-1]
        bb_upper = bb_bands['upper'].iloc[-1]
        bb_middle = bb_bands['middle'].iloc[-1]

        current_close = df['Close'].iloc[-1]
        current_open = df['Open'].iloc[-1]
        current_low = df['Low'].iloc[-1]

        ema_check = ema_21 > ema_100
        bullish_bar = current_close > current_open
        above_bb_upper = current_close > bb_upper

        is_valid = ema_check and bullish_bar and above_bb_upper

        bars_since_crossover = None
        if ema_check:
            bars_since_crossover = self.calculate_bars_since_crossover(ema_21_series, ema_100_series)

        validation_values = {
            'ema_21': ema_21,
            'ema_100': ema_100,
            'bb_upper': bb_upper,
            'bb_middle': bb_middle,
            'current_price': current_close,
            'current_open': current_open,
            'low_price': current_low,
            'date': df.index[-1].strftime('%Y-%m-%d'),
            'bars_since_crossover': bars_since_crossover,
            'ema_check': ema_check,
            'bullish_bar': bullish_bar,
            'above_bb_upper': above_bb_upper
        }

        logger.info(f"\nResults for {symbol}:")
        logger.info(f"  Current Price (Close):   ${current_close:.2f}")
        logger.info(f"  Current Open:            ${current_open:.2f}")
        logger.info(f"  Low:                     ${current_low:.2f}")
        logger.info(f"  21 EMA:                  ${ema_21:.2f}")
        logger.info(f"  100 EMA:                 ${ema_100:.2f}")
        logger.info(f"  BB Upper Band:           ${bb_upper:.2f}")
        logger.info(f"  BB Middle Band:          ${bb_middle:.2f}")

        if bars_since_crossover is not None:
            logger.info(f"  Bars Since Crossover:    {bars_since_crossover} bars")
        else:
            logger.info(f"  Bars Since Crossover:    N/A (not applicable)")

        logger.info(f"\n  Validation Checks:")
        logger.info(f"    21 EMA > 100 EMA:      {Colors.GREEN + '✓ PASS' + Colors.RESET if ema_check else Colors.RED + '✗ FAIL' + Colors.RESET}")
        logger.info(f"    Bullish Bar:           {Colors.GREEN + '✓ PASS' + Colors.RESET if bullish_bar else Colors.RED + '✗ FAIL' + Colors.RESET} (Close {'>' if bullish_bar else '<='} Open)")
        logger.info(f"    Above BB Upper:        {Colors.GREEN + '✓ PASS' + Colors.RESET if above_bb_upper else Colors.RED + '✗ FAIL' + Colors.RESET} (Close {'>' if above_bb_upper else '<='} ${bb_upper:.2f})")

        logger.info(f"\n  Final Status:            {Colors.BOLD + Colors.GREEN + '✓ PASSED - Adding to watchlist' + Colors.RESET if is_valid else Colors.BOLD + Colors.RED + '✗ FAILED - Not adding to watchlist' + Colors.RESET}")
        logger.info(f"{'='*60}\n")

        return is_valid, validation_values

    def _get_watchlist_symbols(self) -> Set[str]:
        """Get all symbols currently in watchlist."""
        if not WATCHLIST_FILE.exists():
            return set()
        return self._load_symbols(WATCHLIST_FILE)

    def add_to_watchlist(self, symbol: str, low_price: float):
        """Add validated ticker to watchlist with low price for limit order."""
        try:
            watchlist_symbols = self._get_watchlist_symbols()
            if symbol in watchlist_symbols:
                logger.info(f"⚠ {symbol} already exists in watchlist - skipping duplicate")
                return

            with open(WATCHLIST_FILE, 'a') as f:
                f.write(f"{symbol} {low_price:.2f}\n")
            logger.info(f"✓ Added {symbol} to watchlist with limit price ${low_price:.2f}")
        except Exception as e:
            logger.error(f"Error adding {symbol} to watchlist: {e}")

    def process_next_ticker(self):
        """Process the next ticker from scanner (one at a time)."""
        ticker = self.get_first_ticker_from_scanner()

        if not ticker:
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing ticker from scanner: {ticker}")
        logger.info(f"{'='*60}")

        is_valid, ema_values = self.validate_ema_criteria(ticker)

        if is_valid:
            low_price = ema_values.get('low_price', 0)
            self.add_to_watchlist(ticker, low_price)
            self._remove_ticker_from_scanner(ticker)
        else:
            logger.info(f"✗ {ticker} does not meet all validation criteria - Not adding to watchlist")
            self._remove_ticker_from_scanner(ticker)

    def _countdown_timer(self, seconds: int):
        """Display a countdown timer showing seconds until next check."""
        import sys

        # Count down from seconds to 1
        for remaining in range(seconds, 0, -1):
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            message = f"\r{timestamp} - INFO - Scanner Active - Checking again in {remaining} seconds"
            sys.stdout.write(message)
            sys.stdout.flush()
            time.sleep(1)

        # Clear the line after countdown reaches 0
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

    def run(self, check_interval: int = 10):
        """
        Run the combined email monitoring and scanner processor loop.

        Args:
            check_interval: Seconds between checks (default: 10)
        """
        logger.info(f"Scanner Active - Checking again in {check_interval} seconds")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                # Clear screen before each new scan cycle
                self._clear_screen()

                # Reload positions for next check
                if OPENPOSITIONS_FILE.exists():
                    self.open_positions = self._load_symbols(OPENPOSITIONS_FILE)
                    logger.info(f"Loaded {len(self.open_positions)} open positions")

                # Check email for new tickers (with timeout)
                try:
                    check_email_for_tickers()
                except Exception as e:
                    logger.error(f"Email check failed: {e}")

                # Process tickers from scanner
                try:
                    ticker_count = self._count_scanner_tickers()
                    logger.info(f"{ticker_count} stocks found in scanner.txt")
                    self.process_next_ticker()
                    logger.info("Scanner processing completed")
                except Exception as e:
                    logger.error(f"Scanner processing failed: {e}")

                # Show countdown timer
                #logger.info(f"\nWaiting {check_interval} seconds before next scan...")
                self._countdown_timer(check_interval)

        except KeyboardInterrupt:
            logger.info("\nScanner processor stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in processing loop: {e}")
            raise


def main():
    """Main entry point."""
    processor = ScannerProcessor()
    processor.run(check_interval=10)


if __name__ == "__main__":
    main()
