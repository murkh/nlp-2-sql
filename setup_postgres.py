"""
One-time setup script: creates the PostgreSQL 'text2sql' database.

Run this before starting the application:
    python setup_postgres.py
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys


def setup():
    # Try common connection strings for Docker PostgreSQL
    candidates = [
        "postgresql://postgres:postgres@localhost:5432/postgres",
        "postgresql://postgres@localhost:5432/postgres",
        "postgresql://localhost:5432/postgres",
    ]

    conn = None
    for conn_str in candidates:
        try:
            conn = psycopg2.connect(conn_str)
            print(f"✅ Connected to PostgreSQL via: {conn_str}")
            break
        except Exception as e:
            print(f"  ✗ {conn_str} → {e}")

    if conn is None:
        print("\n❌ Could not connect to PostgreSQL.")
        print("   Make sure your Docker container is running on localhost:5432")
        print("   Update POSTGRES_URL in .env if using different credentials.")
        sys.exit(1)

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname='text2sql'")
    if cur.fetchone():
        print("✅ Database 'text2sql' already exists")
    else:
        cur.execute("CREATE DATABASE text2sql")
        print("✅ Database 'text2sql' created successfully")

    cur.close()
    conn.close()

    # Now verify we can connect to the text2sql database
    try:
        test_url = conn_str.replace("/postgres", "/text2sql")
        test_conn = psycopg2.connect(test_url)
        test_conn.close()
        print(f"✅ Verified connection to text2sql database")
        print(f"\n   Set this in your .env if different:")
        print(f"   POSTGRES_URL={test_url}")
    except Exception as e:
        print(f"⚠️  Could not verify text2sql database: {e}")

    print("\n🎉 PostgreSQL setup complete! You can now run: python main.py")


if __name__ == "__main__":
    setup()
