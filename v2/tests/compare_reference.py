"""
v2/tests/compare_reference.py

Builds each IRS reference trade with the plain-dict builder and diffs the
output against the FINXIS reference file. Covers all 8 reference files:
5 single-currency (Phase 3a) + 3 cross-currency (Phase 3b).

Normalization before comparing (both sides):
  - '@key' / '@ref' bare hash ids dropped
  - key ids canonicalised by first-reference path (S1.., E1..) so definition
    order doesn't cause false diffs
  - unreferenced key definitions dropped (cosmetic)
  - dangling refs become 'UNRESOLVED:<id>' on both sides
  - party[] sorted by first partyId identifier value
  - float.is_integer() -> int

Run from repo root:  python v2/tests/compare_reference.py [name ...]
Names: fixedfloat, ois, zerocoupon, basis, basis-ois,
       xccy-fixedfixed, xccy-fixedfloat, xccy-basis  (default: all)
"""
import sys, json, copy
sys.path.insert(0, '.')

from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput,
    FXLinkedNotionalInput, PrincipalPaymentScheduleInput, TaxonomyInput,
)
from v2.src.builders.cdm_builder import build_irs_trade_state
from v2.src.schemas.fra import FRAInput
from v2.src.builders.fra_builder import build_fra_trade_state

REF_DIR = 'v2/data/reference/interest_rate_swap'
LEI_SCHEME = "http://www.fpml.org/coding-scheme/external/iso17442"
SWAPSWIRE_TID = "http://www.swapswire.com/spec/2001/trade-id-1-0"
SWAPSWIRE_MA = "http://www.swapswire.com/spec/2001/master-agreement-type-1-0"

PARTY_A = PartyInput(key="partyA", lei="549300ABANKV6BYQOWM67",
                     lei_scheme=LEI_SCHEME, id_type="LEI", name='A BANK("ABANK")')
PARTY_B = PartyInput(key="partyB", lei="529900CPTY57S5UCBB52",
                     lei_scheme=LEI_SCHEME, id_type="LEI",
                     name='SELL SECURITIES CO LTD ("Counterparty")')


# ── single-currency fixtures (Phase 3a) ───────────────────────────────────────

def _fixedfloat():
    return IRSTradeInput(
        trade_date="2018-11-15", trade_id="FpML-test-7",
        isda_taxonomy="InterestRate_IRSwap_FixedFloat",
        other_taxonomy="InterestRate::VanillaSwap",
        parties=[PARTY_A, PARTY_B,
                 PartyInput(key="dco", lei="123456QQQQ57S5UCBB11",
                            lei_scheme=LEI_SCHEME, id_type="LEI",
                            name="ABC CENTRAL PARTY CLEARING SVC LTD")],
        party1_key="partyB", party2_key="partyA",
        trade_identifiers=[TradeIdentifierInput(
            issuer_key="partyA",
            id_scheme="http://www.partyA.com/swaps/trade-id",
            id_value="FpML-test-7")],
        calc_agent_key="partyA",
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=3672000000, notional_currency="EUR",
                     floating_index="EUR-EONIA-AVERAGE", day_count_fraction="ACT/360",
                     effective_date="2018-11-16", effective_date_bdc="NONE",
                     termination_date="2023-11-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="NONE",
                     calc_period_multiplier=1, calc_period="M", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     payment_offset_multiplier=1, payment_offset_period="D",
                     payment_offset_day_type="Business"),
            LegInput(payer="Party2", receiver="Party1", leg_type="fixed",
                     notional_amount=3672000000, notional_currency="EUR",
                     fixed_rate=0.002, day_count_fraction="ACT/360",
                     effective_date="2018-11-16", effective_date_bdc="NONE",
                     termination_date="2023-11-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="NONE",
                     calc_period_multiplier=1, calc_period="M", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     payment_offset_multiplier=1, payment_offset_period="D",
                     payment_offset_day_type="Business"),
        ])


