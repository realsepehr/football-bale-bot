# -*- coding: utf-8 -*-
"""Move an existing SQLite database into Railway's persistent volume once.

The old deployment stored fantasy.db in /app, which is ephemeral. When the
persistent volume is introduced at /data, copy the old database only when the
new persistent database does not exist yet. Never overwrite an existing DB.
"""
import os
import shutil

SOURCE = "/app/fantasy.db"
TARGET = os.environ.get("DATABASE_PATH", "/data/fantasy.db")


def main():
    if os.path.exists(TARGET):
        print(f"Persistent database already exists: {TARGET}")
        return

    if not os.path.exists(SOURCE):
        print(f"No legacy database found at {SOURCE}; the application will initialize a new one.")
        return

    os.makedirs(os.path.dirname(TARGET) or ".", exist_ok=True)
    shutil.copy2(SOURCE, TARGET)
    print(f"Migrated legacy database: {SOURCE} -> {TARGET}")


if __name__ == "__main__":
    main()
