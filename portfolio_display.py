import schwabdev
import mailreader
from env import app_key, app_secret, callback_url, account_nbr
from time import sleep
import os
import time
import sys


def main():
    client = schwabdev.Client(app_key, app_secret, callback_url)
    sleep(2)
    print("\n")

    # Fetch account details on startup
    print("Fetching initial account information...")
    fetch_account_details(client)

    last_scanner_file_mod_time = None
    scanner_file_path = 'scannerresults.txt'
    if os.path.exists(scanner_file_path):
        last_scanner_file_mod_time = os.path.getmtime(scanner_file_path)

    while True:
        # Check if scannerresults.txt has been modified
        if os.path.exists(scanner_file_path):
            current_mod_time = os.path.getmtime(scanner_file_path)
            if last_scanner_file_mod_time is None or current_mod_time != last_scanner_file_mod_time:
                last_scanner_file_mod_time = current_mod_time
                print("\nDetected changes in scannerresults.txt. Fetching latest information...")
                fetch_account_details(client)

        # Countdown timer for rechecking
        countdown_timer(60)


def fetch_account_details(client):
    # Clear the screen before displaying new information
    clear_screen()

    # Get linked accounts to retrieve account hash value
    linked_accounts = client.account_linked().json()
    #print(linked_accounts)

    # Find the account with matching account number and get the hash value
    account_hash = None
    for account in linked_accounts:
        if account.get('accountNumber') == account_nbr:
            account_hash = account.get('hashValue')
            break

    if account_hash is None:
        print("Account not found.")
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
