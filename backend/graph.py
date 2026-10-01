"""Neo4j graph rebuild and simulation edge retrieval."""

import os

from neo4j import GraphDatabase

from backend.simulation import Dependency, Exposure


class StaleGraphError(RuntimeError):
    pass


def driver():
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not all((uri, user, password)):
        raise RuntimeError("Neo4j connection is not configured")
    return GraphDatabase.driver(uri, auth=(user, password))


def rebuild(data: dict, version: str) -> None:
    """Replace only this project's labelled graph, atomically in Neo4j."""
    with driver() as db:
        with db.session() as session:
            session.run(
                "CREATE CONSTRAINT risk_bank_id IF NOT EXISTS "
                "FOR (n:RiskInstitution) REQUIRE n.id IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT risk_service_id IF NOT EXISTS "
                "FOR (n:RiskInfrastructure) REQUIRE n.id IS UNIQUE"
            ).consume()

            def write(tx):
                tx.run(
                    "MATCH (n) WHERE n:RiskInstitution OR n:RiskInfrastructure "
                    "OR n:RiskNetworkVersion DETACH DELETE n"
                ).consume()
                tx.run(
                    "UNWIND $rows AS row "
                    "CREATE (:RiskInstitution {id: row.id, name: row.name})",
                    rows=data["banks"],
                ).consume()
                tx.run(
                    "UNWIND $rows AS row "
                    "CREATE (:RiskInfrastructure {id: row.id, name: row.name})",
                    rows=data["services"],
                ).consume()
                tx.run(
                    "UNWIND $rows AS row "
                    "MATCH (b:RiskInstitution {id: row.bank_id}) "
                    "MATCH (s:RiskInfrastructure {id: row.service_id}) "
                    "CREATE (b)-[:DEPENDS_ON {loss: row.loss}]->(s)",
                    rows=data["dependencies"],
                ).consume()
                tx.run(
                    "UNWIND $rows AS row "
                    "MATCH (c:RiskInstitution {id: row.creditor_id}) "
                    "MATCH (d:RiskInstitution {id: row.debtor_id}) "
                    "CREATE (c)-[:EXPOSED_TO {amount: row.amount, "
                    "recovery_rate: row.recovery_rate}]->(d)",
                    rows=data["exposures"],
                ).consume()
                tx.run(
                    "CREATE (:RiskNetworkVersion {fingerprint: $version})",
                    version=version,
                ).consume()

            session.execute_write(write)


def load_edges(expected_version: str) -> tuple[list[Dependency], list[Exposure]]:
    """Read both edge types from Neo4j after checking the SQL snapshot version."""
    with driver() as db:
        with db.session() as session:
            found = session.run(
                "MATCH (v:RiskNetworkVersion) RETURN v.fingerprint AS version"
            ).single()
            if found is None or found["version"] != expected_version:
                raise StaleGraphError("Graph is missing or out of date. Run graph sync.")
            dependency_rows = session.run(
                "MATCH (b:RiskInstitution)-[r:DEPENDS_ON]->(s:RiskInfrastructure) "
                "RETURN b.id AS bank_id, s.id AS service_id, r.loss AS loss"
            ).data()
            exposure_rows = session.run(
                "MATCH (c:RiskInstitution)-[r:EXPOSED_TO]->(d:RiskInstitution) "
                "RETURN c.id AS creditor_id, d.id AS debtor_id, "
                "r.amount AS amount, r.recovery_rate AS recovery_rate"
            ).data()

    from decimal import Decimal

    dependencies = [
        Dependency(int(r["bank_id"]), int(r["service_id"]), Decimal(r["loss"]))
        for r in dependency_rows
    ]
    exposures = [
        Exposure(int(r["creditor_id"]), int(r["debtor_id"]),
                 Decimal(r["amount"]), Decimal(r["recovery_rate"]))
        for r in exposure_rows
    ]
    return dependencies, exposures
