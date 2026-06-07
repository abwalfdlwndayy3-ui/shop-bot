import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            wallet      INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS configs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            server_type     TEXT NOT NULL,
            package_label   TEXT NOT NULL,
            traffic_total   INTEGER NOT NULL,
            traffic_used    INTEGER DEFAULT 0,
            expiry_date     TEXT NOT NULL,
            config_text     TEXT DEFAULT '',
            status          TEXT DEFAULT 'pending',
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            server_type     TEXT NOT NULL,
            package_label   TEXT NOT NULL,
            amount          INTEGER NOT NULL,
            status          TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS wallet_tx (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            amount          INTEGER NOT NULL,
            tx_type         TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)
    conn.commit()
    conn.close()


def ensure_user(user_id: int, username: str | None, first_name: str | None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO users (user_id, username, first_name)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
             username   = excluded.username,
             first_name = excluded.first_name""",
        (user_id, username or "", first_name or ""),
    )
    conn.commit()
    conn.close()


def get_user(user_id: int) -> sqlite3.Row | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def get_wallet(user_id: int) -> int:
    user = get_user(user_id)
    return user["wallet"] if user else 0


def add_wallet(user_id: int, amount: int):
    conn = get_conn()
    conn.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def deduct_wallet(user_id: int, amount: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row or row["wallet"] < amount:
        conn.close()
        return False
    conn.execute("UPDATE users SET wallet = wallet - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return True


def create_order(user_id: int, server_type: str, package_label: str, amount: int, receipt_file_id: str | None = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO orders (user_id, server_type, package_label, amount, receipt_file_id) VALUES (?, ?, ?, ?, ?)",
        (user_id, server_type, package_label, amount, receipt_file_id),
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def update_order_status(order_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def create_wallet_tx(user_id: int, amount: int, tx_type: str, receipt_file_id: str | None = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO wallet_tx (user_id, amount, tx_type, receipt_file_id) VALUES (?, ?, ?, ?)",
        (user_id, amount, tx_type, receipt_file_id),
    )
    tx_id = cur.lastrowid
    conn.commit()
    conn.close()
    return tx_id


def confirm_wallet_tx(tx_id: int) -> tuple[int, int] | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM wallet_tx WHERE id = ?", (tx_id,)).fetchone()
    if not row or row["status"] != "pending":
        conn.close()
        return None
    conn.execute("UPDATE wallet_tx SET status = 'confirmed' WHERE id = ?", (tx_id,))
    conn.execute("UPDATE users SET wallet = wallet + ? WHERE user_id = ?", (row["amount"], row["user_id"]))
    conn.commit()
    conn.close()
    return (row["user_id"], row["amount"])


def add_config(user_id: int, server_type: str, package_label: str, traffic_total: int, days: int, config_text: str = "") -> int:
    from datetime import date, timedelta
    expiry = (date.today() + timedelta(days=days)).isoformat()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO configs (user_id, server_type, package_label, traffic_total, expiry_date, config_text, status)
           VALUES (?, ?, ?, ?, ?, ?, 'active')""",
        (user_id, server_type, package_label, traffic_total, expiry, config_text),
    )
    config_id = cur.lastrowid
    conn.commit()
    conn.close()
    return config_id


def get_user_configs(user_id: int) -> list[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM configs WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_config(config_id: int) -> sqlite3.Row | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM configs WHERE id = ?", (config_id,)).fetchone()
    conn.close()
    return row


def get_pending_orders() -> list[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at").fetchall()
    conn.close()
    return rows
  
