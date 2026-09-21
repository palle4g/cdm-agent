"""
v2/src/builders/cdm_builder.py

Builds real ISDA CDM JSON for Interest Rate Swaps as PLAIN PYTHON DICTS,
in exactly the shape of the FINXIS reference files
(v2/data/reference/interest_rate_swap/). No finos imports — the reference
files are the spec; correctness is checked by diffing against them
(see v2/tests/compare_reference.py).

Why not finos.cdm Pydantic objects: finos-cdm 7.2-7.4 + rune-runtime 2.2.1
cannot currently roundtrip this format (reference resolution, choice-type
routing, and serializer bugs — see v2/experiments/finos_cdm_roundtrip/ and
https://github.com/finos/rune-python-runtime/issues/37). Revisit as an
optional validation pass when upstream fixes land.

Scope: single-currency Fixed/Float, OIS, Zero-Coupon, Basis (Phase 3a).
Cross-currency is Phase 3b.
"""
from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput
)

CDM_VERSION = "0.0.0.master-SNAPSHOT"


# ── small shape helpers ───────────────────────────────────────────────────────

def _data(value):
    return {"@data": value}


def _scheme_data(scheme, value):
    out = {}
    if scheme:
        out["@scheme"] = scheme
    out["@data"] = value
    return out


def _bdc(convention, bc_ref=None):
    out = {"businessDayConvention": convention}
    if bc_ref:
        out["businessCenters"] = {
            "businessCentersReference": {"@ref:external": bc_ref}
        }
    return out


def _adjustable_date(iso_date, bdc, bc_ref=None):
    return {
        "adjustableDate": {
            "unadjustedDate": iso_date,
            "dateAdjustments": _bdc(bdc, bc_ref),
        }
    }


def _currency_unit(currency):
    return {"currency": _data(currency)}


# ── keyed objects (quantity / price / observable) ─────────────────────────────

def _quantity(key, amount, currency):
    return {
        "@key:scoped": key,
        "value": amount,
        "unit": _currency_unit(currency),
    }


def _price(key, rate, currency, operator=None):
    p = {
        "@key:scoped": key,
        "value": rate,
        "unit": _currency_unit(currency),
        "perUnitOf": _currency_unit(currency),
        "priceType": "InterestRate",
    }
    if operator:
        p["arithmeticOperator"] = operator
    return p


def _observable(obs_key, index_key, leg: LegInput):
    fri = {
        "@type": "cdm.observable.asset.FloatingRateIndex",
        "identifier": [
            {
                "identifier": _data(leg.floating_index),
                "identifierType": "Other",
            }
        ],
        "assetType": "Other",
        "assetClass": "InterestRate",
    }
    if leg.floating_index_is_named:
        fri["floatingRateIndex"] = _data(leg.floating_index)
    if leg.index_tenor_multiplier is not None and leg.index_tenor_period:
        fri["indexTenor"] = {
            "periodMultiplier": leg.index_tenor_multiplier,
            "period": leg.index_tenor_period,
        }
    return {
        "@key:scoped": obs_key,
        "@data": {
            "@type": "cdm.observable.asset.InterestRateIndex",
            "@key:scoped": index_key,
            "@data": fri,
        },
    }


# ── payout-leg blocks ─────────────────────────────────────────────────────────

def _calculation_period_dates(leg: LegInput, key):
    cpd = {
        "@key:external": key,
        "effectiveDate": _adjustable_date(
            leg.effective_date, leg.effective_date_bdc, leg.effective_date_bc_ref
        ),
        "terminationDate": _adjustable_date(
            leg.termination_date, leg.termination_date_bdc, leg.termination_date_bc_ref
        ),
        "calculationPeriodDatesAdjustments": _bdc(leg.calc_period_bdc, leg.calc_period_bc_ref),
    }
    if leg.first_period_start_date:
        cpd["firstPeriodStartDate"] = _adjustable_date(
            leg.first_period_start_date,
            leg.first_period_start_bdc or leg.effective_date_bdc,
        )
    cpd["calculationPeriodFrequency"] = {
        "periodMultiplier": leg.calc_period_multiplier,
        "period": leg.calc_period,
        "rollConvention": leg.roll_convention,
    }
    return cpd


def _payment_dates(leg: LegInput):
    pd = {
        "paymentFrequency": {
            "periodMultiplier": leg.payment_freq_multiplier,
            "period": leg.payment_freq_period,
        }
    }
    if leg.first_payment_date:
        pd["firstPaymentDate"] = leg.first_payment_date
    pd["payRelativeTo"] = leg.pay_relative_to
    if leg.payment_offset_multiplier is not None:
        offset = {
            "periodMultiplier": leg.payment_offset_multiplier,
            "period": leg.payment_offset_period,
        }
        if leg.payment_offset_day_type:
            offset["dayType"] = leg.payment_offset_day_type
        pd["paymentDaysOffset"] = offset
    pd["paymentDatesAdjustments"] = _bdc(leg.payment_bdc, leg.payment_bc_ref)
    return pd