def _ois():
    return IRSTradeInput(
        trade_date="2023-02-16", trade_id="FpML-test-7c",
        isda_taxonomy="InterestRate_IRSwap_FixedFloat_OIS",
        parties=[PARTY_A, PARTY_B],
        party1_key="partyA", party2_key="partyB",
        trade_identifiers=[TradeIdentifierInput(
            issuer_key="partyA",
            id_scheme="http://www.partyA.com/swaps/trade-id",
            id_value="FpML-test-7c")],
        master_agreement_type="ISDAMaster", master_agreement_scheme=SWAPSWIRE_MA,
        has_confirmation=True,
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=1100000, notional_currency="GBP",
                     floating_index="GBP-SONIA-OIS Compound",
                     day_count_fraction="ACT/365.FIXED",
                     effective_date="2023-02-16", effective_date_bdc="NONE",
                     termination_date="2033-02-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=1, calc_period="Y", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="Y",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodEndDate",
                     fixing_offset_multiplier=0, fixing_offset_period="D",
                     fixing_bdc="PRECEDING",
                     reset_freq_multiplier=1, reset_freq_period="Y",
                     reset_bdc="MODFOLLOWING"),
            LegInput(payer="Party2", receiver="Party1", leg_type="fixed",
                     notional_amount=1100000, notional_currency="GBP",
                     fixed_rate=0.03537, day_count_fraction="ACT/365.FIXED",
                     effective_date="2023-02-16", effective_date_bdc="NONE",
                     termination_date="2033-02-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=1, calc_period="Y", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="Y",
                     payment_bdc="MODFOLLOWING"),
        ])


def _zerocoupon():
    return IRSTradeInput(
        trade_date="2018-02-20", trade_id="IRS858TH30",
        isda_taxonomy="InterestRate_IRSwap_FixedFloat_ZeroCoupon",
        parties=[
            PartyInput(key="party1", lei="Party 1",
                       lei_scheme="http://www.fpml.org/coding-scheme/external"),
            PartyInput(key="party2", lei="Party 2",
                       lei_scheme="http://www.fpml.org/coding-scheme/external"),
        ],
        party1_key="party1", party2_key="party2",
        trade_identifiers=[TradeIdentifierInput(
            issuer_key="party1",
            id_scheme="http://www.fpml.org/coding-scheme/external/uti",
            id_value="IRS858TH30", id_version=1)],
        upfront_payment_amount=200, upfront_payment_currency="USD",
        upfront_payment_date="2018-02-22",
        upfront_payer_key="party1", upfront_receiver_key="party2",
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="fixed",
                     notional_amount=100000, notional_currency="GBP",
                     fixed_rate=0.03, day_count_fraction="30E/360",
                     effective_date="2018-02-22", effective_date_bdc="MODFOLLOWING",
                     termination_date="2020-02-22", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     first_period_start_date="2018-02-20",
                     calc_period_multiplier=1, calc_period="T", roll_convention="NONE",
                     payment_freq_multiplier=1, payment_freq_period="T",
                     payment_bdc="MODFOLLOWING"),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=100000, notional_currency="GBP",
                     floating_index="GBP-LIBOR-ISDA",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     day_count_fraction="ACT/360",
                     effective_date="2018-02-22", effective_date_bdc="MODFOLLOWING",
                     termination_date="2020-02-22", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="NONE",
                     first_period_start_date="2018-02-20", first_period_start_bdc="NONE",
                     calc_period_multiplier=3, calc_period="M", roll_convention="22",
                     payment_freq_multiplier=1, payment_freq_period="T",
                     payment_bdc="MODFOLLOWING",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING",
                     compounding_method="Flat"),
        ])


