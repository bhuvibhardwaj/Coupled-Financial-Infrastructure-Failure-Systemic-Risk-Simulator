"""Small, deterministic financial cascade used by the API and tests."""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Bank:
    id: int
    name: str
    buffer: Decimal


@dataclass(frozen=True)
class Dependency:
    bank_id: int
    service_id: int
    loss_at_full_failure: Decimal


@dataclass(frozen=True)
class Exposure:
    creditor_id: int
    debtor_id: int
    amount: Decimal
    recovery_rate: Decimal


@dataclass
class Impact:
    bank_id: int
    bank_name: str
    first_affected_round: int | None = None
    operational_loss: Decimal = Decimal("0.00")
    financial_loss: Decimal = Decimal("0.00")
    stress_pct: Decimal = Decimal("0.00")
    defaulted: bool = False
    propagation_path: list[str] = field(default_factory=list)


@dataclass
class Result:
    impacts: list[Impact]
    risk_score: Decimal
    default_count: int


def simulate(
    banks: list[Bank],
    dependencies: list[Dependency],
    exposures: list[Exposure],
    failed_service_id: int,
    severity: int,
    service_name: str | None = None,
) -> Result:
    if not 0 <= severity <= 100:
        raise ValueError("Severity must be between 0 and 100")
    if not banks:
        raise ValueError("At least one bank is required")

    by_id = {bank.id: bank for bank in banks}
    if len(by_id) != len(banks) or any(bank.buffer <= 0 for bank in banks):
        raise ValueError("Banks must have unique IDs and positive buffers")
    impacts = {bank.id: Impact(bank.id, bank.name) for bank in banks}

    for edge in dependencies:
        if edge.bank_id not in by_id or edge.loss_at_full_failure < 0:
            raise ValueError("Invalid dependency")
        if edge.service_id != failed_service_id:
            continue
        loss = money(edge.loss_at_full_failure * Decimal(severity) / 100)
        if loss > 0:
            impacts[edge.bank_id].operational_loss += loss
            impacts[edge.bank_id].first_affected_round = 0
            impacts[edge.bank_id].propagation_path = [
                service_name or f"Service #{failed_service_id}",
                by_id[edge.bank_id].name,
            ]

    for edge in exposures:
        if (edge.creditor_id not in by_id or edge.debtor_id not in by_id
                or edge.creditor_id == edge.debtor_id or edge.amount < 0
                or not 0 <= edge.recovery_rate <= 1):
            raise ValueError("Invalid exposure")

    newly_defaulted = {
        bank.id for bank in banks
        if impacts[bank.id].operational_loss >= bank.buffer
    }
    processed_defaults: set[int] = set()
    round_number = 1

    while newly_defaulted:
        processed_defaults.update(newly_defaulted)
        round_losses: dict[int, Decimal] = {}
        for edge in sorted(exposures, key=lambda item: (item.debtor_id, item.creditor_id)):
            if edge.debtor_id in newly_defaulted:
                loss = money(edge.amount * (1 - edge.recovery_rate))
                round_losses[edge.creditor_id] = (
                    round_losses.get(edge.creditor_id, Decimal("0.00")) + loss
                )
                if loss > 0 and not impacts[edge.creditor_id].propagation_path:
                    impacts[edge.creditor_id].propagation_path = [
                        *impacts[edge.debtor_id].propagation_path,
                        by_id[edge.creditor_id].name,
                    ]
        for creditor_id, loss in round_losses.items():
            if loss <= 0:
                continue
            impact = impacts[creditor_id]
            impact.financial_loss += loss
            if impact.first_affected_round is None:
                impact.first_affected_round = round_number

        newly_defaulted = {
            bank.id for bank in banks
            if bank.id not in processed_defaults
            and impacts[bank.id].operational_loss + impacts[bank.id].financial_loss
            >= bank.buffer
        }
        round_number += 1

    for bank in banks:
        impact = impacts[bank.id]
        total = impact.operational_loss + impact.financial_loss
        impact.defaulted = total >= bank.buffer
        impact.stress_pct = money(min(Decimal("100"), total * 100 / bank.buffer))

    ordered = [impacts[bank.id] for bank in banks]
    score = money(sum((item.stress_pct for item in ordered), Decimal("0")) / len(ordered))
    return Result(ordered, score, sum(item.defaulted for item in ordered))