def _reset_dates(leg: LegInput, calc_key, reset_key):
    rd = {
        "@key:external": reset_key,
        "calculationPeriodDatesReference": {"@ref:external": calc_key},
    }
    if leg.reset_relative_to:
        rd["resetRelativeTo"] = leg.reset_relative_to

    fixing = {
        "periodMultiplier": leg.fixing_offset_multiplier,
        "period": leg.fixing_offset_period,
    }
    if leg.fixing_offset_day_type:
        fixing["dayType"] = leg.fixing_offset_day_type
    if leg.fixing_bdc:
        fixing["businessDayConvention"] = leg.fixing_bdc
    if leg.fixing_bc_ref:
        fixing["businessCentersReference"] = {"@ref:external": leg.fixing_bc_ref}
    fixing["dateRelativeTo"] = {"@ref:external": reset_key}
    rd["fixingDates"] = fixing

    rd["resetFrequency"] = {
        "periodMultiplier": leg.reset_freq_multiplier,
        "period": leg.reset_freq_period,
    }
    rd["resetDatesAdjustments"] = _bdc(leg.reset_bdc, leg.reset_bc_ref)
    return rd


def _build_leg(leg: LegInput, leg_no: int, counters: dict):
    """
    Returns (payout_dict, trade_lot_price_quantity_entry).
    counters tracks price-N / InterestRateIndex-N / observable-N numbering
    by order of first use, matching the reference files.
    """
    qty_key = f"quantity-{leg_no}"

    payout = {
        "@type": "cdm.product.asset.InterestRatePayout",
        "payerReceiver": {"payer": leg.payer, "receiver": leg.receiver},
        "priceQuantity": {"quantitySchedule": {"@ref:scoped": qty_key}},
    }

    if leg.leg_type == "fixed":
        counters["price"] += 1
        price_key = f"price-{counters['price']}"
        payout["rateSpecification"] = {
            "@type": "cdm.product.asset.FixedRateSpecification",
            "rateSchedule": {"price": {"@ref:scoped": price_key}},
        }
        pq_entry = {
            "price": [_price(price_key, leg.fixed_rate, leg.notional_currency)],
            "quantity": _quantity(qty_key, leg.notional_amount, leg.notional_currency),
        }
    else:  # floating
        counters["index"] += 1
        counters["observable"] += 1
        index_key = f"InterestRateIndex-{counters['index']}"
        obs_key = f"observable-{counters['observable']}"
        rate_spec = {
            "@type": "cdm.product.asset.FloatingRateSpecification",
            "rateOption": {"@ref:scoped": index_key},
        }
        pq_entry = {
            "quantity": _quantity(qty_key, leg.notional_amount, leg.notional_currency),
            "observable": _observable(obs_key, index_key, leg),
        }
        if leg.spread is not None:
            counters["price"] += 1
            price_key = f"price-{counters['price']}"
            rate_spec["spreadSchedule"] = {"price": {"@ref:scoped": price_key}}
            pq_entry = {
                "price": [_price(price_key, leg.spread, leg.notional_currency, operator="Add")],
                "quantity": pq_entry["quantity"],
                "observable": pq_entry["observable"],
            }
        payout["rateSpecification"] = rate_spec

    payout["dayCountFraction"] = _data(leg.day_count_fraction)

    calc_key = f"calculationPeriodDates-leg{leg_no}"
    payout["calculationPeriodDates"] = _calculation_period_dates(leg, calc_key)
    payout["paymentDates"] = _payment_dates(leg)

    if leg.leg_type == "floating" and leg.reset_freq_multiplier is not None:
        reset_key = f"resetDates-leg{leg_no}"
        payout["resetDates"] = _reset_dates(leg, calc_key, reset_key)

    if leg.compounding_method:
        payout["compoundingMethod"] = leg.compounding_method

    return payout, pq_entry


# ── parties / identifiers / contract details ──────────────────────────────────

def _party(p: PartyInput):
    ident = {"identifier": _scheme_data(p.lei_scheme, p.lei or p.key)}
    if p.id_type:
        ident["identifierType"] = p.id_type
    party = {"@key:external": p.key, "partyId": [ident]}
    if p.name:
        party["name"] = _data(p.name)
    return party


