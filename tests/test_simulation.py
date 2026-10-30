"""Hand-checkable cascade cases; these need no running databases."""

import unittest
from decimal import Decimal

from backend.simulation import Bank, Dependency, Exposure, simulate

D = Decimal


class SimulationTests(unittest.TestCase):
    def test_payment_rail_cascade_matches_worked_example(self):
        banks = [
            Bank(1, "Bank A", D("100")), Bank(2, "Bank B", D("50")),
            Bank(3, "Bank C", D("75")), Bank(4, "Bank D", D("90")),
            Bank(5, "Bank E", D("80")), Bank(6, "Bank F", D("110")),
        ]
        result = simulate(
            banks,
            [Dependency(1, 1, D("120"))],
            [Exposure(2, 1, D("80"), D("0.25")),
             Exposure(3, 2, D("90"), D("0.20"))],
            {1: 100},
        )
        self.assertEqual(result.default_count, 2)
        self.assertEqual(result.risk_score, D("49.33"))
        self.assertEqual(result.impacts[0].operational_loss, D("120.00"))
        self.assertEqual(result.impacts[1].financial_loss, D("60.00"))
        self.assertEqual(result.impacts[1].first_affected_round, 1)
        self.assertEqual(
            result.impacts[1].propagation_path,
            ["Service #1", "Bank A", "Bank B"],
        )
        self.assertEqual(result.impacts[2].financial_loss, D("72.00"))
        self.assertEqual(result.impacts[2].stress_pct, D("96.00"))
        self.assertEqual(result.impacts[2].first_affected_round, 2)
        self.assertFalse(result.impacts[2].defaulted)
        self.assertIsNone(result.impacts[3].first_affected_round)

    def test_cycle_processed_once(self):
        result = simulate(
            [Bank(1, "A", D("50")), Bank(2, "B", D("50"))],
            [Dependency(1, 1, D("60"))],
            [Exposure(2, 1, D("100"), D("0")),
             Exposure(1, 2, D("20"), D("0"))],
            {1: 100},
        )
        self.assertEqual(result.default_count, 2)
        self.assertEqual(result.impacts[0].financial_loss, D("20.00"))
        self.assertEqual(result.impacts[1].financial_loss, D("100.00"))

    def test_combines_same_round_losses_before_default_check(self):
        result = simulate(
            [Bank(1, "A", D("50")), Bank(2, "B", D("50")),
             Bank(3, "C", D("50"))],
            [Dependency(1, 1, D("60")), Dependency(2, 1, D("60"))],
            [Exposure(3, 1, D("30"), D("0")),
             Exposure(3, 2, D("30"), D("0"))],
            {1: 100},
        )
        self.assertEqual(result.default_count, 3)
        self.assertEqual(result.impacts[2].financial_loss, D("60.00"))
        self.assertEqual(result.impacts[2].first_affected_round, 1)

    def test_zero_severity_does_not_propagate(self):
        result = simulate(
            [Bank(1, "A", D("50")), Bank(2, "B", D("50"))],
            [Dependency(1, 1, D("60"))],
            [Exposure(2, 1, D("100"), D("0"))],
            {1: 0},
        )
        self.assertEqual(result.default_count, 0)
        self.assertEqual(result.risk_score, D("0.00"))

    def test_extra_buffer_stops_the_second_default(self):
        result = simulate(
            [Bank(1, "Bank A", D("100")), Bank(2, "Bank B", D("70")),
             Bank(3, "Bank C", D("75"))],
            [Dependency(1, 1, D("120"))],
            [Exposure(2, 1, D("80"), D("0.25")),
             Exposure(3, 2, D("90"), D("0.20"))],
            {1: 100}, service_names={1: "Payment Rail"},
        )
        self.assertEqual(result.default_count, 1)
        self.assertEqual(result.impacts[1].stress_pct, D("85.71"))
        self.assertEqual(result.impacts[2].financial_loss, D("0.00"))
        self.assertEqual(
            result.impacts[1].propagation_path,
            ["Payment Rail", "Bank A", "Bank B"],
        )

    def test_multiple_failures_aggregate_operational_loss(self):
        # 120 x 50% = 60 and 80 x 25% = 20, summed before any default check.
        result = simulate(
            [Bank(1, "Bank A", D("1000"))],
            [Dependency(1, 1, D("120")), Dependency(1, 2, D("80"))],
            [],
            {1: 50, 2: 25},
        )
        self.assertEqual(result.impacts[0].operational_loss, D("80.00"))
        self.assertEqual(result.impacts[0].stress_pct, D("8.00"))
        self.assertEqual(result.default_count, 0)

    def test_combined_failures_cross_the_buffer_together(self):
        # Neither service alone exhausts the 100 buffer, but their sum does.
        banks = [Bank(1, "Bank A", D("100"))]
        dependencies = [Dependency(1, 1, D("120")), Dependency(1, 2, D("80"))]
        alone = simulate(banks, [dependencies[0]], [], {1: 50})
        self.assertFalse(alone.impacts[0].defaulted)
        combined = simulate(banks, dependencies, [], {1: 50, 2: 50})
        self.assertEqual(combined.impacts[0].operational_loss, D("100.00"))
        self.assertTrue(combined.impacts[0].defaulted)
        self.assertEqual(combined.default_count, 1)
        self.assertEqual(combined.risk_score, D("100.00"))

    def test_multiple_failures_still_cascade_through_exposures(self):
        # Two services drain Bank A (80 + 40 = 120); the usual cascade follows.
        result = simulate(
            [Bank(1, "Bank A", D("100")), Bank(2, "Bank B", D("50")),
             Bank(3, "Bank C", D("75"))],
            [Dependency(1, 1, D("80")), Dependency(1, 2, D("40"))],
            [Exposure(2, 1, D("80"), D("0.25")),
             Exposure(3, 2, D("90"), D("0.20"))],
            {1: 100, 2: 100},
        )
        self.assertEqual(result.default_count, 2)
        self.assertEqual(result.impacts[0].operational_loss, D("120.00"))
        self.assertEqual(result.impacts[1].financial_loss, D("60.00"))
        self.assertEqual(result.impacts[2].financial_loss, D("72.00"))
        self.assertFalse(result.impacts[2].defaulted)
        # The path starts at the service contributing the largest loss.
        self.assertEqual(
            result.impacts[0].propagation_path, ["Service #1", "Bank A"]
        )
        self.assertEqual(
            result.impacts[1].propagation_path,
            ["Service #1", "Bank A", "Bank B"],
        )

    def test_requires_at_least_one_failed_service(self):
        with self.assertRaises(ValueError):
            simulate([Bank(1, "A", D("50"))], [], [], {})

    def test_rejects_out_of_range_severity_in_any_failure(self):
        with self.assertRaises(ValueError):
            simulate(
                [Bank(1, "A", D("50"))],
                [Dependency(1, 1, D("60"))],
                [],
                {1: 100, 2: 150},
            )


if __name__ == "__main__":
    unittest.main()
