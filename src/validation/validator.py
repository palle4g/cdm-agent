"""
validator.py
T-006: Validation engine for CDM mappings (product-aware).

Dispatches to the correct validation logic based on product_type, so an
FX Forward's payoutLeg1/2 structure isn't wrongly checked against government
bond rules, and vice versa. Shared checks (trade identifier, parties) apply
to every product; product-specific checks branch by product_type.
"""

import json
from decimal import Decimal
from dataclasses import dataclass

from finos.cdm.base.staticdata.party.Party import Party
from finos.cdm.base.staticdata.party.PartyIdentifier import PartyIdentifier
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier
from finos.cdm.base.staticdata.identifier.AssignedIdentifier import AssignedIdentifier
from finos.cdm.observable.asset.Money import Money
from finos.cdm.base.math.UnitType import UnitType


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list
    warnings: list
    validated_objects: dict
    summary: str


VALID_DAY_COUNTS = [
    "ACT/ACT.ICMA", "ACT/ACT.ISDA", "ACT/ACT.ISMA", "ACT/ACT.AFB",
    "ACT/360", "ACT/365.FIXED", "ACT/365L", "30/360", "30E/360",
    "30E/360.ISDA", "1/1"
]
VALID_ROLES = ["Party1", "Party2"]


# ---------- SHARED CHECKS (apply to every product) ----------

def validate_trade_identifier(cdm_trade):
    try:
        identifiers = cdm_trade.get("tradeIdentifier", [])
        if not identifiers:
            return False, "tradeIdentifier is missing or empty", None
        assigned = identifiers[0].get("assignedIdentifier", [])
        if not assigned:
            return False, "assignedIdentifier is missing or empty", None
        identifier_value = assigned[0].get("identifier", "")
        if not identifier_value:
            return False, "identifier value is empty", None
        cdm_obj = TradeIdentifier(assignedIdentifier=[AssignedIdentifier(identifier=identifier_value)])
        return True, None, cdm_obj
    except Exception as e:
        return False, str(e), None


def validate_parties(cdm_trade):
    try:
        parties = cdm_trade.get("party", [])
        if not parties:
            return False, "party list is missing or empty", None
        if len(parties) < 2:
            return False, "at least 2 parties required", None
        cdm_parties = []
        for i, p in enumerate(parties):
            party_ids = p.get("partyId", [])
            if not party_ids:
                return False, "party[" + str(i) + "] has no partyId", None
            identifier = party_ids[0].get("identifier", "")
            if not identifier:
                return False, "party[" + str(i) + "].partyId[0].identifier is empty", None
            name = p.get("name", "")
            # finos-cdm quirk: passing name=None explicitly raises an internal
            # error; omitting the kwarg entirely when there's no name works fine.
            if name:
                cdm_party = Party(partyId=[PartyIdentifier(identifier=identifier)], name=name)
            else:
                cdm_party = Party(partyId=[PartyIdentifier(identifier=identifier)])
            cdm_parties.append(cdm_party)
        return True, None, cdm_parties
    except Exception as e:
        return False, str(e), None


def _validate_money(amount, currency, label):
    """Shared amount/currency validation used by bond and swap legs."""
    errors = []
    summary = {}
    if not amount:
        errors.append(label + " amount is missing")
    else:
        try:
            amt = float(amount)
            if amt <= 0:
                errors.append(label + " amount " + str(amt) + " must be positive")
            else:
                summary[label + "Amount"] = amt
                Money(value=Decimal(str(amount)), unit=UnitType(currency=currency if currency else "USD"))
        except Exception as e:
            errors.append(label + " amount validation failed: " + str(e))
    if not currency:
        errors.append(label + " currency is missing")
    elif len(currency) != 3 or not currency.isalpha():
        errors.append(label + " currency must be 3-letter ISO code, got: " + str(currency))
    else:
        summary[label + "Currency"] = currency
    return errors, summary


