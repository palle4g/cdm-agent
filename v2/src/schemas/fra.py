"""
v2/src/schemas/fra.py
Input schema for Forward Rate Agreements (FRA).

FRA is structurally close to IRS (same InterestRatePayout, FixedRate/
FloatingRateSpecification, and observable/index shapes) but has a single
settlement period rather than a repeating calculation schedule, and a
singular net-settlement paymentDate rather than a paymentDates schedule.
Kept as its own module rather than overloading IRSTradeInput/LegInput with
FRA-only fields.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from v2.src.schemas.interest_rate_swap import PartyInput, TradeIdentifierInput


@dataclass
class FRAInput:
    trade_date: str
    trade_id: str
    isda_taxonomy: str
    parties: List[PartyInput] = field(default_factory=list)
    party1_key: str = ""
    party2_key: str = ""
    trade_identifiers: List[TradeIdentifierInput] = field(default_factory=list)

    notional_amount: float = 0.0
    notional_currency: str = ""
    day_count_fraction: str = "ACT/360"

    fixed_rate: float = 0.0
    floating_index: str = ""
    index_tenor_multiplier: int = 6
    index_tenor_period: str = "M"

    reset_date: str = ""              # adjustedDate, shared by both legs' effectiveDate
    reset_date_key: str = "resetDate" # @key:external name for the reset date
    termination_date: str = ""        # adjustedDate

    payment_date: str = ""            # singular net-settlement date (unadjustedDate)
    payment_date_bdc: str = "FOLLOWING"

    fixing_offset_multiplier: int = -2
    fixing_offset_period: str = "D"
    fixing_offset_day_type: Optional[str] = "Business"
    fixing_bdc: str = "NONE"

    # odd-but-real artifact: some FRA records show a paymentFrequency on the
    # fixed leg only (not a real repeating schedule, just how the source
    # data was written) — set both to include it, leave None to omit
    fixed_leg_payment_freq_multiplier: Optional[int] = None
    fixed_leg_payment_freq_period: Optional[str] = None

    fixed_leg_payer: str = "Party1"     # CDM role that pays the fixed amount
    floating_leg_payer: str = "Party2"  # CDM role that pays the floating amount
