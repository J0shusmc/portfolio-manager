import schwabdev
import mailreader
from env import app_key, app_secret, callback_url, account_nbr
from time import sleep
import os
import time
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('portfolio_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    client = schwabdev.Client(app_key, app_secret, callback_url)
    sleep(2)
    print("\n")

    # Get account hash for order placement
    account_hash = get_account_hash(client)
    if not account_hash:
        print("Error: Could not retrieve account hash. Exiting.")
        return

    # Fetch account details on startup
    print("Fetching initial account information...")
    fetch_account_details(client)
    sleep(1)  # Pause after portfolio display

    watchlist_file_path = 'watchlist.txt'

    # Check watchlist on startup
    if os.path.exists(watchlist_file_path) and os.path.getsize(watchlist_file_path) > 0:
        print("Found items in watchlist. Processing orders...")
        process_watchlist_orders(client, account_hash, watchlist_file_path)
        # Refresh account details after placing orders
        fetch_account_details(client)
        sleep(1)  # Pause after portfolio refresh
    else:
        print("Watchlist is empty.")
        sleep(1)

    last_watchlist_mod_time = None
    if os.path.exists(watchlist_file_path):
        last_watchlist_mod_time = os.path.getmtime(watchlist_file_path)

    while True:
        # Countdown timer for rechecking
        countdown_timer(60)

        # Clear screen before next check
        clear_screen()

        # Check if watchlist.txt has been modified
        if os.path.exists(watchlist_file_path):
            current_mod_time = os.path.getmtime(watchlist_file_path)
            if last_watchlist_mod_time is None or current_mod_time != last_watchlist_mod_time:
                last_watchlist_mod_time = current_mod_time

                # Only process if file is not empty
                if os.path.getsize(watchlist_file_path) > 0:
                    print("\nDetected changes in watchlist.txt. Processing orders...")
                    process_watchlist_orders(client, account_hash, watchlist_file_path)

        # Always refresh and display portfolio
        fetch_account_details(client)
        sleep(1)  # Pause after portfolio refresh

        # Display watchlist status
        print()
        display_watchlist_status()


def fetch_account_details(client):
    # Clear the screen before displaying new information
    clear_screen()

    # Get linked accounts to retrieve account hash value
    try:
        linked_accounts_response = client.account_linked().json()
    except Exception as e:
        print(f"Error fetching linked accounts: {e}")
        print("Please re-authenticate by deleting tokens and restarting the application.")
        return

    # Handle case where response might be a dict with error or a list
    if isinstance(linked_accounts_response, dict):
        if 'error' in linked_accounts_response:
            print(f"API Error: {linked_accounts_response}")
            print("Please re-authenticate by deleting tokens and restarting the application.")
            return
        # Sometimes API returns a dict wrapping the list
        linked_accounts = linked_accounts_response.get('accounts', [linked_accounts_response])
    elif isinstance(linked_accounts_response, list):
        linked_accounts = linked_accounts_response
    else:
        print(f"Unexpected response type: {type(linked_accounts_response)}")
        print(f"Response: {linked_accounts_response}")
        return

    # Find the account with matching account number and get the hash value
    account_hash = None
    for account in linked_accounts:
        if isinstance(account, dict) and account.get('accountNumber') == account_nbr:
            account_hash = account.get('hashValue')
            break

    if account_hash is None:
        print("Account not found.")
        print(f"Available accounts: {linked_accounts}")
        return

    # Fetch account details for the selected account using the hash value
    account_details = client.account_details(account_hash, fields="positions").json()

    # Display account information
    account_number = account_details['securitiesAccount']['accountNumber']
    masked_account_number = f"*******{account_number[-3:]}"
    account_type = account_details['securitiesAccount']['type']
    current_balances = account_details['securitiesAccount']['currentBalances']

    # Get cash balance and liquidation value
    cash_balance = current_balances.get('cashBalance', 0.0)
    liquidation_value = current_balances.get('liquidationValue', 0.0)

    print("-" * 40)
    print(f"Account Type: {account_type}")
    print(f"Account Number: {masked_account_number}")
    print(f"Cash Balance: ${cash_balance:.2f}")
    print(f"Liquidation Value: ${liquidation_value:.2f}")
    print("-" * 40)

    # Fetch and display account positions
    positions = account_details['securitiesAccount'].get('positions', [])
    with open('openpositions.txt', 'w') as f:
        if positions:
            print("Positions:")

            # Collect all symbols for batch quote request
            symbols = [position['instrument']['symbol'] for position in positions]

            # Fetch current market prices for all symbols
            quotes = {}
            if symbols:
                try:
                    quotes_response = client.quotes(symbols).json()
                    quotes = quotes_response if isinstance(quotes_response, dict) else {}
                except Exception as e:
                    print(f"Warning: Could not fetch quotes: {e}")

            # Display each position with P&L
            for position in positions:
                symbol = position['instrument']['symbol']
                quantity = position.get('longQuantity', 0) - position.get('shortQuantity', 0)
                average_price = position.get('averagePrice', 0.0)

                # Get current market price
                current_price = 0.0
                if symbol in quotes:
                    quote_data = quotes[symbol].get('quote', {}) if isinstance(quotes[symbol], dict) else {}
                    current_price = quote_data.get('lastPrice', 0.0) or quote_data.get('mark', 0.0)

                # Calculate P&L
                cost_basis = average_price * abs(quantity)
                current_value = current_price * abs(quantity)
                unrealized_pnl = current_value - cost_basis
                pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

                # Color coding for P&L
                pnl_color = '\033[92m' if unrealized_pnl >= 0 else '\033[91m'  # Green for profit, red for loss
                reset_color = '\033[0m'

                print(f"  {quantity} shares of {symbol} @ ${average_price:.2f} | {pnl_color}P&L: ${unrealized_pnl:+.2f} ({pnl_percent:+.2f}%){reset_color}")
                print("-" * 40)
                f.write(f"{symbol}\n")
        else:
            print("No positions available.")
            f.truncate(0)  # Clear the file if no positions


def display_watchlist_status():
    """Display simple watchlist status message."""
    watchlist_file = 'watchlist.txt'

    try:
        if not os.path.exists(watchlist_file) or os.path.getsize(watchlist_file) == 0:
            print("Watchlist is empty.")
            return

        with open(watchlist_file, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if not lines:
            print("Watchlist is empty.")
        else:
            items = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    symbol = parts[0].upper()
                    items.append(symbol)

            if items:
                print(f"Watchlist: {', '.join(items)}")
            else:
                print("Watchlist is empty.")

    except Exception as e:
        logger.error(f"Error reading watchlist: {e}")
        print("Watchlist is empty.")


def get_account_hash(client):
    """Get the account hash for order placement."""
    try:
        linked_accounts_response = client.account_linked().json()

        if isinstance(linked_accounts_response, dict):
            if 'error' in linked_accounts_response:
                logger.error(f"API Error getting account hash: {linked_accounts_response}")
                return None
            linked_accounts = linked_accounts_response.get('accounts', [linked_accounts_response])
        elif isinstance(linked_accounts_response, list):
            linked_accounts = linked_accounts_response
        else:
            logger.error(f"Unexpected response type: {type(linked_accounts_response)}")
            return None

        for account in linked_accounts:
            if isinstance(account, dict) and account.get('accountNumber') == account_nbr:
                return account.get('hashValue')

        logger.error("Account not found in linked accounts")
        return None
    except Exception as e:
        logger.error(f"Error getting account hash: {e}")
        return None


def create_limit_order(symbol, limit_price, quantity=1):
    """
    Create a limit order payload for Schwab API.

    Args:
        symbol: Stock ticker symbol
        limit_price: Limit price for the order
        quantity: Number of shares (default: 1)

    Returns:
        dict: Order payload for Schwab API
    """
    return {
        "orderType": "LIMIT",
        "session": "NORMAL",
        "duration": "GOOD_TILL_CANCEL",
        "orderStrategyType": "SINGLE",
        "price": str(limit_price),
        "orderLegCollection": [
            {
                "instruction": "BUY",
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": "EQUITY"
                }
            }
        ]
    }


def process_watchlist_orders(client, account_hash, watchlist_file_path):
    """
    Process watchlist.txt and place limit orders for each ticker.
    Format: TICKER LIMIT_PRICE (one per line)
    """
    try:
        if not os.path.exists(watchlist_file_path):
            logger.warning(f"Watchlist file not found: {watchlist_file_path}")
            return

        with open(watchlist_file_path, 'r') as f:
            lines = f.readlines()

        if not lines:
            logger.info("Watchlist is empty, no orders to place")
            return

        logger.info(f"Processing {len(lines)} ticker(s) from watchlist")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                parts = line.split()
                if len(parts) < 2:
                    logger.warning(f"Invalid line format: {line}")
                    continue

                symbol = parts[0].upper()
                limit_price = float(parts[1])

                logger.info(f"Placing limit order: {symbol} @ ${limit_price:.2f}")

                # Create order payload
                order_payload = create_limit_order(symbol, limit_price)

                # Place order
                response = client.order_place(account_hash, order_payload)

                if response.status_code in [200, 201]:
                    order_id = response.headers.get('Location', 'N/A')
                    logger.info(f"✓ Order placed successfully for {symbol} | Order ID: {order_id}")
                    print(f"\033[92m✓ Limit order placed: {symbol} @ ${limit_price:.2f}\033[0m")
                    sleep(3)  # Pause after order placement
                else:
                    logger.error(f"✗ Order failed for {symbol}: {response.status_code} - {response.text}")
                    print(f"\033[91m✗ Failed to place order for {symbol}: {response.status_code}\033[0m")
                    sleep(10)  # Pause after failed order

            except ValueError as e:
                logger.error(f"Invalid price format in line: {line} - {e}")
                print(f"\033[91m✗ Error: Invalid price format in line: {line}\033[0m")
                sleep(10)
            except Exception as e:
                logger.error(f"Error processing line '{line}': {e}")
                print(f"\033[91m✗ Error processing {symbol}: {e}\033[0m")
                sleep(10)

        # Clear watchlist after processing
        logger.info("Clearing watchlist after processing all orders")
        with open(watchlist_file_path, 'w') as f:
            f.truncate(0)

    except Exception as e:
        logger.error(f"Error processing watchlist: {e}")


def countdown_timer(seconds):
    while seconds > 0:
        print(f"\rRefreshing in {seconds} seconds...", end="")
        time.sleep(1)
        seconds -= 1


def clear_screen():
    # Clear the terminal screen
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


if __name__ == '__main__':
    main()
