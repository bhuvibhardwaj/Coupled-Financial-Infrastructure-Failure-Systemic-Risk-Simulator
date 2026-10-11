"""Authenticated scenarios, saved results, paths, and buffer comparisons."""

import json
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field

from backend.auth import current_user
from backend.db import connect, fingerprint, load_network, lock_network, snapshot
from backend.graph import StaleGraphError, candidate_paths, load_edges
from backend.simulation import Bank, Dependency, Exposure, Result, simulate

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    failed_service_id: int = Field(gt=0)
    severity: int = Field(ge=0, le=100)


class ComparisonRequest(BaseModel):
    bank_id: int = Field(gt=0)
    extra_buffer: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


def owned_run(conn, run_id: int, user: dict):
    row = conn.execute(
        "SELECT r.id, r.scenario_id, r.baseline_run_id, r.input_snapshot, "
        "s.owner_id, s.failed_infrastructure_id, s.severity "
        "FROM simulation_runs r JOIN scenarios s ON s.id = r.scenario_id "
        "WHERE r.id = %s",
        (run_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Run not found")
    if user["role"] != "admin" and row["owner_id"] != user["id"]:
        raise HTTPException(403, "This run belongs to another user")
    return row


def save_result(
    conn, scenario_id: int, user_id: int, data: dict, result: Result,
    baseline_run_id: int | None = None, bank_id: int | None = None,
    extra_buffer: Decimal | None = None,
) -> int:
    service_name = next(
        s["name"] for s in data["network"]["services"]
        if s["id"] == data["failed_service_id"]
    )
    run = conn.execute(
        "INSERT INTO simulation_runs "
        "(scenario_id, created_by, risk_score, default_count, input_snapshot, "
        "baseline_run_id, mitigation_bank_id, extra_buffer, formula_version, "
        "failed_service_name) "
        "VALUES (%s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s, 1, %s) RETURNING id",
        (scenario_id, user_id, result.risk_score, result.default_count,
         json.dumps(data), baseline_run_id, bank_id, extra_buffer, service_name),
    ).fetchone()
    for impact in result.impacts:
        conn.execute(
            "INSERT INTO run_impacts "
            "(run_id, institution_id, first_affected_round, operational_loss, "
            "financial_loss, stress_pct, defaulted, propagation_path, bank_name_at_run) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, CAST(%s AS jsonb), %s)",
            (run["id"], impact.bank_id, impact.first_affected_round,
             impact.operational_loss, impact.financial_loss, impact.stress_pct,
             impact.defaulted, json.dumps(impact.propagation_path), impact.bank_name),
        )
    score = conn.execute(
        "SELECT calculate_systemic_risk(%s) AS score", (run["id"],)
    ).fetchone()["score"]
    conn.execute(
        "UPDATE simulation_runs SET risk_score = %s WHERE id = %s",
        (score, run["id"]),
    )
    return run["id"]


@router.get("")
def recent_runs(
    user: dict = Depends(current_user),
    q: str = Query(default="", max_length=100),
):
    with connect() as conn:
        return conn.execute(
            "SELECT run_id, created_at, scenario_name, failed_service, severity, "
            "risk_score, default_count, baseline_run_id, extra_buffer "
            "FROM v_run_summary "
            "WHERE (%s = 'admin' OR owner_id = %s) "
            "AND (%s = '' OR scenario_name ILIKE %s) "
            "ORDER BY created_at DESC, run_id DESC LIMIT 50",
            (user["role"], user["id"], q.strip(), f"%{q.strip()}%"),
        ).fetchall()


@router.get("/{run_id}")
def get_run(run_id: Annotated[int, Path(gt=0)], user: dict = Depends(current_user)):
    with connect() as conn:
        owned_run(conn, run_id, user)
        summary = conn.execute(
            "SELECT * FROM v_run_summary WHERE run_id = %s", (run_id,)
        ).fetchone()
        impacts = conn.execute(
            "SELECT i.id AS bank_id, COALESCE(r.bank_name_at_run, i.name) AS bank_name, "
            "r.first_affected_round, "
            "r.operational_loss, r.financial_loss, r.stress_pct, r.defaulted, "
            "r.propagation_path FROM run_impacts r "
            "JOIN institutions i ON i.id = r.institution_id "
            "WHERE r.run_id = %s "
            "ORDER BY r.first_affected_round NULLS LAST, i.id",
            (run_id,),
        ).fetchall()
        for impact in impacts:
            if isinstance(impact["propagation_path"], str):
                impact["propagation_path"] = json.loads(impact["propagation_path"])
        return {**summary, "impacts": impacts}


@router.post("", status_code=201)
def create_run(request: RunRequest, user: dict = Depends(current_user)):
    if not request.name.strip():
        raise HTTPException(422, "Scenario name cannot be blank")
    with connect() as conn:
        lock_network(conn)
        banks, services, sql_dependencies, sql_exposures = load_network(conn)
        service = next((s for s in services if s["id"] == request.failed_service_id), None)
        if service is None:
            raise HTTPException(404, "Service not found")
        data = snapshot(banks, services, sql_dependencies, sql_exposures)
        try:
            dependencies, exposures = load_edges(fingerprint(data))
        except StaleGraphError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Neo4jError as exc:
            raise HTTPException(503, "Neo4j is unavailable") from exc
        result = simulate(
            banks, dependencies, exposures, request.failed_service_id,
            request.severity, service["name"],
        )
        data_for_run = {
            "network": data,
            "failed_service_id": request.failed_service_id,
            "severity": request.severity,
            "formula_version": 1,
        }
        scenario = conn.execute(
            "INSERT INTO scenarios (name, failed_infrastructure_id, severity, owner_id) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (request.name.strip(), request.failed_service_id, request.severity, user["id"]),
        ).fetchone()
        run_id = save_result(conn, scenario["id"], user["id"], data_for_run, result)
        return {"run_id": run_id}


@router.post("/{run_id}/compare", status_code=201)
def compare_run(
    run_id: Annotated[int, Path(gt=0)], request: ComparisonRequest,
    user: dict = Depends(current_user),
):
    with connect() as conn:
        baseline = owned_run(conn, run_id, user)
        if baseline["baseline_run_id"] is not None:
            raise HTTPException(422, "Compare against an original run")
        saved = baseline["input_snapshot"]
        if isinstance(saved, str):
            saved = json.loads(saved)
        network = saved["network"]
        banks = [
            Bank(b["id"], b["name"], Decimal(b["buffer"]))
            for b in network["banks"]
        ]
        if request.bank_id not in {b.id for b in banks}:
            raise HTTPException(404, "Bank not found in this run")
        banks = [
            Bank(b.id, b.name, b.buffer + request.extra_buffer)
            if b.id == request.bank_id else b for b in banks
        ]
        dependencies = [
            Dependency(e["bank_id"], e["service_id"], Decimal(e["loss"]))
            for e in network["dependencies"]
        ]
        exposures = [
            Exposure(e["creditor_id"], e["debtor_id"], Decimal(e["amount"]),
                     Decimal(e["recovery_rate"])) for e in network["exposures"]
        ]
        service_name = next(
            s["name"] for s in network["services"]
            if s["id"] == saved["failed_service_id"]
        )
        result = simulate(
            banks, dependencies, exposures, saved["failed_service_id"],
            saved["severity"], service_name,
        )
        compared_snapshot = {
            **saved,
            "mitigation": {"bank_id": request.bank_id,
                           "extra_buffer": str(request.extra_buffer)},
        }
        compared_id = save_result(
            conn, baseline["scenario_id"], user["id"], compared_snapshot,
            result, baseline_run_id=run_id, bank_id=request.bank_id,
            extra_buffer=request.extra_buffer,
        )
        return {"run_id": compared_id, "baseline_run_id": run_id}


@router.get("/{run_id}/trace/{bank_id}")
def trace_run(
    run_id: Annotated[int, Path(gt=0)],
    bank_id: Annotated[int, Path(gt=0)],
    user: dict = Depends(current_user),
):
    with connect() as conn:
        run = owned_run(conn, run_id, user)
        row = conn.execute(
            "SELECT propagation_path FROM run_impacts "
            "WHERE run_id = %s AND institution_id = %s",
            (run_id, bank_id),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Bank not found in this run")
        saved = run["input_snapshot"]
        if isinstance(saved, str):
            saved = json.loads(saved)
        path = row["propagation_path"]
        if isinstance(path, str):
            path = json.loads(path)
        network = saved["network"]
        by_name = {b["name"]: b["id"] for b in network["banks"]}
        expected_ids = [by_name[name] for name in path[1:]] if path else []
        try:
            candidates = candidate_paths(
                saved["failed_service_id"], bank_id, fingerprint(network)
            )
            return {"path": path, "graph_current": True,
                    "verified_in_graph": expected_ids in candidates if path else False}
        except (StaleGraphError, Neo4jError):
            return {"path": path, "graph_current": False,
                    "verified_in_graph": None}
