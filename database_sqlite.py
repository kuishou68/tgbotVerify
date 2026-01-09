"""SQLite database implementation.

Lightweight local storage without MySQL.
"""
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class SQLiteDatabase:
    """SQLite database helper."""

    def __init__(self):
        """Initialize the database connection."""
        db_path = os.getenv("SQLITE_PATH", "tgbot_verify.sqlite3")
        self.db_path = os.path.abspath(db_path)
        self._ensure_parent_dir()
        logger.info("SQLite database initialized: %s", self.db_path)
        self.init_database()

    def _ensure_parent_dir(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self) -> None:
        """Initialize database schema."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("PRAGMA journal_mode = WAL")

            # Users table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance INTEGER DEFAULT 1,
                    is_blocked INTEGER DEFAULT 0,
                    invited_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_checkin TEXT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_invited_by ON users(invited_by)"
            )

            # Invitations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inviter_id INTEGER NOT NULL,
                    invitee_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (inviter_id) REFERENCES users(user_id),
                    FOREIGN KEY (invitee_id) REFERENCES users(user_id)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_invitations_inviter ON invitations(inviter_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_invitations_invitee ON invitations(invitee_id)"
            )

            # Verifications table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    verification_type TEXT NOT NULL,
                    verification_url TEXT,
                    verification_id TEXT,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_verifications_user_id ON verifications(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_verifications_type ON verifications(verification_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_verifications_created ON verifications(created_at)"
            )

            # Card keys table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS card_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_code TEXT UNIQUE NOT NULL,
                    balance INTEGER NOT NULL,
                    max_uses INTEGER DEFAULT 1,
                    current_uses INTEGER DEFAULT 0,
                    expire_at TEXT NULL,
                    created_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_keys_code ON card_keys(key_code)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_keys_created_by ON card_keys(created_by)"
            )

            # Card key usage table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS card_key_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_code TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    used_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_key_usage_code ON card_key_usage(key_code)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_key_usage_user ON card_key_usage(user_id)"
            )

            conn.commit()
            logger.info("SQLite schema initialized")

        except Exception as e:
            logger.error("Failed to initialize database: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[Dict]:
        if row is None:
            return None
        result = dict(row)
        for key in ("created_at", "last_checkin", "expire_at", "used_at"):
            if result.get(key):
                try:
                    result[key] = datetime.fromisoformat(result[key]).isoformat()
                except ValueError:
                    pass
        return result

    def create_user(
        self, user_id: int, username: str, full_name: str, invited_by: Optional[int] = None
    ) -> bool:
        """Create a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, full_name, invited_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    full_name,
                    invited_by,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

            if invited_by:
                cursor.execute(
                    "UPDATE users SET balance = balance + 2 WHERE user_id = ?",
                    (invited_by,),
                )

                cursor.execute(
                    """
                    INSERT INTO invitations (inviter_id, invitee_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (invited_by, user_id, datetime.now().isoformat(timespec="seconds")),
                )

            conn.commit()
            return True

        except sqlite3.IntegrityError:
            conn.rollback()
            return False
        except Exception as e:
            logger.error("Failed to create user: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row)
        finally:
            cursor.close()
            conn.close()

    def user_exists(self, user_id: int) -> bool:
        """Check whether a user exists."""
        return self.get_user(user_id) is not None

    def is_user_blocked(self, user_id: int) -> bool:
        """Check whether a user is blocked."""
        user = self.get_user(user_id)
        return user and user["is_blocked"] == 1

    def block_user(self, user_id: int) -> bool:
        """Block a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to block user: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def unblock_user(self, user_id: int) -> bool:
        """Unblock a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to unblock user: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_blacklist(self) -> List[Dict]:
        """Get blocked users."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM users WHERE is_blocked = 1")
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    def add_balance(self, user_id: int, amount: int) -> bool:
        """Add balance to a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to add balance: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def deduct_balance(self, user_id: int, amount: int) -> bool:
        """Deduct balance from a user."""
        user = self.get_user(user_id)
        if not user or user["balance"] < amount:
            return False

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to deduct balance: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def can_checkin(self, user_id: int) -> bool:
        """Check whether the user can check in today."""
        user = self.get_user(user_id)
        if not user:
            return False

        last_checkin = user.get("last_checkin")
        if not last_checkin:
            return True

        last_date = datetime.fromisoformat(last_checkin).date()
        today = datetime.now().date()
        return last_date < today

    def checkin(self, user_id: int) -> bool:
        """Check in a user (single daily check-in)."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE users
                SET balance = balance + 1, last_checkin = ?
                WHERE user_id = ?
                AND (
                    last_checkin IS NULL
                    OR date(last_checkin) < date('now')
                )
                """,
                (datetime.now().isoformat(timespec="seconds"), user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error("Failed to check in: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def add_verification(
        self, user_id: int, verification_type: str, verification_url: str,
        status: str, result: str = "", verification_id: str = ""
    ) -> bool:
        """Add a verification record."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO verifications
                (user_id, verification_type, verification_url, verification_id, status, result, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    verification_type,
                    verification_url,
                    verification_id,
                    status,
                    result,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to add verification record: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def get_user_verifications(self, user_id: int) -> List[Dict]:
        """Get verification records for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM verifications
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    def create_card_key(
        self, key_code: str, balance: int, created_by: int,
        max_uses: int = 1, expire_days: Optional[int] = None
    ) -> bool:
        """Create a card key."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            expire_at = None
            if expire_days:
                expire_at = (datetime.now() + timedelta(days=expire_days)).isoformat(timespec="seconds")

            cursor.execute(
                """
                INSERT INTO card_keys (key_code, balance, max_uses, created_by, created_at, expire_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key_code,
                    balance,
                    max_uses,
                    created_by,
                    datetime.now().isoformat(timespec="seconds"),
                    expire_at,
                ),
            )
            conn.commit()
            return True

        except sqlite3.IntegrityError:
            logger.error("Card key already exists: %s", key_code)
            conn.rollback()
            return False
        except Exception as e:
            logger.error("Failed to create card key: %s", e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def use_card_key(self, key_code: str, user_id: int) -> Optional[int]:
        """Use a card key and return awarded balance."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM card_keys WHERE key_code = ?", (key_code,))
            card = self._row_to_dict(cursor.fetchone())

            if not card:
                return None

            expire_at = card.get("expire_at")
            if expire_at:
                if datetime.now() > datetime.fromisoformat(expire_at):
                    return -2

            if card["current_uses"] >= card["max_uses"]:
                return -1

            cursor.execute(
                "SELECT COUNT(*) as count FROM card_key_usage WHERE key_code = ? AND user_id = ?",
                (key_code, user_id),
            )
            count_row = cursor.fetchone()
            if count_row and count_row["count"] > 0:
                return -3

            cursor.execute(
                "UPDATE card_keys SET current_uses = current_uses + 1 WHERE key_code = ?",
                (key_code,),
            )
            cursor.execute(
                "INSERT INTO card_key_usage (key_code, user_id, used_at) VALUES (?, ?, ?)",
                (key_code, user_id, datetime.now().isoformat(timespec="seconds")),
            )
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (card["balance"], user_id),
            )

            conn.commit()
            return card["balance"]

        except Exception as e:
            logger.error("Failed to use card key: %s", e)
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()

    def get_card_key_info(self, key_code: str) -> Optional[Dict]:
        """Get card key info."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM card_keys WHERE key_code = ?", (key_code,))
            return self._row_to_dict(cursor.fetchone())
        finally:
            cursor.close()
            conn.close()

    def get_all_card_keys(self, created_by: Optional[int] = None) -> List[Dict]:
        """Get all card keys, optionally filtered by creator."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if created_by:
                cursor.execute(
                    "SELECT * FROM card_keys WHERE created_by = ? ORDER BY created_at DESC",
                    (created_by,),
                )
            else:
                cursor.execute("SELECT * FROM card_keys ORDER BY created_at DESC")

            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    def get_all_user_ids(self) -> List[int]:
        """Get all user IDs."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT user_id FROM users")
            rows = cursor.fetchall()
            return [row["user_id"] for row in rows]
        finally:
            cursor.close()
            conn.close()
