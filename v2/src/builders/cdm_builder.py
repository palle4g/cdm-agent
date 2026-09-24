"""
v2/src/builders/cdm_builder.py

Builds real ISDA CDM JSON for Interest Rate Swaps as PLAIN PYTHON DICTS,
in exactly the shape of the FINXIS reference files
(v2/data/reference/interest_rate_swap/). No finos imports.

Scope:
  Phase 3a: single-currency Fixed/Float, OIS, Zero-Coupon, Basis
  Phase 3b: cross-currency Fixed/Fixed, Fixed/Float, Basis

Correctness checked by v2/tests/compare_reference.py (all reference files).
"""
from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput,
    FXLinkedNotionalInput, PrincipalPaymentScheduleInput, TaxonomyInput,
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


def _adjustable_date(iso_date, bdc, bc_ref=None, adjusted_date=None):
    adj = {
        "unadjustedDate": iso_date,
        "dateAdjustments": _bdc(bdc, bc_ref),
    }
    if adjusted_date:
        adj["adjustedDate"] = _data(adjusted_date)
    return {"adjustableDate": adj}


def _currency_unit(currency):
    return {"currency": _data(currency)}


def _amount(value, currency):
    return {"value": value, "unit": _currency_unit(currency)}


# ── keyed objects ─────────────────────────────────────────────────────────────

def _quantity(key, amount, currency):
    q = {"@key:scoped": key}
    if amount is not None:
        q["value"] = amount
    q["unit"] = _currency_unit(currency)
    return q


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
        "identifier": [{"identifier": _data(leg.floating_index), "identifierType": "Other"}],
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


# ── FX-linked notional ────────────────────────────────────────────────────────

def _fx_linked_notional(fx: FXLinkedNotionalInput):
    fixing = {
        "periodMultiplier": fx.fixing_offset_multiplier,
        "period": fx.fixing_offset_period,
    }
    if fx.fixing_offset_day_type:
        fixing["dayType"] = fx.fixing_offset_day_type
    fixing["businessDayConvention"] = fx.fixing_offset_bdc
    fixing["dateRelativeTo"] = {"@ref:external": fx.date_relative_to_key}

    source = {"sourceProvider": _data(fx.source_provider)}
    if fx.source_page:
        source["sourcePage"] = _data(fx.source_page)
    if fx.source_page_heading:
        source["sourcePageHeading"] = fx.source_page_heading

    interim = {
        "periodMultiplier": fx.interim_multiplier,
        "period": fx.interim_period,
    }
    if fx.interim_day_type:
        interim["dayType"] = fx.interim_day_type
    interim["businessDayConvention"] = fx.interim_bdc
    interim["dateRelativeTo"] = {"@ref:external": fx.interim_date_relative_to_key}

    return {
        "fxLinkedNotionalSchedule": {
            "varyingNotionalCurrency": _data(fx.varying_notional_currency),
            "varyingNotionalFixingDates": fixing,
            "fxSpotRateSource": {"primarySource": source},
            "fixingTime": {
                "hourMinuteTime": fx.fixing_time,
                "businessCenter": _data(fx.fixing_business_center),
            },
            "varyingNotionalInterimExchangePaymentDates": interim,
        }
    }


# ── principalPayment block ────────────────────────────────────────────────────

def _principal_payment(leg: LegInput):
    pp = {
        "initialPayment": leg.principal_initial,
        "finalPayment": leg.principal_final,
        "intermediatePayment": leg.principal_intermediate,
    }
    if leg.principal_schedule:
        ps = leg.principal_schedule
        schedule = {}
        if ps.initial_date is not None:
            schedule["initialPrincipalPayment"] = {
                "principalPaymentDate": {"adjustedDate": _data(ps.initial_date)},
                "payerReceiver": {"payer": ps.initial_payer, "receiver": ps.initial_receiver},
                "principalAmount": _amount(ps.initial_amount, ps.initial_currency),
            }
        if ps.final_date is not None:
            schedule["finalPrincipalPayment"] = {
                "principalPaymentDate": {"adjustedDate": _data(ps.final_date)},
                "payerReceiver": {"payer": ps.final_payer, "receiver": ps.final_receiver},
                "principalAmount": _amount(ps.final_amount, ps.final_currency),
            }
        if schedule:
            pp["principalPaymentSchedule"] = schedule
    return pp


