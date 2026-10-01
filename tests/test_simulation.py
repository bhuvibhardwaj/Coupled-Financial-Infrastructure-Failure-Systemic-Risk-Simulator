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
            1, 100,
        )
        self.assertEqual(result.default_count, 2)
        self.assertEqual(result.risk_score, D("49.33"))
        self.assertEqual(result.impacts[0].operational_loss, D("120.00"))
        self.assertEqual(result.impacts[1].financial_loss, D("60.00"))
        self.assertEqual(result.impacts[1].first_affected_round, 1)
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
            1, 100,
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
            1, 100,
        )
        self.assertEqual(result.default_count, 3)
        self.assertEqual(result.impacts[2].financial_loss, D("60.00"))
        self.assertEqual(result.impacts[2].first_affected_round, 1)

    def test_zero_severity_does_not_propagate(self):
        result = simulate(
            [Bank(1, "A", D("50")), Bank(2, "B", D("50"))],
            [Dependency(1, 1, D("60"))],
            [Exposure(2, 1, D("100"), D("0"))],
            1, 0,
        )
        self.assertEqual(result.default_count, 0)
        self.assertEqual(result.risk_score, D("0.00"))


if __name__ == "__main__":
    unittest.main()
