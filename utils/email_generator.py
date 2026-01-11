"""Generate Outlook-style email credentials with short prefixes and lucky digits."""
import random
import string
from typing import Generator, Tuple

from faker import Faker

fake = Faker()


def _build_username() -> str:
    """Build a short username and append lucky digits (6/8)."""
    first = fake.first_name().lower()
    last = fake.last_name().lower()
    base = "".join(ch for ch in (first[:4] + last[:4]) if ch.isalpha())
    if len(base) < 4:
        base += "".join(random.choice(string.ascii_lowercase) for _ in range(4 - len(base)))

    digits = ["6", "8", "6"]
    random.shuffle(digits)
    return f"{base}{''.join(digits)}"


def _build_password(length: int = 12) -> str:
    """Generate a complex password with upper/lower/digit/special."""
    specials = "@#$%&*+!"
    alphabet = string.ascii_letters + string.digits + specials

    while True:
        pw = "".join(random.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in specials for c in pw)
        ):
            return pw


def generate_accounts(count: int) -> Generator[Tuple[int, str, str], None, None]:
    """Yield (index, email, password) tuples."""
    for idx in range(1, count + 1):
        username = _build_username()
        password = _build_password()
        yield idx, f"{username}@outlook.com", password
