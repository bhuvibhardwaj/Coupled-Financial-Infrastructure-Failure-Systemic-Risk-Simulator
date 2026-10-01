"""PostgreSQL access and the canonical network snapshot."""

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pg8000.dbapi
from dotenv import load_dotenv

from backend.simulation import Bank, Dependency, Exposure

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class QueryResult:
    def __init__(self, cursor):
        self.cursor = cursor

    def _as_dict(self, row):
        if row is None:
            return None
        return dict(zip((col[0] for col in self.cursor.description), row))

    def fetchone(self):
        return self._as_dict(self.cursor.fetchone())

    def fetchall(self):
        return [self._as_dict(row) for row in self.cursor.fetchall()]


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params=()):
        cursor = self.raw.cursor()
        cursor.execute(sql, params)
        return QueryResult(cursor)


@contextmanager
def connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise RuntimeError("DATABASE_URL must use a PostgreSQL URL")
    raw = pg8000.dbapi.connect(
        host=parts.hostname or "localhost",
        port=parts.port or 5432,
        database=parts.path.lstrip("/"),
        user=unquote(parts.username or ""),
        password=unquote(parts.password or ""),
    )
    try:
        yield Connection(raw)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def load_network(conn) -> tuple[list[Bank], list[dict], list[Dependency], list[Exposure]]:
    bank_rows = conn.execute(
        "SELECT id, name, liquidity_buffer FROM institutions ORDER BY id"
    ).fetchall()
    services = conn.execute(
        "SELECT id, name, category FROM infrastructure ORDER BY id"
    ).fetchall()
    dependency_rows = conn.execute(
        "SELECT institution_id, infrastructure_id, loss_at_full_failure "
        "FROM dependencies ORDER BY institution_id, infrastructure_id"
    ).fetchall()
    exposure_rows = conn.execute(
        "SELECT creditor_id, debtor_id, amount, recovery_rate "
        "FROM exposures ORDER BY creditor_id, debtor_id"
    ).fetchall()
    banks = [Bank(r["id"], r["name"], r["liquidity_buffer"]) for r in bank_rows]
    dependencies = [
        Dependency(r["institution_id"], r["infrastructure_id"], r["loss_at_full_failure"])
        for r in dependency_rows
    ]
    exposures = [
        Exposure(r["creditor_id"], r["debtor_id"], r["amount"], r["recovery_rate"])
        for r in exposure_rows
    ]
    return banks, services, dependencies, exposures


def snapshot(banks, services, dependencies, exposures) -> dict:
    return {
        "banks": [
            {"id": b.id, "name": b.name, "buffer": str(b.buffer)} for b in banks
        ],
        "services": services,
        "dependencies": [
            {"bank_id": d.bank_id, "service_id": d.service_id,
             "loss": str(d.loss_at_full_failure)} for d in dependencies
        ],
        "exposures": [
            {"creditor_id": e.creditor_id, "debtor_id": e.debtor_id,
             "amount": str(e.amount), "recovery_rate": str(e.recovery_rate)}
            for e in exposures
        ],
    }


def fingerprint(data: dict) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
