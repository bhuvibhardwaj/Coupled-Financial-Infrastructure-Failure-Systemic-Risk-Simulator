"""Network management, Cypher analysis, and administrator audit views."""

from decimal import Decimal
from typing import Annotated

import pg8000.dbapi
from fastapi import APIRouter, Depends, HTTPException, Path
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field

from backend.auth import admin_user, current_user
from backend.db import connect, fingerprint, load_network, lock_network, snapshot
from backend.graph import StaleGraphError, network_analysis, rebuild

router = APIRouter(prefix="/api", tags=["network"])


class BankInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    liquidity_buffer: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class ServiceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=80)


class DependencyInput(BaseModel):
    institution_id: int = Field(gt=0)
    infrastructure_id: int = Field(gt=0)
    loss_at_full_failure: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class ExposureInput(BaseModel):
    creditor_id: int = Field(gt=0)
    debtor_id: int = Field(gt=0)
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    recovery_rate: Decimal = Field(ge=0, le=1, max_digits=4, decimal_places=3)


def actor_context(conn, user: dict):
    lock_network(conn)
    conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user["id"]),))


def clean(value: str) -> str:
    text = value.strip()
    if not text:
        raise HTTPException(422, "Name/category cannot be blank")
    return text


def database_conflict(exc):
    raise HTTPException(409, "Record conflicts with existing network data or saved runs") from exc


@router.get("/services")
def services(user: dict = Depends(current_user)):
    with connect() as conn:
        return conn.execute(
            "SELECT id, name, category FROM infrastructure ORDER BY id"
        ).fetchall()


@router.get("/network")
def get_network(user: dict = Depends(current_user)):
    with connect() as conn:
        lock_network(conn)
        banks, services, dependencies, exposures = load_network(conn)
        data = snapshot(banks, services, dependencies, exposures)
        try:
            analysis = network_analysis(fingerprint(data))
            graph_current = True
        except (StaleGraphError, Neo4jError):
            analysis = {"service_ranking": [], "bank_ranking": []}
            graph_current = False
    return {**data, **analysis, "graph_current": graph_current}


@router.post("/admin/network/rebuild")
def rebuild_network(user: dict = Depends(admin_user)):
    with connect() as conn:
        lock_network(conn)
        data = snapshot(*load_network(conn))
        try:
            rebuild(data, fingerprint(data))
        except Neo4jError as exc:
            raise HTTPException(503, "Neo4j is unavailable") from exc
    return {"graph_current": True, "banks": len(data["banks"]),
            "services": len(data["services"])}


@router.get("/admin/audit")
def audit_log(user: dict = Depends(admin_user)):
    with connect() as conn:
        return conn.execute(
            "SELECT a.id, a.changed_at, a.table_name, a.action, a.record_id, "
            "u.name AS actor_name FROM audit_logs a "
            "LEFT JOIN users u ON u.id = a.actor_id "
            "ORDER BY a.changed_at DESC, a.id DESC LIMIT 50"
        ).fetchall()


