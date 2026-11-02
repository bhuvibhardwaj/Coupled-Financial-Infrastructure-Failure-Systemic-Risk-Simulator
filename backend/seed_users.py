"""Create custom accounts or reset the local demo logins."""

import argparse
from getpass import getpass

from backend.auth import hash_password
from backend.db import connect

DEMO_ACCOUNTS = (
    ("Demo Admin", "admin@example.com", "admin123", "admin"),
    ("Demo Analyst", "analyst@example.com", "analyst123", "analyst"),
)


def seed_defaults(reset: bool = False):
    with connect() as conn:
        if reset:
            # Keep identities referenced by saved scenarios, but revoke access.
            conn.execute("DELETE FROM user_sessions")
            conn.execute("UPDATE users SET active = false")
        for name, email, password, role in DEMO_ACCOUNTS:
            user = conn.execute(
                "INSERT INTO users (name, email, password_hash, role) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, "
                "password_hash = EXCLUDED.password_hash, role = EXCLUDED.role, active = true "
                "RETURNING id",
                (name, email, hash_password(password), role),
            ).fetchone()
            conn.execute("DELETE FROM user_sessions WHERE user_id = %s", (user["id"],))
    print("Local demo accounts ready: admin / admin123 and analyst / analyst123")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--defaults", action="store_true", help="Create the local demo accounts")
    parser.add_argument("--reset", action="store_true", help="Deactivate existing accounts and revoke sessions")
    args = parser.parse_args()
    if args.reset and not args.defaults:
        parser.error("--reset requires --defaults")
    if args.defaults:
        seed_defaults(reset=args.reset)
        return
    for role in ("admin", "analyst"):
        name = input(f"{role.title()} display name: ").strip()
        email = input(f"{role.title()} email: ").strip().lower()
        password = getpass(f"{role.title()} password (8+ characters): ")
        if not name or "@" not in email:
            raise ValueError("A name and valid-looking email are required")
        encoded = hash_password(password)
        with connect() as conn:
            conn.execute(
                "INSERT INTO users (name, email, password_hash, role) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, "
                "password_hash = EXCLUDED.password_hash, role = EXCLUDED.role, active = true",
                (name, email, encoded, role),
            )
    print("Admin and Analyst accounts are ready.")


if __name__ == "__main__":
    main()
