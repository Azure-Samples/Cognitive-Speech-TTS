from __future__ import annotations

from dataclasses import dataclass


MIN_LOAN_USD = 1_000
MAX_LOAN_USD = 1_000_000
ALLOWED_TERMS_MONTHS = tuple(range(12, 361, 12))

_CREDIT_TIER_ADJUSTMENTS = {
    "excellent": 0.00,
    "good": 0.35,
    "fair": 1.00,
    "limited": 1.75,
}
_AMOUNT_BANDS = (
    ("small_conforming", 250_000, 6.95),
    ("standard_conforming", 832_750, 6.85),
    ("jumbo", 1_000_000, 7.05),
)
_NEGOTIATION_RANGE = 0.25


@dataclass(frozen=True)
class PricedOffer:
    amount_usd: int
    term_months: int
    annual_rate_percent: float
    monthly_payment_usd: int
    credit_tier: str
    amount_band: str
    at_best_available: bool
    can_reduce_further: bool
    requires_officer_review: bool

    def public(self) -> dict[str, object]:
        return {
            "amount_usd": self.amount_usd,
            "term_months": self.term_months,
            "annual_rate_percent": self.annual_rate_percent,
            "monthly_payment_usd": self.monthly_payment_usd,
            "credit_tier": self.credit_tier,
            "amount_band": self.amount_band,
            "at_best_available": self.at_best_available,
            "can_reduce_further": self.can_reduce_further,
            "requires_officer_review": self.requires_officer_review,
            "indicative": True,
        }


def rate_ladder(credit_tier: str, term_months: int) -> list[dict[str, object]]:
    credit_adjustment = _CREDIT_TIER_ADJUSTMENTS.get(credit_tier, 2.25)
    term_adjustment = _term_adjustment(term_months)
    return [
        {
            "amount_band": name,
            "min_amount_usd": (
                MIN_LOAN_USD if index == 0 else _AMOUNT_BANDS[index - 1][1] + 1
            ),
            "max_amount_usd": ceiling,
            "starting_annual_rate_percent": round(
                base_rate + credit_adjustment + term_adjustment,
                2,
            ),
        }
        for index, (name, ceiling, base_rate) in enumerate(_AMOUNT_BANDS)
    ]


def _amount_band(amount_usd: int) -> tuple[str, float]:
    for name, ceiling, base_rate in _AMOUNT_BANDS:
        if amount_usd <= ceiling:
            return name, base_rate
    raise ValueError(f"amount exceeds supported maximum: {amount_usd}")


def _term_adjustment(term_months: int) -> float:
    if term_months <= 180:
        return -0.70
    if term_months < 360:
        return -0.30
    return 0.00


def _monthly_payment(amount_usd: int, annual_rate_percent: float, term_months: int) -> int:
    monthly_rate = annual_rate_percent / 1200.0
    if monthly_rate == 0:
        return round(amount_usd / term_months)
    factor = (1 + monthly_rate) ** term_months
    return round(amount_usd * monthly_rate * factor / (factor - 1))


def price_offer(
    *,
    amount_usd: int,
    term_months: int,
    credit_tier: str,
    indicative_max_loan_usd: int,
    requested_rate_percent: float | None,
    current_rate_percent: float | None,
) -> PricedOffer:
    amount_band, amount_base_rate = _amount_band(amount_usd)
    credit_adjustment = _CREDIT_TIER_ADJUSTMENTS.get(credit_tier, 2.25)
    starting_rate = round(
        amount_base_rate + credit_adjustment + _term_adjustment(term_months),
        2,
    )
    floor = round(starting_rate - _NEGOTIATION_RANGE, 2)

    if requested_rate_percent is None:
        offered_rate = (
            min(current_rate_percent, starting_rate)
            if current_rate_percent is not None
            else starting_rate
        )
    else:
        offered_rate = max(floor, min(requested_rate_percent, starting_rate))
        if current_rate_percent is not None:
            offered_rate = min(offered_rate, current_rate_percent)
    offered_rate = round(offered_rate, 2)
    at_best_available = offered_rate <= floor

    return PricedOffer(
        amount_usd=amount_usd,
        term_months=term_months,
        annual_rate_percent=offered_rate,
        monthly_payment_usd=_monthly_payment(
            amount_usd, offered_rate, term_months
        ),
        credit_tier=credit_tier,
        amount_band=amount_band,
        at_best_available=at_best_available,
        can_reduce_further=not at_best_available,
        requires_officer_review=amount_usd > indicative_max_loan_usd,
    )