def _basis():
    return IRSTradeInput(
        trade_date="2021-04-07", trade_id="58005869",
        isda_taxonomy="InterestRate_IRSwap_Basis",
        parties=[PARTY_A, PARTY_B],
        party1_key="partyA", party2_key="partyB",
        trade_identifiers=[
            TradeIdentifierInput(issuer_key="partyA",
                                 id_scheme=SWAPSWIRE_TID, id_value="58005869"),
            TradeIdentifierInput(issuer_key="partyB",
                                 id_scheme=SWAPSWIRE_TID, id_value="58005869"),
        ],
        master_agreement_type="ISDAMaster", master_agreement_scheme=SWAPSWIRE_MA,
        has_confirmation=True, confirmation_definitions="ISDA2006",
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=150000000, notional_currency="USD",
                     floating_index="USD-SIFMA Municipal Swap Index",
                     day_count_fraction="ACT/ACT.ISDA",
                     effective_date="2021-04-09", effective_date_bdc="NONE",
                     termination_date="2026-04-09", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="9",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=0, fixing_offset_period="D",
                     fixing_bdc="PRECEDING",
                     reset_freq_multiplier=1, reset_freq_period="W",
                     reset_bdc="MODFOLLOWING"),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=150000000, notional_currency="USD",
                     floating_index="USD-LIBOR-BBA",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     day_count_fraction="ACT/360",
                     effective_date="2021-04-09", effective_date_bdc="NONE",
                     termination_date="2026-04-09", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="9",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING"),
        ])


def _basis_ois():
    BC = "primaryBusinessCenters"
    return IRSTradeInput(
        trade_date="2021-08-18", trade_id="BankA1234",
        isda_taxonomy="InterestRate_IRSwap_Basis_OIS",
        primary_asset_class="Commodity",
        product_id_value="Commodity:Metals:Precious:LoanLease:Cash",
        product_id_scheme="http://www.dtcc.com/coding-scheme/external/GTR-Product-Id",
        product_id_source="Other",
        parties=[
            PartyInput(key="party1", lei="Bank A",
                       lei_scheme="http://www.fpml.org/coding-scheme/dummy-party-id",
                       name="Bank a"),
            PartyInput(key="party2", lei="Bank B",
                       lei_scheme="http://www.fpml.org/coding-scheme/dummy-party-id",
                       name="Bank B"),
        ],
        party1_key="party1", party2_key="party2",
        trade_identifiers=[
            TradeIdentifierInput(issuer_key="party1",
                                 id_scheme="http://www.bankB.com/swaps/com-trade-id",
                                 id_value="BankA1234"),
            TradeIdentifierInput(issuer_key="party2",
                                 id_scheme="http://www.bankA.com/swaps/com-trade-id",
                                 id_value="BankB5678"),
        ],
        has_confirmation=True,
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=100, notional_currency="XAU",
                     floating_index="USD-SOFR-OIS Compound",
                     day_count_fraction="ACT/365.FIXED",
                     effective_date="2021-08-18", effective_date_bdc="MODFOLLOWING",
                     termination_date="2022-08-18", termination_date_bdc="MODFOLLOWING",
                     termination_date_bc_ref=BC,
                     calc_period_bdc="MODFOLLOWING", calc_period_bc_ref=BC,
                     calc_period_multiplier=3, calc_period="M", roll_convention="1",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     first_payment_date="2021-11-18",
                     payment_bdc="MODFOLLOWING", payment_bc_ref=BC,
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     fixing_bc_ref=BC,
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING", reset_bc_ref=BC),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=100, notional_currency="XAU",
                     floating_index="GOFO", floating_index_is_named=False,
                     spread=-0.0001,
                     day_count_fraction="ACT/365.FIXED",
                     effective_date="2021-08-18", effective_date_bdc="MODFOLLOWING",
                     effective_date_bc_ref=BC,
                     termination_date="2022-08-18", termination_date_bdc="MODFOLLOWING",
                     termination_date_bc_ref=BC,
                     calc_period_bdc="MODFOLLOWING", calc_period_bc_ref=BC,
                     calc_period_multiplier=3, calc_period="M", roll_convention="1",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     first_payment_date="2021-11-18",
                     payment_bdc="MODFOLLOWING", payment_bc_ref=BC,
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     fixing_bc_ref=BC,
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING", reset_bc_ref=BC),
        ])


# ── cross-currency fixtures (Phase 3b) ────────────────────────────────────────

