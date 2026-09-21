"""
v2/src/schemas/interest_rate_swap.py
Input schema for Interest Rate Swap trades.
The agent extracts these fields from raw legacy input.
cdm_builder.py maps this into real CDM JSON (plain dicts, reference-file shape).
Covers: single-currency Fixed/Float, OIS, Zero-Coupon, Basis swaps.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LegInput:
    payer: str
    receiver: str
    leg_type: str                            # "fixed" or "floating"
    notional_amount: float
    notional_currency: str
    fixed_rate: Optional[float] = None
    floating_index: Optional[str] = None
    index_tenor_multiplier: Optional[int] = None
    index_tenor_period: Optional[str] = None
    spread: Optional[float] = None
    day_count_fraction: str = "ACT/360"
    effective_date: str = ""
    termination_date: str = ""
    first_period_start_date: Optional[str] = None
    calc_period_multiplier: int = 1
    calc_period: str = "M"
    roll_convention: str = "NONE"
    calc_period_bdc: str = "MODFOLLOWING"
    effective_date_bdc: str = "NONE"
    termination_date_bdc: str = "MODFOLLOWING"
    payment_freq_multiplier: int = 1
    payment_freq_period: str = "M"
    pay_relative_to: str = "CalculationPeriodEndDate"
    payment_bdc: str = "MODFOLLOWING"
    first_payment_date: Optional[str] = None
    payment_offset_multiplier: Optional[int] = None
    payment_offset_period: Optional[str] = None
    payment_offset_day_type: Optional[str] = None
    reset_relative_to: Optional[str] = None
    fixing_offset_multiplier: Optional[int] = None
    fixing_offset_period: Optional[str] = None
    fixing_offset_day_type: Optional[str] = None
    fixing_bdc: Optional[str] = None
    reset_freq_multiplier: Optional[int] = None
    reset_freq_period: Optional[str] = None
    reset_bdc: Optional[str] = None
    compounding_method: Optional[str] = None


@dataclass
class PartyInput:
    key: str
    lei: Optional[str] = None
    lei_scheme: Optional[str] = None
    name: Optional[str] = None


@dataclass
class TradeIdentifierInput:
    issuer_key: Optional[str] = None
    issuer_lei: Optional[str] = None
    issuer_scheme: Optional[str] = None
    id_scheme: str = ""
    id_value: str = ""
    id_version: Optional[int] = None
    identifier_type: Optional[str] = None


@dataclass
class IRSTradeInput:
    trade_date: str
    trade_id: str
    parties: List[PartyInput] = field(default_factory=list)
    party1_key: str = ""
    party2_key: str = ""
    trade_identifiers: List[TradeIdentifierInput] = field(default_factory=list)
    legs: List[LegInput] = field(default_factory=list)
    isda_taxonomy: Optional[str] = None
    other_taxonomy: Optional[str] = None     # e.g. "InterestRate::VanillaSwap"
    calc_agent_key: Optional[str] = None
    upfront_payment_amount: Optional[float] = None
    upfront_payment_currency: Optional[str] = None
    upfront_payment_date: Optional[str] = None
    upfront_payer_key: Optional[str] = None
    upfront_receiver_key: Optional[str] = None