@router.post("/admin/banks", status_code=201)
def add_bank(body: BankInput, user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            actor_context(conn, user)
            return conn.execute(
                "INSERT INTO institutions (name, liquidity_buffer) VALUES (%s, %s) "
                "RETURNING id, name, liquidity_buffer",
                (clean(body.name), body.liquidity_buffer),
            ).fetchone()
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.put("/admin/banks/{bank_id}")
def edit_bank(bank_id: Annotated[int, Path(gt=0)], body: BankInput,
              user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            actor_context(conn, user)
            row = conn.execute(
                "UPDATE institutions SET name = %s, liquidity_buffer = %s "
                "WHERE id = %s RETURNING id, name, liquidity_buffer",
                (clean(body.name), body.liquidity_buffer, bank_id),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Bank not found")
            return row
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.delete("/admin/banks/{bank_id}")
def delete_bank(bank_id: Annotated[int, Path(gt=0)], user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            actor_context(conn, user)
            row = conn.execute(
                "DELETE FROM institutions WHERE id = %s RETURNING id", (bank_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Bank not found")
            return {"deleted": row["id"]}
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.post("/admin/services", status_code=201)
def add_service(body: ServiceInput, user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            actor_context(conn, user)
            return conn.execute(
                "INSERT INTO infrastructure (name, category) VALUES (%s, %s) "
                "RETURNING id, name, category",
                (clean(body.name), clean(body.category)),
            ).fetchone()
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.put("/admin/services/{service_id}")
def edit_service(service_id: Annotated[int, Path(gt=0)], body: ServiceInput,
                 user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            actor_context(conn, user)
            row = conn.execute(
                "UPDATE infrastructure SET name = %s, category = %s "
                "WHERE id = %s RETURNING id, name, category",
                (clean(body.name), clean(body.category), service_id),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Service not found")
            return row
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.delete("/admin/services/{service_id}")
def delete_service(service_id: Annotated[int, Path(gt=0)],
                   user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            actor_context(conn, user)
            row = conn.execute(
                "DELETE FROM infrastructure WHERE id = %s RETURNING id", (service_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Service not found")
            return {"deleted": row["id"]}
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.post("/admin/dependencies", status_code=201)
def add_dependency(body: DependencyInput, user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            lock_network(conn)
            conn.execute(
                "INSERT INTO dependencies "
                "(institution_id, infrastructure_id, loss_at_full_failure) "
                "VALUES (%s, %s, %s)",
                (body.institution_id, body.infrastructure_id,
                 body.loss_at_full_failure),
            )
            return body
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.put("/admin/dependencies/{bank_id}/{service_id}")
def edit_dependency(bank_id: int, service_id: int, body: DependencyInput,
                    user: dict = Depends(admin_user)):
    if (body.institution_id, body.infrastructure_id) != (bank_id, service_id):
        raise HTTPException(422, "Relationship endpoints cannot be changed")
    with connect() as conn:
        lock_network(conn)
        row = conn.execute(
            "UPDATE dependencies SET loss_at_full_failure = %s "
            "WHERE institution_id = %s AND infrastructure_id = %s "
            "RETURNING institution_id",
            (body.loss_at_full_failure, bank_id, service_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Dependency not found")
        return body


@router.delete("/admin/dependencies/{bank_id}/{service_id}")
def delete_dependency(bank_id: int, service_id: int,
                      user: dict = Depends(admin_user)):
    with connect() as conn:
        lock_network(conn)
        row = conn.execute(
            "DELETE FROM dependencies WHERE institution_id = %s "
            "AND infrastructure_id = %s RETURNING institution_id",
            (bank_id, service_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Dependency not found")
        return {"deleted": True}


@router.post("/admin/exposures", status_code=201)
def add_exposure(body: ExposureInput, user: dict = Depends(admin_user)):
    try:
        with connect() as conn:
            lock_network(conn)
            conn.execute(
                "INSERT INTO exposures "
                "(creditor_id, debtor_id, amount, recovery_rate) "
                "VALUES (%s, %s, %s, %s)",
                (body.creditor_id, body.debtor_id,
                 body.amount, body.recovery_rate),
            )
            return body
    except pg8000.dbapi.DatabaseError as exc:
        database_conflict(exc)


@router.put("/admin/exposures/{creditor_id}/{debtor_id}")
def edit_exposure(creditor_id: int, debtor_id: int, body: ExposureInput,
                  user: dict = Depends(admin_user)):
    if (body.creditor_id, body.debtor_id) != (creditor_id, debtor_id):
        raise HTTPException(422, "Relationship endpoints cannot be changed")
    with connect() as conn:
        lock_network(conn)
        row = conn.execute(
            "UPDATE exposures SET amount = %s, recovery_rate = %s "
            "WHERE creditor_id = %s AND debtor_id = %s RETURNING creditor_id",
            (body.amount, body.recovery_rate, creditor_id, debtor_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Exposure not found")
        return body


@router.delete("/admin/exposures/{creditor_id}/{debtor_id}")
def delete_exposure(creditor_id: int, debtor_id: int,
                    user: dict = Depends(admin_user)):
    with connect() as conn:
        lock_network(conn)
        row = conn.execute(
            "DELETE FROM exposures WHERE creditor_id = %s AND debtor_id = %s "
            "RETURNING creditor_id",
            (creditor_id, debtor_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Exposure not found")
        return {"deleted": True}
