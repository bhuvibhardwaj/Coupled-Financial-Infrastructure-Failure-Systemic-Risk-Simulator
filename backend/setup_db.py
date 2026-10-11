"""Create tables and load a fictional demonstration network."""

from pathlib import Path
import re

from backend.db import connect

ROOT = Path(__file__).resolve().parents[1]


def split_sql(source: str) -> list[str]:
    """Split our schema script without breaking quoted function bodies."""
    statements: list[str] = []
    start = 0
    i = 0
    quote = False
    dollar = None
    while i < len(source):
        if dollar:
            if source.startswith(dollar, i):
                i += len(dollar)
                dollar = None
                continue
        elif quote:
            if source.startswith("''", i):
                i += 2
                continue
            if source[i] == "'":
                quote = False
        elif source.startswith("--", i):
            end = source.find("\n", i)
            i = len(source) if end < 0 else end + 1
            continue
        elif source[i] == "'":
            quote = True
        elif source[i] == "$":
            match = re.match(r"\$[A-Za-z_0-9]*\$", source[i:])
            if match:
                dollar = match.group()
                i += len(dollar)
                continue
        elif source[i] == ";":
            if source[start:i].strip():
                statements.append(source[start:i].strip())
            start = i + 1
        i += 1
    if source[start:].strip():
        statements.append(source[start:].strip())
    return statements


def main():
    with connect() as conn:
        for name in ("schema.sql", "seed.sql"):
            source = (ROOT / "sql" / name).read_text(encoding="utf-8")
            for statement in split_sql(source):
                conn.execute(statement)
    print("PostgreSQL schema and seed data are ready.")


if __name__ == "__main__":
    main()