def _validate_day_count(day_count, label):
    if not day_count:
        return [label + " dayCountFraction is missing"], {}
    if day_count not in VALID_DAY_COUNTS:
        return [label + " dayCountFraction '" + day_count + "' not recognised"], {}
    return [], {label + "DayCount": day_count}


def _validate_rate(rate, label):
    if rate is None:
        return [label + " rate is missing"], {}
    r = float(rate)
    if r > 1.0:
        return [label + " rate " + str(r) + " looks like a percentage - should be decimal"], {}
    if r < 0:
        return [label + " rate " + str(r) + " cannot be negative"], {}
    return [], {label + "Rate": r}


def _validate_payer_receiver(pr, label):
    payer = pr.get("payer")
    receiver = pr.get("receiver")
    errors = []
    if not payer or payer not in VALID_ROLES:
        errors.append(label + " payerReceiver.payer must be Party1 or Party2, got: " + str(payer))
    if not receiver or receiver not in VALID_ROLES:
        errors.append(label + " payerReceiver.receiver must be Party1 or Party2, got: " + str(receiver))
    if payer and receiver and payer == receiver:
        errors.append(label + " payer and receiver cannot be the same party")
    return errors


# ---------- PRODUCT-SPECIFIC CHECKS ----------

def validate_government_bond(cdm_trade):
    errors = []
    summary = {}
    product = cdm_trade.get("product", {})

    identifiers = product.get("productIdentifier", [])
    if not identifiers or not identifiers[0].get("identifier"):
        errors.append("product.productIdentifier is missing")
    else:
        identifier = identifiers[0]["identifier"]
        source = identifiers[0].get("source", "")
        if source == "ISIN" and (len(identifier) != 12 or not identifier[:2].isalpha()):
            errors.append("ISIN must be 12 characters starting with 2 letters, got: " + identifier)
        else:
            summary["productIdentifier"] = identifier

    terms = product.get("economicTerms", {})
    eff_date = terms.get("effectiveDate", {}).get("adjustableDate", {}).get("unadjustedDate")
    term_date = terms.get("terminationDate", {}).get("adjustableDate", {}).get("unadjustedDate")
    if not term_date:
        errors.append("terminationDate is required but missing")
    if eff_date and term_date and term_date <= eff_date:
        errors.append("terminationDate " + term_date + " must be after effectiveDate " + eff_date)

    payouts = terms.get("payout", [])
    if not payouts:
        errors.append("payout list is empty")
        return errors, summary
    irp = payouts[0].get("interestRatePayout", {})

    rate = irp.get("rateSpecification", {}).get("fixedRate", {}).get("rateSchedule", {}).get("initialValue")
    e, s = _validate_rate(rate, "coupon")
    errors += e
    summary.update(s)

    principal = irp.get("principalPayment", {}).get("principalAmount", {})
    e, s = _validate_money(principal.get("amount"), principal.get("unit", {}).get("currency"), "principal")
    errors += e
    summary.update(s)

    e, s = _validate_day_count(irp.get("dayCountFraction"), "coupon")
    errors += e
    summary.update(s)

    errors += _validate_payer_receiver(irp.get("payerReceiver", {}), "coupon")

    return errors, summary