def _xccy_fixedfixed():
    return IRSTradeInput(
        trade_date="2006-01-09", trade_id="UITD7895394",
        isda_taxonomy="InterestRate_CrossCurrency_FixedFixed",
        parties=[
            PartyInput(key="party1", lei="54930084UKLVMY22DS16",
                       lei_scheme=LEI_SCHEME, id_type="LEI", name="Party A"),
            PartyInput(key="party2", lei="48750084UKLVTR22DS78",
                       lei_scheme=LEI_SCHEME, id_type="LEI", name="Party B"),
        ],
        party1_key="party2", party2_key="party1",
        trade_identifiers=[TradeIdentifierInput(
            issuer_lei="54930084UKLVMY22DS16",
            issuer_scheme=LEI_SCHEME,
            id_scheme="http://www.fpml.org/coding-scheme/external/uti",
            id_value="UITD7895394",
            identifier_type="UniqueTransactionIdentifier")],
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="fixed",
                     notional_amount=1000000000, notional_currency="JPY",
                     fixed_rate=0.001, day_count_fraction="ACT/365.FIXED",
                     cpd_key="fixedCalcPeriodDatesJPY",
                     effective_date="2006-01-11", effective_date_bdc="NONE",
                     termination_date="2011-01-11", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=6, calc_period="M", roll_convention="11",
                     payment_freq_multiplier=6, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     principal_initial=True, principal_final=True,
                     principal_intermediate=True),
            LegInput(payer="Party2", receiver="Party1", leg_type="fixed",
                     notional_amount=100000000, notional_currency="USD",
                     fixed_rate=0.02, day_count_fraction="ACT/365.FIXED",
                     cpd_key="fixedCalcPeriodDatesUSD",
                     effective_date="2006-01-11", effective_date_bdc="NONE",
                     termination_date="2011-01-11", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=6, calc_period="M", roll_convention="11",
                     payment_freq_multiplier=6, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     principal_initial=True, principal_final=True,
                     principal_intermediate=True),
        ])


def _xccy_fixedfloat():
    return IRSTradeInput(
        trade_date="2001-01-09", trade_id="123",
        isda_taxonomy="InterestRate_CrossCurrency_FixedFloat",
        parties=[
            PartyInput(key="party1", lei="Party A",
                       lei_scheme="http://www.fpml.org/coding-scheme/dummy-party-id"),
            PartyInput(key="party2", lei="Party B",
                       lei_scheme="http://www.fpml.org/coding-scheme/dummy-party-id"),
        ],
        party1_key="party2", party2_key="party1",
        trade_identifiers=[
            TradeIdentifierInput(issuer_key="party1",
                                 id_scheme="http://www.partyA.com/trade-id",
                                 id_value="123"),
            TradeIdentifierInput(issuer_key="party2",
                                 id_scheme="http://www.partyB.com/trade-id",
                                 id_value="123"),
        ],
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="fixed",
                     notional_amount=1000000000, notional_currency="JPY",
                     fixed_rate=0.01, day_count_fraction="ACT/365.FIXED",
                     cpd_key="fixedCalcPeriodDates",
                     effective_date="2006-01-11", effective_date_bdc="NONE",
                     termination_date="2011-01-11", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=6, calc_period="M", roll_convention="11",
                     payment_freq_multiplier=6, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     principal_initial=True, principal_final=True,
                     principal_intermediate=True),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=None, notional_currency="USD",
                     floating_index="USD-LIBOR-BBA",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     day_count_fraction="ACT/360",
                     cpd_key="floatingCalcPeriodDates",
                     payment_dates_key="floatingPaymentDates",
                     reset_dates_key="floatingResetDates",
                     effective_date="2006-01-11", effective_date_bdc="NONE",
                     termination_date="2011-01-11", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="11",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING",
                     principal_initial=True, principal_final=True,
                     principal_intermediate=True,
                     quantity_reference_key="notionalScheduleJPY",
                     fx_linked_notional=FXLinkedNotionalInput(
                         varying_notional_currency="USD",
                         fixing_offset_multiplier=-2, fixing_offset_period="D",
                         fixing_offset_day_type="Business", fixing_offset_bdc="NONE",
                         date_relative_to_key="floatingResetDates",
                         source_provider="BankOfJapan",
                         fixing_time="17:00:00", fixing_business_center="JPTO",
                         interim_multiplier=0, interim_period="D",
                         interim_bdc="NONE",
                         interim_date_relative_to_key="floatingPaymentDates",
                     )),
        ])