# ── payout-leg blocks ─────────────────────────────────────────────────────────

def _calculation_period_dates(leg: LegInput, default_key: str):
    key = leg.cpd_key or default_key
    cpd = {
        "@key:external": key,
        "effectiveDate": _adjustable_date(
            leg.effective_date, leg.effective_date_bdc, leg.effective_date_bc_ref
        ),
        "terminationDate": _adjustable_date(
            leg.termination_date, leg.termination_date_bdc,
            leg.termination_date_bc_ref, leg.termination_date_adjusted
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


def _payment_dates(leg: LegInput, leg_no: int):
    key = leg.payment_dates_key
    pd = {}
    if key:
        pd["@key:external"] = key
    pd["paymentFrequency"] = {
        "periodMultiplier": leg.payment_freq_multiplier,
        "period": leg.payment_freq_period,
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


def _reset_dates(leg: LegInput, calc_key: str):
    reset_key = leg.reset_dates_key or f"resetDates-leg{calc_key}"
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
    qty_key = f"quantity-{leg_no}"
    default_cpd_key = f"calculationPeriodDates-leg{leg_no}"

    payout = {
        "@type": "cdm.product.asset.InterestRatePayout",
        "payerReceiver": {"payer": leg.payer, "receiver": leg.receiver},
    }

    # priceQuantity block
    pq_ref = {"quantitySchedule": {"@ref:scoped": qty_key}}
    if leg.quantity_reference_key:
        pq_ref["quantityReference"] = {"@ref:external": leg.quantity_reference_key}
    if leg.fx_linked_notional:
        pq_ref["quantityMultiplier"] = _fx_linked_notional(leg.fx_linked_notional)
    payout["priceQuantity"] = pq_ref

    # principalPayment
    if leg.principal_initial or leg.principal_final or leg.principal_intermediate:
        payout["principalPayment"] = _principal_payment(leg)

    # settlementTerms
    if leg.settlement_currency:
        payout["settlementTerms"] = {"settlementCurrency": _data(leg.settlement_currency)}

    # rateSpecification + tradeLot entry
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

    cpd_key = leg.cpd_key or default_cpd_key
    payout["calculationPeriodDates"] = _calculation_period_dates(leg, default_cpd_key)
    payout["paymentDates"] = _payment_dates(leg, leg_no)

    if leg.reset_freq_multiplier is not None:
        payout["resetDates"] = _reset_dates(leg, cpd_key)

    if leg.compounding_method:
        payout["compoundingMethod"] = leg.compounding_method

    if leg.cashflow_matches_parameters is not None:
        payout["cashflowRepresentation"] = {
            "cashflowsMatchParameters": leg.cashflow_matches_parameters
        }

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


def _build_taxonomy(input_data: IRSTradeInput):
    taxonomy = []
    if input_data.primary_asset_class:
        taxonomy.append({"primaryAssetClass": _data(input_data.primary_asset_class)})
    for t in input_data.additional_taxonomies:
        if t.primary_asset_class:
            taxonomy.append({"primaryAssetClass": _data(t.primary_asset_class)})
        else:
            entry = {"source": t.source, "value": {"name": _scheme_data(t.value_scheme, t.value)}}
            taxonomy.append(entry)
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
    return taxonomy


# ── main entry point ──────────────────────────────────────────────────────────

def build_irs_trade_state(input_data: IRSTradeInput) -> dict:
    """Build a real ISDA CDM TradeState dict in reference-file shape."""
    counters = {"price": 0, "index": 0, "observable": 0}
    payouts, pq_entries = [], []
    for i, leg in enumerate(input_data.legs, start=1):
        payout, pq = _build_leg(leg, i, counters)
        payouts.append(payout)
        pq_entries.append(pq)

    taxonomy = _build_taxonomy(input_data)
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

    # tradeDate — may carry a @key:external (xccy-basis references it in FX-linked notional)
    trade_date_block = {}
    if input_data.tradedate_key:
        trade_date_block["@key:external"] = input_data.tradedate_key
    trade_date_block["@data"] = input_data.trade_date
    trade["tradeDate"] = trade_date_block

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