def validate_fx_forward(cdm_trade):
    errors = []
    summary = {}
    product = cdm_trade.get("product", {})
    terms = product.get("economicTerms", {})

    leg1 = terms.get("payoutLeg1", {})
    leg2 = terms.get("payoutLeg2", {})

    if not leg1 or not leg2:
        errors.append("Both payoutLeg1 and payoutLeg2 are required for an FX forward")
        return errors, summary

    for leg_name, leg in [("leg1", leg1), ("leg2", leg2)]:
        amount = leg.get("amount", {})
        e, s = _validate_money(amount.get("value"), amount.get("currency"), leg_name)
        errors += e
        summary.update(s)
        direction = leg.get("direction")
        if direction not in ["RECEIVE", "PAY"]:
            errors.append(leg_name + " direction must be RECEIVE or PAY, got: " + str(direction))
        else:
            summary[leg_name + "Direction"] = direction

    if leg1.get("direction") and leg1.get("direction") == leg2.get("direction"):
        errors.append("payoutLeg1 and payoutLeg2 cannot have the same direction - one must RECEIVE, one must PAY")

    settlement_date = terms.get("settlementDate")
    if not settlement_date:
        errors.append("settlementDate is missing - required for FX forwards, no safe default exists")
    else:
        summary["settlementDate"] = settlement_date

    return errors, summary


def validate_interest_rate_swap(cdm_trade):
    errors = []
    summary = {}
    product = cdm_trade.get("product", {})
    terms = product.get("economicTerms", {})

    eff_date = terms.get("effectiveDate", {}).get("adjustableDate", {}).get("unadjustedDate")
    term_date = terms.get("terminationDate", {}).get("adjustableDate", {}).get("unadjustedDate")
    if not eff_date:
        errors.append("effectiveDate is required but missing")
    if not term_date:
        errors.append("terminationDate is required but missing")
    if eff_date and term_date and term_date <= eff_date:
        errors.append("terminationDate " + term_date + " must be after effectiveDate " + eff_date)

    payouts = terms.get("payout", [])
    if len(payouts) < 2:
        errors.append("Interest rate swap requires 2 payout legs (fixed and floating), found " + str(len(payouts)))
        return errors, summary

    fixed_leg = payouts[0].get("interestRatePayout", {})
    float_leg = payouts[1].get("interestRatePayout", {})

    # Fixed leg checks
    rate = fixed_leg.get("rateSpecification", {}).get("fixedRate", {}).get("rateSchedule", {}).get("initialValue")
    e, s = _validate_rate(rate, "fixedLeg")
    errors += e
    summary.update(s)

    principal = fixed_leg.get("principalPayment", {}).get("principalAmount", {})
    e, s = _validate_money(principal.get("amount"), principal.get("unit", {}).get("currency"), "notional")
    errors += e
    summary.update(s)

    e, s = _validate_day_count(fixed_leg.get("dayCountFraction"), "fixedLeg")
    errors += e
    summary.update(s)

    errors += _validate_payer_receiver(fixed_leg.get("payerReceiver", {}), "fixedLeg")

    # Floating leg checks
    float_index = float_leg.get("rateSpecification", {}).get("floatingRate", {}).get("index")
    if not float_index:
        errors.append("floatingLeg index (e.g. SOFR, EURIBOR) is missing")
    else:
        summary["floatIndex"] = float_index

    spread = float_leg.get("rateSpecification", {}).get("floatingRate", {}).get("spread")
    if spread is None:
        errors.append("floatingLeg spread is missing - must be explicit, even if 0.0")
    elif float(spread) > 1.0:
        errors.append("floatingLeg spread " + str(spread) + " looks like a percentage - should be decimal")
    else:
        summary["floatSpread"] = spread

    e, s = _validate_day_count(float_leg.get("dayCountFraction"), "floatingLeg")
    errors += e
    summary.update(s)

    return errors, summary


# ---------- DISPATCH ----------

_PRODUCT_VALIDATORS = {
    "GovernmentBond": validate_government_bond,
    "FXForward": validate_fx_forward,
    "InterestRateSwap": validate_interest_rate_swap,
}