def _xccy_basis():
    return IRSTradeInput(
        trade_date="2018-03-19", trade_id="DRTY123456",
        isda_taxonomy="InterestRate_CrossCurrency_Basis",
        primary_asset_class="InterestRate",
        additional_taxonomies=[
            TaxonomyInput(source="CFI", value="SRAXCC",
                          value_scheme="http://www.fpml.org/coding-scheme/external/product-classification/iso10962"),
            TaxonomyInput(source="EMIR", value="SW",
                          value_scheme="http://www.dtcc.com/coding-scheme/external/product-classification/emir-contract-type"),
        ],
        product_id_value="InterestRate:CrossCurrency:Basis",
        product_id_scheme="http://www.dtcc.com/coding-scheme/external/GTR-Product-Id",
        product_id_source="Other",
        tradedate_key="tradeDate",
        parties=[
            PartyInput(key="party1", lei="54930084UKLVMY22DS16",
                       lei_scheme=LEI_SCHEME, id_type="LEI", name="Party A"),
            PartyInput(key="party2", lei="48750084UKLVTR22DS78",
                       lei_scheme=LEI_SCHEME, id_type="LEI", name="Party B"),
        ],
        party1_key="party1", party2_key="party2",
        trade_identifiers=[
            TradeIdentifierInput(
                issuer_lei="1031234567",
                issuer_scheme="http://www.fpml.org/coding-scheme/external/nsa/cftc",
                id_scheme="http://www.fpml.org/coding-scheme/external/usi",
                id_value="DRTY123456",
                identifier_type="UniqueSwapIdentifier"),
            TradeIdentifierInput(
                issuer_lei="54930084UKLVMY22DS16",
                issuer_scheme=LEI_SCHEME,
                id_scheme="http://www.fpml.org/coding-scheme/external/uti",
                id_value="UITD7895394",
                identifier_type="UniqueTransactionIdentifier"),
        ],
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=2034.95, notional_currency="USD",
                     floating_index="USD-LIBOR-BBA",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     day_count_fraction="ACT/360",
                     cpd_key="d0e5285", reset_dates_key="d0e5632",
                     effective_date="2018-03-21", effective_date_bdc="MODFOLLOWING",
                     termination_date="2023-03-21", termination_date_bdc="MODFOLLOWING",
                     termination_date_adjusted="2023-03-21",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="21",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     first_payment_date="2018-06-21",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING",
                     compounding_method="None",
                     cashflow_matches_parameters=False,
                     principal_initial=False, principal_final=False,
                     principal_intermediate=True,
                     settlement_currency="USD",
                     quantity_reference_key="fixed_notional_schedule",
                     fx_linked_notional=FXLinkedNotionalInput(
                         varying_notional_currency="USD",
                         fixing_offset_multiplier=2, fixing_offset_period="D",
                         fixing_offset_day_type="Business",
                         fixing_offset_bdc="MODFOLLOWING",
                         date_relative_to_key="tradeDate",
                         source_provider="Telerate",
                         source_page="WM Company LDN 11am Mid",
                         source_page_heading="USD/EUR",
                         fixing_time="11:00:00", fixing_business_center="GBLO",
                         interim_multiplier=2, interim_period="D",
                         interim_day_type="Business", interim_bdc="MODFOLLOWING",
                         interim_date_relative_to_key="tradeDate",
                     )),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=1650, notional_currency="EUR",
                     floating_index="EUR-EURIBOR-Telerate",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     spread=-0.0045,
                     day_count_fraction="ACT/360",
                     cpd_key="d0e6004", reset_dates_key="d0e6350",
                     effective_date="2018-03-21", effective_date_bdc="MODFOLLOWING",
                     termination_date="2023-03-21", termination_date_bdc="MODFOLLOWING",
                     termination_date_adjusted="2023-03-21",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="21",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     first_payment_date="2018-06-21",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING",
                     compounding_method="None",
                     cashflow_matches_parameters=False,
                     principal_initial=True, principal_final=True,
                     principal_intermediate=True,
                     settlement_currency="EUR",
                     principal_schedule=PrincipalPaymentScheduleInput(
                         initial_date="2018-03-21",
                         initial_payer="Party1", initial_receiver="Party2",
                         initial_amount=1650, initial_currency="EUR",
                         final_date="2023-03-21",
                         final_payer="Party2", final_receiver="Party1",
                         final_amount=1650, final_currency="EUR",
                     )),
        ])


