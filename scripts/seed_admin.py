#!/usr/bin/env python3
"""
Seed an admin account in the FedVeil admins table.
Run once against RDS before starting the server for the first time:

    python scripts/seed_admin.py

Requires RDS_* environment variables to be set (same as the server).
"""
import getpass
from src.storage.db_connection import init_tables
from src.storage.admin_db import create_admin


def main():
    print("FedVeil — Create Admin Account")
    print("=" * 40)

    username = input("Username: ").strip()
    if not username:
        print("Error: username cannot be empty.")
        raise SystemExit(1)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Error: passwords do not match.")
        raise SystemExit(1)

    if len(password) < 8:
        print("Error: password must be at least 8 characters.")
        raise SystemExit(1)

    # Ensure tables exist before inserting
    init_tables()

    try:
        create_admin(username, password)
        print(f"\nAdmin '{username}' created successfully.")
    except ValueError as e:
        print(f"\nError: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
