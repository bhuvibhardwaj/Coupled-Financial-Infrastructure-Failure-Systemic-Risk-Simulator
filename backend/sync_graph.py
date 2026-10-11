"""Rebuild the Neo4j projection from the PostgreSQL source of truth."""

from backend.db import connect, fingerprint, load_network, lock_network, snapshot
from backend.graph import rebuild


def main():
    with connect() as conn:
        lock_network(conn)
        data = snapshot(*load_network(conn))
        rebuild(data, fingerprint(data))
    print("Neo4j graph is synced with PostgreSQL.")


if __name__ == "__main__":
    main()
