import os
import time
import re
import platform
import socket
from datetime import datetime, timedelta
from env import mail_username, mail_password
from imap_tools import MailBox, AND

def extract_ticker_symbols(text):
    """Extract ticker symbols from the text using regex pattern.
    Only extracts symbols from emails containing 'BBAuto' or 'BBAUTO'.
    """
    # Check for BBAuto (case-insensitive)
    if 'bbauto' not in text.lower():
        return []

    ticker_pattern = r'\b[A-Z]{1,5}\b'
    tickers = re.findall(ticker_pattern, text)

    # Filter out common words that aren't ticker symbols
    excluded_words = {'ALERT', 'NEW', 'SYMBOL', 'WAS', 'ADDED', 'TO', 'BBAUTO', 'FROM', 'THE', 'IN', 'AT', 'ON', 'BY', 'FOR', 'WITH'}
    return [ticker for ticker in tickers if ticker not in excluded_words]

def overwrite_results_file(tickers):
    """Append unique tickers to scanner.txt without overwriting existing ones."""
    # Use absolute path for Linux compatibility
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "scanner.txt")

    # Load existing tickers from the file
    existing_tickers = set()
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            existing_tickers = set(line.strip() for line in file.readlines())

    # Update tickers with any new tickers from this run
    updated_tickers = existing_tickers.union(tickers)

    # Write all unique tickers to the file
    try:
        with open(file_path, "w") as file:
            for ticker in updated_tickers:
                file.write(ticker + "\n")
    except Exception as e:
        print(f"Error updating results file: {e}")

def clear_screen():
    """Clear the console screen based on the operating system."""
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')

def countdown_timer(seconds):
    """Display a countdown timer showing seconds until next check."""
    while seconds > 0:
        print(f"\rChecking in {seconds} seconds...", end="", flush=True)
        time.sleep(1)
        seconds -= 1
    print("\r" + " " * 40 + "\r", end="")  # Clear the countdown line

def mailbox_reader():
    loop_count = 0

    while True:
        loop_count += 1
        start_time = time.time()

        try:
            print(f"\n[DEBUG] Loop #{loop_count} - Starting email check at {time.strftime('%H:%M:%S')}")

            # Set socket timeout to prevent hanging
            socket.setdefaulttimeout(10)
            print("[DEBUG] Socket timeout set to 10 seconds")

            # Login to mailbox
            print("[DEBUG] Attempting to connect to imap.gmail.com...")
            connect_start = time.time()

            with MailBox("imap.gmail.com").login(mail_username, mail_password, "INBOX") as mb:
                connect_time = time.time() - connect_start
                print(f"[DEBUG] ✓ Connected successfully in {connect_time:.2f}s")

                # Calculate date for last 24 hours
                yesterday = datetime.now().date() - timedelta(days=1)
                print(f"[DEBUG] Filtering emails since: {yesterday}")

                # Fetch ONLY BBAuto emails from last 24 hours - MUCH faster!
                print("[DEBUG] Fetching BBAuto emails from last 24 hours...")
                fetch_start = time.time()

                # Generator approach - processes emails one at a time without loading all into memory
                # IMPROVED: Filter by date and subject at IMAP level for maximum speed
                bbauto_found = False
                email_count = 0
                bbauto_count = 0

                for msg in mb.fetch(
                    criteria=AND(
                        seen=False,
                        from_='alerts@thinkorswim.com',
                        date_gte=yesterday,
                        subject='BBAuto'  # Only fetch emails with BBAuto in subject
                    ),
                    mark_seen=False
                ):
                    email_count += 1
                    bbauto_count += 1
                    print(f"[DEBUG] Processing BBAuto email #{email_count}: '{msg.subject[:50]}...'")

                    # Extract ticker symbols from both subject and body
                    extract_start = time.time()
                    full_content = f"{msg.subject} {msg.text}"
                    tickers = extract_ticker_symbols(full_content)
                    extract_time = time.time() - extract_start

                    print(f"[DEBUG] Ticker extraction took {extract_time:.2f}s")

                    if tickers:
                        print(f"[DEBUG] Found tickers: {', '.join(tickers)}")
                        overwrite_results_file(tickers)
                        print(f"✓ Signal received: Ticker(s) {', '.join(tickers)}")
                        bbauto_found = True
                    else:
                        print("[DEBUG] No valid tickers extracted from email")

                    # Mark BBAuto email as seen and move to trash
                    print(f"[DEBUG] Marking email as seen and moving to trash...")
                    mb.flag(msg.uid, ['\\Seen'], True)
                    mb.move(msg.uid, '[Gmail]/Trash')
                    print(f"[DEBUG] ✓ Email processed and moved to trash")

                fetch_time = time.time() - fetch_start
                print(f"[DEBUG] Fetch completed in {fetch_time:.2f}s - Processed {email_count} emails ({bbauto_count} BBAuto)")

                # Show waiting message if no BBAuto emails were processed
                if not bbauto_found:
                    clear_screen()
                    print("Waiting for scanner results...")

            total_time = time.time() - start_time
            print(f"[DEBUG] Total loop time: {total_time:.2f}s")

            # Countdown timer before next check
            countdown_timer(30)  # 30 second interval

        except socket.timeout:
            elapsed = time.time() - start_time
            print(f"[ERROR] Socket timeout after {elapsed:.2f}s - Connection took too long")
            time.sleep(10)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ERROR] Error occurred after {elapsed:.2f}s: {e}")
            print(f"[ERROR] Error type: {type(e).__name__}")
            time.sleep(10)  # Briefly wait before retrying

if __name__ == "__main__":
    mailbox_reader()
