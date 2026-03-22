#!/usr/bin/env python3
"""
Initialize SQLite database with all 6 tables.
"""

import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "db/prototype.db")
REPO_ROOT = Path(__file__).parent.parent


def init_database():
    """Create database and initialize all tables."""

    # Ensure db directory exists
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing tables (for fresh start)
    cursor.execute("DROP TABLE IF EXISTS audit_log")
    cursor.execute("DROP TABLE IF EXISTS conversations")
    cursor.execute("DROP TABLE IF EXISTS vendor_assignments")
    cursor.execute("DROP TABLE IF EXISTS forecasts")
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS restaurants")

    # Create restaurants table
    cursor.execute("""
        CREATE TABLE restaurants (
            restaurant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cuisine TEXT,
            location TEXT,
            config JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create orders table
    cursor.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            restaurant_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            items JSON NOT NULL,
            total_cost FLOAT,
            status TEXT NOT NULL DEFAULT 'draft',
            vendors_assigned JSON,
            scheduled_send_time DATETIME,
            queued_at DATETIME,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
        )
    """)

    # Create forecasts table
    cursor.execute("""
        CREATE TABLE forecasts (
            forecast_id TEXT PRIMARY KEY,
            restaurant_id TEXT NOT NULL,
            date DATE NOT NULL,
            ingredients JSON NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
        )
    """)

    # Create vendor_assignments table
    cursor.execute("""
        CREATE TABLE vendor_assignments (
            assignment_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            vendor_id TEXT NOT NULL,
            items JSON NOT NULL,
            estimated_cost FLOAT,
            routing_reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    """)

    # Create conversations table
    cursor.execute("""
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
        )
    """)

    # Create audit_log table (no foreign keys — must survive orphaned records)
    cursor.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            restaurant_id TEXT,
            order_id TEXT,
            input_summary TEXT,
            output_summary TEXT,
            duration_ms INTEGER,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        )
    """)

    # Seed restaurants table from restaurant_profile.json
    restaurant_file = REPO_ROOT / "data" / "restaurant_profile.json"
    if restaurant_file.exists():
        with open(restaurant_file, "r") as f:
            restaurant = json.load(f)
            cursor.execute("""
                INSERT INTO restaurants (restaurant_id, name, cuisine, location, config)
                VALUES (?, ?, ?, ?, ?)
            """, (
                restaurant.get("restaurant_id"),
                restaurant.get("name"),
                restaurant.get("cuisine"),
                restaurant.get("location"),
                json.dumps(restaurant)
            ))

    conn.commit()
    conn.close()

    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_database()