def _fra():
    return FRAInput(
        trade_date="1991-05-14", trade_id="MB87623",
        isda_taxonomy="InterestRate_Fra",
        parties=[
            PartyInput(key="party1", lei="TR24TWEY5RVRQV65HD49",
                       lei_scheme=LEI_SCHEME, id_type="LEI"),
            PartyInput(key="party2", lei="BFXS5XCH7N0Y05NIXW11",
                       lei_scheme=LEI_SCHEME, id_type="LEI"),
        ],
        party1_key="party1", party2_key="party2",
        trade_identifiers=[
            TradeIdentifierInput(issuer_key="party1",
                                 id_scheme="http://www.hsbc.com/swaps/trade-id",
                                 id_value="MB87623"),
            TradeIdentifierInput(issuer_key="party2",
                                 id_scheme="http://www.abnamro.com/swaps/trade-id",
                                 id_value="AA9876"),
        ],
        notional_amount=25000000, notional_currency="CHF",
        day_count_fraction="ACT/360",
        fixed_rate=0.04,
        floating_index="CHF-LIBOR-BBA",
        index_tenor_multiplier=6, index_tenor_period="M",
        reset_date="1991-07-17", reset_date_key="resetDate",
        termination_date="1992-01-17",
        payment_date="1991-07-17", payment_date_bdc="FOLLOWING",
        fixing_offset_multiplier=-2, fixing_offset_period="D",
        fixing_offset_day_type="Business", fixing_bdc="NONE",
        fixed_leg_payment_freq_multiplier=6, fixed_leg_payment_freq_period="M",
        fixed_leg_payer="Party1", floating_leg_payer="Party2",
    )


CASES = {
    "fixedfloat":     (_fixedfloat,     f"{REF_DIR}/swaps/irs-fixedfloat.json",              build_irs_trade_state),
    "ois":            (_ois,             f"{REF_DIR}/swaps/irs-fixedfloat-ois.json",           build_irs_trade_state),
    "zerocoupon":     (_zerocoupon,      f"{REF_DIR}/swaps/irs-fixedfloat-zerocoupon.json",     build_irs_trade_state),
    "basis":          (_basis,           f"{REF_DIR}/cross_currency/irs-basis.json",            build_irs_trade_state),
    "basis-ois":      (_basis_ois,       f"{REF_DIR}/cross_currency/irs-basis-ois.json",         build_irs_trade_state),
    "xccy-fixedfixed":(_xccy_fixedfixed, f"{REF_DIR}/cross_currency/irs-xccy-fixedfixed.json",   build_irs_trade_state),
    "xccy-fixedfloat":(_xccy_fixedfloat, f"{REF_DIR}/cross_currency/irs-xccy-fixedfloat.json",   build_irs_trade_state),
    "xccy-basis":     (_xccy_basis,      f"{REF_DIR}/cross_currency/irs-xccy-basis.json",        build_irs_trade_state),
    "fra":            (_fra,             f"{REF_DIR}/swaps/irs-fra.json",                        build_fra_trade_state),
}


# ── normalization (identity-aware) ────────────────────────────────────────────

