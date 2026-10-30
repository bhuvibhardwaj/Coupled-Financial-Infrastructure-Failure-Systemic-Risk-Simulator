"""API-layer rules: request validation and snapshot backward compatibility.

These exercise the pure helpers behind the run endpoints, so they run without a
live PostgreSQL or Neo4j instance.
"""

import unittest
from decimal import Decimal as D

from fastapi import HTTPException
from pydantic import ValidationError

from backend.runs import FailureInput, RunRequest, build_failures, snapshot_failures
from backend.simulation import Bank, Dependency, Exposure, simulate

SERVICES = [
    {"id": 1, "name": "Payment Rail", "category": "Payments"},
    {"id": 2, "name": "Cloud Platform", "category": "Cloud"},
]

# A run saved before multi-service support only carried a single service.
LEGACY_SNAPSHOT = {
    "network": {
        "banks": [
            {"id": 1, "name": "Bank A", "buffer": "100"},
            {"id": 2, "name": "Bank B", "buffer": "50"},
            {"id": 3, "name": "Bank C", "buffer": "75"},
        ],
        "services": [{"id": 1, "name": "Payment Rail", "category": "Payments"}],
        "dependencies": [{"bank_id": 1, "service_id": 1, "loss": "120"}],
        "exposures": [
            {"creditor_id": 2, "debtor_id": 1, "amount": "80", "recovery_rate": "0.25"},
            {"creditor_id": 3, "debtor_id": 2, "amount": "90", "recovery_rate": "0.20"},
        ],
    },
    "failed_service_id": 1,
    "severity": 100,
}

MULTI_SNAPSHOT = {
    "network": {
        "banks": [{"id": 1, "name": "Bank A", "buffer": "100"}],
        "services": SERVICES,
        "dependencies": [
            {"bank_id": 1, "service_id": 1, "loss": "120"},
            {"bank_id": 1, "service_id": 2, "loss": "80"},
        ],
        "exposures": [],
    },
    "failures": [
        {"service_id": 1, "severity": 50, "service_name": "Payment Rail"},
        {"service_id": 2, "severity": 25, "service_name": "Cloud Platform"},
    ],
    "failed_service_id": 1,
    "severity": 50,
}


def replay(snapshot: dict):
    """Mirror how compare_run rebuilds and replays a saved scenario."""
    network = snapshot["network"]
    banks = [Bank(b["id"], b["name"], D(b["buffer"])) for b in network["banks"]]
    dependencies = [
        Dependency(d["bank_id"], d["service_id"], D(d["loss"]))
        for d in network["dependencies"]
    ]
    exposures = [
        Exposure(e["creditor_id"], e["debtor_id"], D(e["amount"]), D(e["recovery_rate"]))
        for e in network["exposures"]
    ]
    severities = {f["service_id"]: f["severity"] for f in snapshot_failures(snapshot)}
    service_names = {s["id"]: s["name"] for s in network["services"]}
    return simulate(banks, dependencies, exposures, severities, service_names)


class RunRequestValidationTests(unittest.TestCase):
    def test_accepts_multiple_failures(self):
        request = RunRequest(name="Storm", failures=[
            {"service_id": 1, "severity": 100},
            {"service_id": 2, "severity": 50},
        ])
        self.assertEqual(len(request.failures), 2)

    def test_rejects_empty_failure_list(self):
        with self.assertRaises(ValidationError):
            RunRequest(name="Empty", failures=[])

    def test_rejects_severity_out_of_range(self):
        for bad in (-1, 101):
            with self.assertRaises(ValidationError):
                RunRequest(name="Bad", failures=[{"service_id": 1, "severity": bad}])

    def test_rejects_non_positive_service_id(self):
        with self.assertRaises(ValidationError):
            RunRequest(name="Bad", failures=[{"service_id": 0, "severity": 10}])


class BuildFailuresTests(unittest.TestCase):
    def test_attaches_service_names(self):
        failures = build_failures([FailureInput(service_id=2, severity=40)], SERVICES)
        self.assertEqual(failures, [
            {"service_id": 2, "severity": 40, "service_name": "Cloud Platform"},
        ])

    def test_rejects_unknown_service(self):
        with self.assertRaises(HTTPException) as caught:
            build_failures([FailureInput(service_id=99, severity=50)], SERVICES)
        self.assertEqual(caught.exception.status_code, 404)

    def test_rejects_duplicate_services(self):
        with self.assertRaises(HTTPException) as caught:
            build_failures([
                FailureInput(service_id=1, severity=10),
                FailureInput(service_id=1, severity=20),
            ], SERVICES)
        self.assertEqual(caught.exception.status_code, 422)


class SnapshotBackwardCompatTests(unittest.TestCase):
    def test_legacy_snapshot_yields_single_failure(self):
        self.assertEqual(
            snapshot_failures(LEGACY_SNAPSHOT),
            [{"service_id": 1, "severity": 100}],
        )

    def test_multi_snapshot_passes_all_failures_through(self):
        self.assertEqual(len(snapshot_failures(MULTI_SNAPSHOT)), 2)

    def test_legacy_run_replays_identically(self):
        result = replay(LEGACY_SNAPSHOT)
        self.assertEqual(result.default_count, 2)
        self.assertEqual(result.impacts[0].operational_loss, D("120.00"))

    def test_rerun_uses_original_severities(self):
        # 120 x 50% + 80 x 25% = 80, below the 100 buffer: no default.
        result = replay(MULTI_SNAPSHOT)
        self.assertEqual(result.impacts[0].operational_loss, D("80.00"))
        self.assertEqual(result.default_count, 0)


if __name__ == "__main__":
    unittest.main()
