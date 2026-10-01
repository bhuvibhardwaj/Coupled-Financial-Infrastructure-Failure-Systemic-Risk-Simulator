"""Create tables and load a fictional demonstration network."""

from pathlib import Path

from backend.db import connect

ROOT = Path(__file__).resolve().parents[1]


def main():
    with connect() as conn:
        for name in ("schema.sql", "seed.sql"):
            source = (ROOT / "sql" / name).read_text(encoding="utf-8")
            for statement in source.split(";"):
                if statement.strip():
                    conn.execute(statement)
    print("PostgreSQL schema and seed data are ready.")


if __name__ == "__main__":
    main()
