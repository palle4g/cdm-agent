"""
v2/src/schemas/interest_rate_swap.py
Input schema for Interest Rate Swap trades (plain-dict builder pipeline).
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
    floating_index_is_named: bool = True     # False: identifier only, no floatingRateIndex value (e.g. GOFO)
    index_tenor_multiplier: Optional[int] = None
    index_tenor_period: Optional[str] = None
    spread: Optional[float] = None
    day_count_fraction: str = "ACT/360"
    effective_date: str = ""
    termination_date: str = ""
    first_period_start_date: Optional[str] = None
    first_period_start_bdc: Optional[str] = None   # defaults to effective_date_bdc
    calc_period_multiplier: int = 1
    calc_period: str = "M"
    roll_convention: str = "NONE"
    calc_period_bdc: str = "MODFOLLOWING"
    effective_date_bdc: str = "NONE"
    termination_date_bdc: str = "MODFOLLOWING"
    # optional businessCenters references (external key, e.g. "primaryBusinessCenters")
    effective_date_bc_ref: Optional[str] = None
    termination_date_bc_ref: Optional[str] = None
    calc_period_bc_ref: Optional[str] = None
    payment_bc_ref: Optional[str] = None
    fixing_bc_ref: Optional[str] = None
    reset_bc_ref: Optional[str] = None
    payment_freq_multiplier: int = 1
    payment_freq_period: str = "M"
    pay_relative_to: str = "CalculationPeriodEndDate"
    payment_bdc: str = "MODFOLLOWING"
    first_payment_date: Optional[str] = None
    payment_offset_multiplier: Optional[int] = None
    payment_offset_period: Optional[str] = None
    payment_offset_day_type: Optional[str] = None
    # reset block — emitted when reset_freq_multiplier is set (floating legs)
    reset_relative_to: Optional[str] = None        # omitted from output when None
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
    lei: Optional[str] = None                # identifier value (LEI or internal id)
    lei_scheme: Optional[str] = None
    id_type: Optional[str] = None            # e.g. "LEI"; omitted when None
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
    primary_asset_class: Optional[str] = None  # e.g. "Commodity" — emitted as first taxonomy entry
    # product-level identifier (e.g. GTR product id)
    product_id_value: Optional[str] = None
    product_id_scheme: Optional[str] = None
    product_id_source: Optional[str] = None  # e.g. "Other"
    calc_agent_key: Optional[str] = None
    # contract details (legal documentation)
    master_agreement_type: Optional[str] = None      # e.g. "ISDAMaster"
    master_agreement_scheme: Optional[str] = None
    has_confirmation: bool = False
    confirmation_definitions: Optional[str] = None   # e.g. "ISDA2006"
    # upfront payment (zero-coupon)
    upfront_payment_amount: Optional[float] = None
    upfront_payment_currency: Optional[str] = None
    upfront_payment_date: Optional[str] = None
    upfront_payer_key: Optional[str] = None
    upfront_receiver_key: Optional[str] = None
