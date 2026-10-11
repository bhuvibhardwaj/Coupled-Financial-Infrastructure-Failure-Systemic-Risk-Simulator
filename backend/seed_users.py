"""Interactively create the two course-demo accounts without storing passwords."""

from getpass import getpass

from backend.auth import hash_password
from backend.db import connect


def main():
    for role in ("admin", "analyst"):
        name = input(f"{role.title()} display name: ").strip()
        email = input(f"{role.title()} email: ").strip().lower()
        password = getpass(f"{role.title()} password (12+ characters): ")
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