def _walk(node, path, first_ref):
    if isinstance(node, dict):
        for k, v in node.items():
            child_path = f"{path}.{k}" if path else k
            if k == "@ref:scoped":
                first_ref.setdefault(("@key:scoped", v), child_path)
            elif k == "@ref:external":
                first_ref.setdefault(("@key:external", v), child_path)
            else:
                _walk(v, child_path, first_ref)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", first_ref)


def _apply(node, mapping):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ("@key", "@ref"):
                continue
            if k in ("@key:scoped", "@key:external"):
                if (k, v) in mapping:
                    out[k] = mapping[(k, v)]
            elif k == "@ref:scoped":
                out[k] = mapping.get(("@key:scoped", v), f"UNRESOLVED:{v}")
            elif k == "@ref:external":
                out[k] = mapping.get(("@key:external", v), f"UNRESOLVED:{v}")
            else:
                out[k] = _apply(v, mapping)
        return out
    if isinstance(node, list):
        return [_apply(item, mapping) for item in node]
    if isinstance(node, float) and node.is_integer():
        return int(node)
    return node


def normalize(doc):
    first_ref = {}
    _walk(doc, "", first_ref)
    mapping, counters = {}, {"@key:scoped": 0, "@key:external": 0}
    ordered = sorted(first_ref.items(), key=lambda kv: (kv[0][0], kv[1]))
    for (kind, ident), _path in ordered:
        counters[kind] += 1
        prefix = "S" if kind == "@key:scoped" else "E"
        mapping[(kind, ident)] = f"{prefix}{counters[kind]}"
    result = _apply(copy.deepcopy(doc), mapping)
    parties = result.get('trade', {}).get('party', [])
    if parties:
        def _party_sort_key(p):
            ids = p.get('partyId', [{}])
            return ids[0].get('identifier', {}).get('@data', '') if ids else ''
        result['trade']['party'] = sorted(parties, key=_party_sort_key)
    return result


# ── diff ──────────────────────────────────────────────────────────────────────

def diff(ours, ref, path, out):
    if isinstance(ours, dict) and isinstance(ref, dict):
        for k in sorted(set(ours) | set(ref)):
            p = f"{path}.{k}" if path else k
            if k not in ours:
                out.append(("MISSING (in ours)", p, None, ref[k]))
            elif k not in ref:
                out.append(("EXTRA (not in reference)", p, ours[k], None))
            else:
                diff(ours[k], ref[k], p, out)
    elif isinstance(ours, list) and isinstance(ref, list):
        if len(ours) != len(ref):
            out.append(("LIST LENGTH", path, len(ours), len(ref)))
        for i, (a, b) in enumerate(zip(ours, ref)):
            diff(a, b, f"{path}[{i}]", out)
    else:
        if ours != ref:
            out.append(("VALUE", path, ours, ref))


# ── run ───────────────────────────────────────────────────────────────────────

def run_case(name, show=25):
    fixture_fn, ref_path, builder_fn = CASES[name]
    ours_raw = builder_fn(fixture_fn())
    with open(ref_path) as f:
        ref_raw = json.load(f)
    out_path = f"v2/tests/out_{name}.json"
    with open(out_path, 'w') as f:
        json.dump(ours_raw, f, indent=2)
    diffs = []
    diff(normalize(ours_raw), normalize(ref_raw), "", diffs)
    status = "EXACT MATCH" if not diffs else f"{len(diffs)} diffs"
    print(f"{name:18s} {status}   (output: {out_path})")
    for kind, path, a, b in diffs[:show]:
        print(f"    [{kind}] {path}")
        if a is not None:
            print(f"        ours: {json.dumps(a)[:130]}")
        if b is not None:
            print(f"        ref : {json.dumps(b)[:130]}")
    if len(diffs) > show:
        print(f"    ... and {len(diffs) - show} more")
    return len(diffs)


if __name__ == "__main__":
    names = sys.argv[1:] or list(CASES)
    total = sum(run_case(n) for n in names)
    print(f"\ntotal diffs across {len(names)} files: {total}")
