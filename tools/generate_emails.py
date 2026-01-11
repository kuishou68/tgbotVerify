"""Generate Outlook-style email credentials with short prefixes and lucky digits.

Usage:
    python tools/generate_emails.py            # default 10 accounts
    python tools/generate_emails.py --count 5  # custom count
"""
import argparse

from utils.email_generator import generate_accounts


def main():
    parser = argparse.ArgumentParser(description="Generate Outlook email/password pairs.")
    parser.add_argument("--count", type=int, default=10, help="number of accounts to generate (default: 10)")
    args = parser.parse_args()

    for idx, email, password in generate_accounts(args.count):
        print(f"{idx}. {email} | {password}")


if __name__ == "__main__":
    main()
