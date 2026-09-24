"""
v2/src/builders/fra_builder.py

Builds real ISDA CDM JSON for Forward Rate Agreements as plain Python dicts,
in the shape of the FINXIS reference file (irs-fra.json). Reuses the small
shape helpers from cdm_builder.py (no duplication of _data/_bdc/_price/etc).
"""
from v2.src.schemas.fra import FRAInput
from v2.src.builders.cdm_builder import (
    CDM_VERSION, _data, _bdc, _price, _quantity, _party, _trade_identifier,
)


def _calculation_period_dates(inp: FRAInput):
    return {
        "effectiveDate": {
            "@key:external": inp.reset_date_key,
            "adjustableDate": {"adjustedDate": _data(inp.reset_date)},
        },
        "terminationDate": {
            "adjustableDate": {"adjustedDate": _data(inp.termination_date)},
        },
    }


def _payment_date(inp: FRAInput):
    return {
        "unadjustedDate": inp.payment_date,
        "dateAdjustments": _bdc(inp.payment_date_bdc),
    }


def _floating_observable(inp: FRAInput, obs_key: str, index_key: str):
    fri = {
        "@type": "cdm.observable.asset.FloatingRateIndex",
        "identifier": [{"identifier": _data(inp.floating_index), "identifierType": "Other"}],
        "assetType": "Other",
        "assetClass": "InterestRate",
        "floatingRateIndex": _data(inp.floating_index),
        "indexTenor": {
            "periodMultiplier": inp.index_tenor_multiplier,
            "period": inp.index_tenor_period,
        },
    }
    return {
        "@key:scoped": obs_key,
        "@data": {
            "@type": "cdm.observable.asset.InterestRateIndex",
            "@key:scoped": index_key,
            "@data": fri,
        },
    }


def build_fra_trade_state(inp: FRAInput) -> dict:
    """Build a real ISDA CDM TradeState dict for a Forward Rate Agreement."""

    fixed_payout = {
        "@type": "cdm.product.asset.InterestRatePayout",
        "payerReceiver": {"payer": inp.fixed_leg_payer, "receiver": inp.floating_leg_payer},
        "priceQuantity": {"quantitySchedule": {"@ref:scoped": "quantity-1"}},
        "rateSpecification": {
            "@type": "cdm.product.asset.FixedRateSpecification",
            "rateSchedule": {"price": {"@ref:scoped": "price-1"}},
        },
        "dayCountFraction": _data(inp.day_count_fraction),
        "calculationPeriodDates": _calculation_period_dates(inp),
    }
    if inp.fixed_leg_payment_freq_multiplier is not None:
        fixed_payout["paymentDates"] = {
            "paymentFrequency": {
                "periodMultiplier": inp.fixed_leg_payment_freq_multiplier,
                "period": inp.fixed_leg_payment_freq_period,
            }
        }
    fixed_payout["paymentDate"] = _payment_date(inp)

    index_key = "InterestRateIndex-1"
    obs_key = "observable-1"

    fixing = {
        "periodMultiplier": inp.fixing_offset_multiplier,
        "period": inp.fixing_offset_period,
    }
    if inp.fixing_offset_day_type:
        fixing["dayType"] = inp.fixing_offset_day_type
    fixing["businessDayConvention"] = inp.fixing_bdc
    fixing["dateRelativeTo"] = {"@ref:external": inp.reset_date_key}

    floating_payout = {
        "@type": "cdm.product.asset.InterestRatePayout",
        "payerReceiver": {"payer": inp.floating_leg_payer, "receiver": inp.fixed_leg_payer},
        "priceQuantity": {"quantitySchedule": {"@ref:scoped": "quantity-2"}},
        "rateSpecification": {
            "@type": "cdm.product.asset.FloatingRateSpecification",
            "rateOption": {"@ref:scoped": index_key},
        },
        "dayCountFraction": _data(inp.day_count_fraction),
        "calculationPeriodDates": _calculation_period_dates(inp),
        "paymentDate": _payment_date(inp),
        "resetDates": {"fixingDates": fixing},
    }

    pq_entries = [
        {
            "price": [_price("price-1", inp.fixed_rate, inp.notional_currency)],
            "quantity": _quantity("quantity-1", inp.notional_amount, inp.notional_currency),
        },
        {
            "quantity": _quantity("quantity-2", inp.notional_amount, inp.notional_currency),
            "observable": _floating_observable(inp, obs_key, index_key),
        },
    ]

    taxonomy = [{
        "source": "ISDA",
        "value": {"name": _data(inp.isda_taxonomy)},
        "calculated": True,
    }]

    trade = {
        "product": {
            "taxonomy": taxonomy,
            "economicTerms": {"payout": [fixed_payout, floating_payout]},
        },
        "tradeLot": [{"priceQuantity": pq_entries}],
        "counterparty": [
            {"role": "Party1", "partyReference": {"@ref:external": inp.party1_key}},
            {"role": "Party2", "partyReference": {"@ref:external": inp.party2_key}},
        ],
        "tradeIdentifier": [_trade_identifier(t) for t in inp.trade_identifiers],
        "tradeDate": _data(inp.trade_date),
        "party": [_party(p) for p in inp.parties],
    }

    return {
        "@model": "cdm",
        "@type": "cdm.event.common.TradeState",
        "@version": CDM_VERSION,
        "trade": trade,
    }
