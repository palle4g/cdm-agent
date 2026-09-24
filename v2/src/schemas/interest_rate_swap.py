"""
v2/src/schemas/interest_rate_swap.py
Input schema for Interest Rate Swap trades (plain-dict builder pipeline).
Covers: single-currency Fixed/Float, OIS, Zero-Coupon, Basis (Phase 3a)
        and cross-currency Fixed/Fixed, Fixed/Float, Basis (Phase 3b).
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class FXLinkedNotionalInput:
    """FX-linked notional schedule for cross-currency legs."""
    varying_notional_currency: str
    # fixing dates relative to a named external key (e.g. "floatingResetDates", "tradeDate")
    fixing_offset_multiplier: int
    fixing_offset_period: str
    fixing_offset_day_type: Optional[str] = None
    fixing_offset_bdc: str = "NONE"
    date_relative_to_key: str = ""        # @ref:external target
    # FX rate source
    source_provider: str = ""             # e.g. "BankOfJapan", "Telerate"
    source_page: Optional[str] = None     # e.g. "WM Company LDN 11am Mid"
    source_page_heading: Optional[str] = None  # e.g. "USD/EUR"
    # fixing time
    fixing_time: str = ""                 # "17:00:00"
    fixing_business_center: str = ""      # "JPTO", "GBLO"
    # interim exchange payment dates
    interim_multiplier: int = 0
    interim_period: str = "D"
    interim_day_type: Optional[str] = None
    interim_bdc: str = "NONE"
    interim_date_relative_to_key: str = ""  # @ref:external target


@dataclass
class PrincipalPaymentScheduleInput:
    """Initial and final principal exchange amounts (xccy-basis leg 2 style)."""
    initial_date: Optional[str] = None        # adjustedDate
    initial_payer: Optional[str] = None       # "Party1" / "Party2"
    initial_receiver: Optional[str] = None
    initial_amount: Optional[float] = None
    initial_currency: Optional[str] = None
    final_date: Optional[str] = None          # adjustedDate
    final_payer: Optional[str] = None
    final_receiver: Optional[str] = None
    final_amount: Optional[float] = None
    final_currency: Optional[str] = None


@dataclass
class LegInput:
    payer: str
    receiver: str
    leg_type: str                            # "fixed" or "floating"
    notional_currency: str
    notional_amount: Optional[float] = None  # None for FX-linked legs
    fixed_rate: Optional[float] = None
    floating_index: Optional[str] = None
    floating_index_is_named: bool = True     # False: identifier only, no floatingRateIndex value
    index_tenor_multiplier: Optional[int] = None
    index_tenor_period: Optional[str] = None
    spread: Optional[float] = None
    day_count_fraction: str = "ACT/360"
    effective_date: str = ""
    termination_date: str = ""
    termination_date_adjusted: Optional[str] = None  # adjustedDate alongside unadjustedDate
    first_period_start_date: Optional[str] = None
    first_period_start_bdc: Optional[str] = None
    calc_period_multiplier: int = 1
    calc_period: str = "M"
    roll_convention: str = "NONE"
    calc_period_bdc: str = "MODFOLLOWING"
    effective_date_bdc: str = "NONE"
    termination_date_bdc: str = "MODFOLLOWING"
    # optional businessCenters references
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
    # reset block
    reset_relative_to: Optional[str] = None
    fixing_offset_multiplier: Optional[int] = None
    fixing_offset_period: Optional[str] = None
    fixing_offset_day_type: Optional[str] = None
    fixing_bdc: Optional[str] = None
    reset_freq_multiplier: Optional[int] = None
    reset_freq_period: Optional[str] = None
    reset_bdc: Optional[str] = None
    compounding_method: Optional[str] = None
    # cross-currency additions
    cpd_key: Optional[str] = None           # named @key:external for calculationPeriodDates
    payment_dates_key: Optional[str] = None # named @key:external for paymentDates
    reset_dates_key: Optional[str] = None   # named @key:external for resetDates
    principal_initial: bool = False
    principal_final: bool = False
    principal_intermediate: bool = False
    principal_schedule: Optional[PrincipalPaymentScheduleInput] = None
    settlement_currency: Optional[str] = None
    cashflow_matches_parameters: Optional[bool] = None
    fx_linked_notional: Optional[FXLinkedNotionalInput] = None
    quantity_reference_key: Optional[str] = None  # dangling @ref:external


@dataclass
class PartyInput:
    key: str
    lei: Optional[str] = None
    lei_scheme: Optional[str] = None
    id_type: Optional[str] = None
    name: Optional[str] = None


@dataclass
class TradeIdentifierInput:
    issuer_key: Optional[str] = None       # -> issuerReference (@ref:external)
    issuer_lei: Optional[str] = None       # -> issuer (@data)
    issuer_scheme: Optional[str] = None
    id_scheme: str = ""
    id_value: str = ""
    id_version: Optional[int] = None
    identifier_type: Optional[str] = None  # e.g. "UniqueTransactionIdentifier"


@dataclass
class TaxonomyInput:
    """Non-ISDA taxonomy entry (CFI, EMIR). For the primary asset class,
    use IRSTradeInput.primary_asset_class directly, not this class."""
    source: str = ""                       # "CFI", "EMIR"
    value: str = ""                        # taxonomy code/name value
    value_scheme: Optional[str] = None     # scheme URI for the value


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
    other_taxonomy: Optional[str] = None
    primary_asset_class: Optional[str] = None
    additional_taxonomies: List[TaxonomyInput] = field(default_factory=list)
    product_id_value: Optional[str] = None
    product_id_scheme: Optional[str] = None
    product_id_source: Optional[str] = None
    calc_agent_key: Optional[str] = None
    master_agreement_type: Optional[str] = None
    master_agreement_scheme: Optional[str] = None
    has_confirmation: bool = False
    confirmation_definitions: Optional[str] = None
    upfront_payment_amount: Optional[float] = None
    upfront_payment_currency: Optional[str] = None
    upfront_payment_date: Optional[str] = None
    upfront_payer_key: Optional[str] = None
    upfront_receiver_key: Optional[str] = None
    tradedate_key: Optional[str] = None    # @key:external on tradeDate (xccy-basis)
