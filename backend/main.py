"""FastAPI endpoints for the first complete simulation flow."""

import json
from typing import Annotated

import pg8000.dbapi
from fastapi import FastAPI, HTTPException, Path
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field

from backend.db import connect, fingerprint, load_network, snapshot
from backend.graph import StaleGraphError, load_edges
from backend.simulation import simulate

app = FastAPI(title="Systemic Risk Simulator API")


class RunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    failed_service_id: int = Field(gt=0)
    severity: int = Field(ge=0, le=100)


@app.get("/api/services")
def services():
    try:
        with connect() as conn:
            return conn.execute(
                "SELECT id, name, category FROM infrastructure ORDER BY id"
            ).fetchall()
    except (pg8000.dbapi.InterfaceError, OSError) as exc:
        raise HTTPException(503, "PostgreSQL is unavailable") from exc


@app.get("/api/runs")
def recent_runs():
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT run_id, created_at, scenario_name, failed_service, "
                "severity, risk_score, default_count "
                "FROM v_run_summary ORDER BY created_at DESC, run_id DESC LIMIT 10"
            ).fetchall()
            return rows
    except (pg8000.dbapi.InterfaceError, OSError) as exc:
        raise HTTPException(503, "PostgreSQL is unavailable") from exc


@app.get("/api/runs/{run_id}")
def get_run(run_id: Annotated[int, Path(gt=0)]):
    try:
        with connect() as conn:
            summary = conn.execute(
                "SELECT * FROM v_run_summary WHERE run_id = %s", (run_id,)
            ).fetchone()
            if summary is None:
                raise HTTPException(404, "Run not found")
            impacts = conn.execute(
                "SELECT i.name AS bank_name, r.first_affected_round, "
                "r.operational_loss, r.financial_loss, r.stress_pct, r.defaulted "
                "FROM run_impacts r JOIN institutions i ON i.id = r.institution_id "
                "WHERE r.run_id = %s ORDER BY r.first_affected_round NULLS LAST, i.id",
                (run_id,),
            ).fetchall()
            return {**summary, "impacts": impacts}
    except (pg8000.dbapi.InterfaceError, OSError) as exc:
        raise HTTPException(503, "PostgreSQL is unavailable") from exc


@app.post("/api/runs", status_code=201)
def create_run(request: RunRequest):
    if not request.name.strip():
        raise HTTPException(422, "Scenario name cannot be blank")
    try:
        with connect() as conn:
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
                request.severity,
            )
            input_snapshot = {
                "network": data,
                "failed_service_id": request.failed_service_id,
                "severity": request.severity,
                "formula_version": 1,
            }
            scenario = conn.execute(
                "INSERT INTO scenarios (name, failed_infrastructure_id, severity) "
                "VALUES (%s, %s, %s) RETURNING id",
                (request.name.strip(), request.failed_service_id, request.severity),
            ).fetchone()
            run = conn.execute(
                "INSERT INTO simulation_runs "
                "(scenario_id, risk_score, default_count, input_snapshot) "
                "VALUES (%s, %s, %s, CAST(%s AS jsonb)) RETURNING id",
                (scenario["id"], result.risk_score, result.default_count,
                 json.dumps(input_snapshot)),
            ).fetchone()
            for impact in result.impacts:
                conn.execute(
                    "INSERT INTO run_impacts "
                    "(run_id, institution_id, first_affected_round, "
                    "operational_loss, financial_loss, stress_pct, defaulted) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (run["id"], impact.bank_id, impact.first_affected_round,
                     impact.operational_loss, impact.financial_loss,
                     impact.stress_pct, impact.defaulted),
                )
            return {"run_id": run["id"]}
    except (pg8000.dbapi.InterfaceError, OSError) as exc:
        raise HTTPException(503, "PostgreSQL is unavailable") from exc
