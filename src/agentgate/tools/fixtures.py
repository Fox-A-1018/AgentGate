from __future__ import annotations

import sqlite3
from pathlib import Path


def initialize_business_database(path: str | Path) -> Path:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                stock INTEGER NOT NULL,
                category TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users_public (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                department TEXT NOT NULL
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO inventory(sku, name, stock, category) VALUES (?, ?, ?, ?)",
                [
                    ("SKU-001", "Demo keyboard", 20, "peripheral"),
                    ("SKU-002", "Demo mouse", 35, "peripheral"),
                    ("SKU-003", "Demo security key", 12, "security"),
                ],
            )
        if connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO orders(order_id, sku, quantity, status) VALUES (?, ?, ?, ?)",
                [
                    ("ORD-001", "SKU-001", 2, "created"),
                    ("ORD-002", "SKU-003", 1, "shipped"),
                ],
            )
        if connection.execute("SELECT COUNT(*) FROM users_public").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO users_public(user_id, display_name, department) VALUES (?, ?, ?)",
                [
                    ("U-001", "Demo Analyst", "security"),
                    ("U-002", "Demo Operator", "operations"),
                ],
            )
    return database_path