def validate(cdm_json, product_type=None):
    """
    Main validation entry point.
    Runs shared checks (trade id, parties) for every product, then dispatches
    to the product-specific check based on product_type. If product_type is
    not given or not recognised, only shared checks run.
    """
    all_errors = []
    validated = {}

    ok, err, obj = validate_trade_identifier(cdm_json)
    if ok:
        validated["tradeIdentifier"] = str(obj.assignedIdentifier[0].identifier)
    else:
        all_errors.append("[tradeIdentifier] " + str(err))

    ok, err, obj = validate_parties(cdm_json)
    if ok:
        validated["parties"] = str(len(obj)) + " parties validated"
    else:
        all_errors.append("[parties] " + str(err))

    product_validator = _PRODUCT_VALIDATORS.get(product_type)
    if product_validator:
        errors, summary = product_validator(cdm_json)
        for e in errors:
            all_errors.append("[" + product_type + "] " + e)
        validated.update(summary)
    else:
        all_errors.append("[product] Unknown or unspecified product_type '" + str(product_type) +
                           "' - only shared checks (trade id, parties) were run")

    is_valid = len(all_errors) == 0
    summary_text = "VALID - all CDM sections passed validation" if is_valid else "INVALID - " + str(len(all_errors)) + " error(s) found"

    return ValidationResult(is_valid=is_valid, errors=all_errors, warnings=[], validated_objects=validated, summary=summary_text)


def validate_from_agent_output(agent_output, product_type=None):
    """Convenience wrapper - validates the cdmTrade inside a full agent output dict."""
    cdm_trade = agent_output.get("cdmTrade", {})
    if not cdm_trade:
        return ValidationResult(False, ["No cdmTrade found in agent output"], [], {}, "INVALID - no cdmTrade in output")
    if product_type is None:
        product_type = agent_output.get("_productType")
    return validate(cdm_trade, product_type=product_type)


if __name__ == "__main__":
    sample_bond = {
        "tradeIdentifier": [{"assignedIdentifier": [{"identifier": "TB-001"}]}],
        "party": [
            {"partyId": [{"identifier": "OUR-BANK"}], "name": "OUR BANK"},
            {"partyId": [{"identifier": "JPM"}], "name": "JPMORGAN"}
        ],
        "product": {
            "productIdentifier": [{"identifier": "US91282CJL54", "source": "ISIN"}],
            "economicTerms": {
                "effectiveDate": {"adjustableDate": {"unadjustedDate": "2026-09-16"}},
                "terminationDate": {"adjustableDate": {"unadjustedDate": "2034-08-15"}},
                "payout": [{"interestRatePayout": {
                    "payerReceiver": {"payer": "Party2", "receiver": "Party1"},
                    "rateSpecification": {"fixedRate": {"rateSchedule": {"initialValue": 0.0425}}},
                    "dayCountFraction": "ACT/ACT.ICMA",
                    "principalPayment": {"principalAmount": {"amount": 10000000, "unit": {"currency": "USD"}}}
                }}]
            }
        }
    }
    print("Test 1: Bond validation (should PASS)")
    r = validate(sample_bond, product_type="GovernmentBond")
    print(r.summary)

    sample_fx = {
        "tradeIdentifier": [{"assignedIdentifier": [{"identifier": "FX-001"}]}],
        "party": [{"partyId": [{"identifier": "OUR-BANK"}]}, {"partyId": [{"identifier": "CPTY"}]}],
        "product": {"economicTerms": {
            "payoutLeg1": {"direction": "RECEIVE", "amount": {"value": 1000000, "currency": "EUR"}},
            "payoutLeg2": {"direction": "PAY", "amount": {"value": 1085000, "currency": "USD"}},
            "settlementDate": "2026-12-18"
        }}
    }
    print("\nTest 2: FX Forward validation (should PASS)")
    r = validate(sample_fx, product_type="FXForward")
    print(r.summary)

    print("\nTest 3: FX Forward with same direction on both legs (should FAIL)")
    bad_fx = json.loads(json.dumps(sample_fx))
    bad_fx["product"]["economicTerms"]["payoutLeg2"]["direction"] = "RECEIVE"
    r = validate(bad_fx, product_type="FXForward")
    print(r.summary)
    for e in r.errors:
        print("  " + e)