def _trade_identifier(tid: TradeIdentifierInput):
    ti = {}
    if tid.issuer_key:
        ti["issuerReference"] = {"@ref:external": tid.issuer_key}
    elif tid.issuer_lei:
        ti["issuer"] = _scheme_data(tid.issuer_scheme, tid.issuer_lei)
    assigned = {"identifier": _scheme_data(tid.id_scheme, tid.id_value)}
    if tid.id_version is not None:
        assigned["version"] = tid.id_version
    ti["assignedIdentifier"] = [assigned]
    if tid.identifier_type:
        ti["identifierType"] = tid.identifier_type
    return ti


def _contract_details(input_data: IRSTradeInput):
    contractual = [{"@ref:external": p.key} for p in input_data.parties]
    docs = []
    if input_data.master_agreement_type:
        docs.append({
            "legalAgreementIdentification": {
                "agreementName": {
                    "agreementType": "MasterAgreement",
                    "masterAgreementType": _scheme_data(
                        input_data.master_agreement_scheme,
                        input_data.master_agreement_type,
                    ),
                }
            },
            "contractualParty": contractual,
        })
    if input_data.has_confirmation:
        name = {"agreementType": "Confirmation"}
        if input_data.confirmation_definitions:
            name["contractualDefinitionsType"] = [_data(input_data.confirmation_definitions)]
        docs.append({
            "legalAgreementIdentification": {"agreementName": name},
            "contractualParty": contractual,
        })
    return {"documentation": docs} if docs else None


# ── main entry point ──────────────────────────────────────────────────────────

def build_irs_trade_state(input_data: IRSTradeInput) -> dict:
    """Build a real ISDA CDM TradeState dict in reference-file shape."""
    counters = {"price": 0, "index": 0, "observable": 0}
    payouts, pq_entries = [], []
    for i, leg in enumerate(input_data.legs, start=1):
        payout, pq = _build_leg(leg, i, counters)
        payouts.append(payout)
        pq_entries.append(pq)

    taxonomy = []
    if input_data.primary_asset_class:
        taxonomy.append({"primaryAssetClass": _data(input_data.primary_asset_class)})
    if input_data.other_taxonomy:
        taxonomy.append({
            "source": "Other",
            "value": {"name": _data(input_data.other_taxonomy)},
        })
    if input_data.isda_taxonomy:
        taxonomy.append({
            "source": "ISDA",
            "value": {"name": _data(input_data.isda_taxonomy)},
            "calculated": True,
        })

    economic_terms = {"payout": payouts}
    if input_data.calc_agent_key:
        economic_terms["calculationAgent"] = {
            "calculationAgentParty": "CalculationAgentIndependent"
        }

    product = {}
    if input_data.product_id_value:
        product["identifier"] = [{
            "identifier": _scheme_data(input_data.product_id_scheme,
                                       input_data.product_id_value),
            "source": input_data.product_id_source,
        }]
    if taxonomy:
        product["taxonomy"] = taxonomy
    product["economicTerms"] = economic_terms

    trade = {
        "product": product,
        "tradeLot": [{"priceQuantity": pq_entries}],
        "counterparty": [
            {"role": "Party1", "partyReference": {"@ref:external": input_data.party1_key}},
            {"role": "Party2", "partyReference": {"@ref:external": input_data.party2_key}},
        ],
    }
    if input_data.calc_agent_key:
        trade["ancillaryParty"] = [{
            "role": "CalculationAgentIndependent",
            "partyReference": [{"@ref:external": input_data.calc_agent_key}],
        }]
    trade["tradeIdentifier"] = [_trade_identifier(t) for t in input_data.trade_identifiers]
    trade["tradeDate"] = _data(input_data.trade_date)
    trade["party"] = [_party(p) for p in input_data.parties]

    contract_details = _contract_details(input_data)
    if contract_details:
        trade["contractDetails"] = contract_details

    result = {
        "@model": "cdm",
        "@type": "cdm.event.common.TradeState",
        "@version": CDM_VERSION,
        "trade": trade,
    }

    if input_data.upfront_payment_amount is not None:
        result["transferHistory"] = [{
            "transfer": {
                "@type": "cdm.event.common.UnscheduledTransfer",
                "quantity": {
                    "value": input_data.upfront_payment_amount,
                    "unit": _currency_unit(input_data.upfront_payment_currency),
                },
                "asset": {
                    "@type": "cdm.base.staticdata.asset.common.Cash",
                    "identifier": [{
                        "identifier": _data(input_data.upfront_payment_currency),
                        "identifierType": "CurrencyCode",
                    }],
                    "assetType": "Cash",
                },
                "settlementDate": {
                    "unadjustedDate": input_data.upfront_payment_date,
                    "dateAdjustments": _bdc("MODFOLLOWING"),
                },
                "payerReceiver": {
                    "payerPartyReference": {"@ref:external": input_data.upfront_payer_key},
                    "receiverPartyReference": {"@ref:external": input_data.upfront_receiver_key},
                },
                "transferType": "Upfront",
            }
        }]

    return result
