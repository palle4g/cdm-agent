"""
v2/tests/test_irs_fixedfloat.py

Builds a CDM TradeState from the irs-fixedfloat.json reference trade
and prints the output. Run from repo root:

    python -c "import sys; sys.path.insert(0,'.')" && python v2/tests/test_irs_fixedfloat.py

or simply:
    cd /d/projects/cdm-agent
    python v2/tests/test_irs_fixedfloat.py
"""
import sys, json
sys.path.insert(0, '.')

from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput
)
from v2.src.builders.cdm_builder import build_irs_trade_state

# ── input data derived from irs-fixedfloat.json ──────────────────────────────
# Reference file: v2/data/reference/interest_rate_swap/swaps/irs-fixedfloat.json
# Taxonomy: InterestRate_IRSwap_FixedFloat
# Trade date: 2018-11-15
# Leg 1: Party1 pays floating (EUR-EONIA-AVERAGE), Party2 receives
# Leg 2: Party2 pays fixed (0.2%), Party1 receives
# Notional: EUR 3,672,000,000
# Tenor: 2018-11-16 to 2023-11-16, monthly

input_data = IRSTradeInput(
    trade_date="2018-11-15",
    trade_id="FpML-test-7",
    isda_taxonomy="InterestRate_IRSwap_FixedFloat",
    parties=[
        PartyInput(
            key="partyA",
            lei="549300ABANKV6BYQOWM67",
            lei_scheme="http://www.fpml.org/coding-scheme/external/iso17442",
            name='A BANK("ABANK")'
        ),
        PartyInput(
            key="partyB",
            lei="529900CPTY57S5UCBB52",
            lei_scheme="http://www.fpml.org/coding-scheme/external/iso17442",
            name='SELL SECURITIES CO LTD ("Counterparty")'
        ),
    ],
    party1_key="partyB",   # Party1 role assigned to partyB per reference file
    party2_key="partyA",   # Party2 role assigned to partyA per reference file
    trade_identifiers=[
        TradeIdentifierInput(
            issuer_key="partyA",
            id_scheme="http://www.partyA.com/swaps/trade-id",
            id_value="FpML-test-7"
        )
    ],
    calc_agent_key="partyA",
    legs=[
        # Leg 1: floating (Party1 pays EUR-EONIA-AVERAGE)
        LegInput(
            payer="Party1",
            receiver="Party2",
            leg_type="floating",
            notional_amount=3672000000.0,
            notional_currency="EUR",
            floating_index="EUR-EONIA-AVERAGE",
            day_count_fraction="ACT/360",
            effective_date="2018-11-16",
            effective_date_bdc="NONE",
            termination_date="2023-11-16",
            termination_date_bdc="MODFOLLOWING",
            calc_period_bdc="NONE",
            calc_period_multiplier=1,
            calc_period="M",
            roll_convention="16",
            payment_freq_multiplier=1,
            payment_freq_period="M",
            pay_relative_to="CalculationPeriodEndDate",
            payment_bdc="MODFOLLOWING",
            payment_offset_multiplier=1,
            payment_offset_period="D",
            payment_offset_day_type="Business",
            reset_relative_to="CalculationPeriodEndDate",
            fixing_offset_multiplier=0,
            fixing_offset_period="D",
            fixing_bdc="NONE",
            reset_freq_multiplier=1,
            reset_freq_period="M",
            reset_bdc="MODFOLLOWING",
        ),
        # Leg 2: fixed (Party2 pays 0.2%)
        LegInput(
            payer="Party2",
            receiver="Party1",
            leg_type="fixed",
            notional_amount=3672000000.0,
            notional_currency="EUR",
            fixed_rate=0.002,
            day_count_fraction="ACT/360",
            effective_date="2018-11-16",
            effective_date_bdc="NONE",
            termination_date="2023-11-16",
            termination_date_bdc="MODFOLLOWING",
            calc_period_bdc="NONE",
            calc_period_multiplier=1,
            calc_period="M",
            roll_convention="16",
            payment_freq_multiplier=1,
            payment_freq_period="M",
            pay_relative_to="CalculationPeriodEndDate",
            payment_bdc="MODFOLLOWING",
            payment_offset_multiplier=1,
            payment_offset_period="D",
            payment_offset_day_type="Business",
        ),
    ]
)

result = build_irs_trade_state(input_data)
print(json.dumps(result, indent=2, default=str))
