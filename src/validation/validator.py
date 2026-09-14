"""
validator.py
T-006: Validation engine for CDM mappings.

Takes the agent's CDM JSON output and attempts to construct
real finos-cdm Pydantic objects. If construction succeeds,
the mapping is structurally valid. If it fails, the error
message is returned so the agent can retry.

This is what makes the system self-correcting - CDM's own
Pydantic validation is the source of truth, not our opinion.
"""

import json
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional

# finos-cdm imports
from finos.cdm.base.staticdata.party.Party import Party
from finos.cdm.base.staticdata.party.PartyIdentifier import PartyIdentifier
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier
from finos.cdm.base.staticdata.identifier.AssignedIdentifier import AssignedIdentifier
from finos.cdm.observable.asset.Money import Money
from finos.cdm.base.math.UnitType import UnitType


@dataclass
class ValidationResult:
    """Result of a CDM validation attempt."""
    is_valid: bool
    errors: list
    warnings: list
    validated_objects: dict
    summary: str


def validate_trade_identifier(cdm_trade: dict) -> tuple:
    """
    Validate the trade identifier section.
    Returns (success, error_message, cdm_object)
    """
    try:
        identifiers = cdm_trade.get("tradeIdentifier", [])
        if not identifiers:
            return False, "tradeIdentifier is missing or empty", None

        first = identifiers[0]
        assigned = first.get("assignedIdentifier", [])
        if not assigned:
            return False, "assignedIdentifier is missing or empty", None

        identifier_value = assigned[0].get("identifier", "")
        if not identifier_value:
            return False, "identifier value is empty", None

        # Construct real CDM object
        cdm_obj = TradeIdentifier(
            assignedIdentifier=[
                AssignedIdentifier(identifier=identifier_value)
            ]
        )
        return True, None, cdm_obj

    except Exception as e:
        return False, str(e), None


def validate_parties(cdm_trade: dict) -> tuple:
    """
    Validate the parties section.
    Returns (success, error_message, list_of_cdm_objects)
    """
    try:
        parties = cdm_trade.get("party", [])
        if not parties:
            return False, "party list is missing or empty", None

        if len(parties) < 2:
            return False, "at least 2 parties required (our bank + counterparty)", None

        cdm_parties = []
        for i, p in enumerate(parties):
            party_ids = p.get("partyId", [])
            if not party_ids:
                return False, f"party[{i}] has no partyId", None

            identifier = party_ids[0].get("identifier", "")
            if not identifier:
                return False, f"party[{i}].partyId[0].identifier is empty", None

            name = p.get("name", "")
            cdm_party = Party(
                partyId=[PartyIdentifier(identifier=identifier)],
                name=name if name else None
            )
            cdm_parties.append(cdm_party)

        return True, None, cdm_parties

    except Exception as e:
        return False, str(e), None


def validate_product_identifier(cdm_trade: dict) -> tuple:
    """
    Validate the product identifier (ISIN/CUSIP).
    Returns (success, error_message, identifier_string)
    """
    try:
        product = cdm_trade.get("product", {})
        identifiers = product.get("productIdentifier", [])

        if not identifiers:
            return False, "product.productIdentifier is missing", None

        identifier = identifiers[0].get("identifier", "")
        source = identifiers[0].get("source", "")

        if not identifier:
            return False, "product.productIdentifier[0].identifier is empty", None

        # Validate ISIN format if source is ISIN
        if source == "ISIN":
            if len(identifier) != 12:
                return False, f"ISIN must be 12 characters, got {len(identifier)}: {identifier}", None
            if not identifier[:2].isalpha():
                return False, f"ISIN must start with 2 letters, got: {identifier[:2]}", None

        return True, None, {"identifier": identifier, "source": source}

    except Exception as e:
        return False, str(e), None


def validate_economic_terms(cdm_trade: dict) -> tuple:
    """
    Validate the economic terms section.
    Returns (success, error_message, summary_dict)
    """
    errors = []
    warnings = []
    summary = {}

    try:
        product = cdm_trade.get("product", {})
        economic_terms = product.get("economicTerms", {})

        # Check effective date
        effective = economic_terms.get("effectiveDate", {})
        eff_date = effective.get("adjustableDate", {}).get("unadjustedDate")
        if not eff_date:
            warnings.append("effectiveDate is missing - settlement date may not be available")
        else:
            summary["effectiveDate"] = eff_date

        # Check termination date
        termination = economic_terms.get("terminationDate", {})
        term_date = termination.get("adjustableDate", {}).get("unadjustedDate")
        if not term_date:
            errors.append("terminationDate is required but missing")
        else:
            summary["terminationDate"] = term_date

        # Validate maturity > settlement
        if eff_date and term_date:
            if term_date <= eff_date:
                errors.append(f"terminationDate {term_date} must be after effectiveDate {eff_date}")

        # Check payouts
        payouts = economic_terms.get("payout", [])
        if not payouts:
            errors.append("payout list is empty - no cashflow legs defined")
            return len(errors) == 0, errors, summary

        payout = payouts[0]
        irp = payout.get("interestRatePayout", {})

        # Validate coupon rate
        rate_spec = irp.get("rateSpecification", {})
        fixed_rate = rate_spec.get("fixedRate", {})
        rate_schedule = fixed_rate.get("rateSchedule", {})
        initial_value = rate_schedule.get("initialValue")

        if initial_value is None:
            errors.append("rateSchedule.initialValue (coupon rate) is missing")
        else:
            rate = float(initial_value)
            if rate > 1.0:
                errors.append(f"coupon rate {rate} looks like a percentage - should be decimal (e.g. 0.0425 not 4.25)")
            elif rate <= 0:
                errors.append(f"coupon rate {rate} must be positive")
            else:
                summary["couponRate"] = rate

        # Validate principal amount
        principal = irp.get("principalPayment", {}).get("principalAmount", {})
        amount = principal.get("amount")
        currency = principal.get("unit", {}).get("currency")

        if not amount:
            errors.append("principalPayment.principalAmount.amount is missing")
        else:
            try:
                amt = float(amount)
                if amt <= 0:
                    errors.append(f"principalAmount {amt} must be positive")
                else:
                    summary["principalAmount"] = amt
                    # Construct real CDM Money object as validation
                    money = Money(
                        value=Decimal(str(amount)),
                        unit=UnitType(currency=currency if currency else "USD")
                    )
                    summary["cdmMoneyObject"] = "valid"
            except Exception as e:
                errors.append(f"principalAmount validation failed: {str(e)}")

        if not currency:
            warnings.append("currency is missing - defaulting to USD")
        else:
            if len(currency) != 3 or not currency.isalpha():
                errors.append(f"currency must be 3-letter ISO code, got: {currency}")
            else:
                summary["currency"] = currency

        # Validate day count fraction
        day_count = irp.get("dayCountFraction")
        valid_day_counts = [
            "ACT/ACT.ICMA", "ACT/ACT.ISDA", "ACT/ACT.ISMA", "ACT/ACT.AFB",
            "ACT/360", "ACT/365.FIXED", "ACT/365L", "30/360", "30E/360",
            "30E/360.ISDA", "1/1"
        ]
        if not day_count:
            errors.append("dayCountFraction is missing")
        elif day_count not in valid_day_counts:
            errors.append(f"dayCountFraction '{day_count}' not recognised. Valid values: {valid_day_counts}")
        else:
            summary["dayCountFraction"] = day_count

        # Validate payer/receiver
        payer_receiver = irp.get("payerReceiver", {})
        payer = payer_receiver.get("payer")
        receiver = payer_receiver.get("receiver")
        valid_roles = ["Party1", "Party2"]
        if not payer or payer not in valid_roles:
            errors.append(f"payerReceiver.payer must be Party1 or Party2, got: {payer}")
        if not receiver or receiver not in valid_roles:
            errors.append(f"payerReceiver.receiver must be Party1 or Party2, got: {receiver}")
        if payer and receiver and payer == receiver:
            errors.append("payer and receiver cannot be the same party")

        return len(errors) == 0, errors, summary

    except Exception as e:
        return False, [str(e)], summary


def validate(cdm_json: dict) -> ValidationResult:
    """
    Main validation function.
    Takes the agent's cdmTrade dict and validates all sections.
    Returns a ValidationResult with pass/fail, errors, and warnings.
    """
    all_errors = []
    all_warnings = []
    validated = {}

    # 1. Validate trade identifier
    ok, err, obj = validate_trade_identifier(cdm_json)
    if ok:
        validated["tradeIdentifier"] = str(obj.assignedIdentifier[0].identifier)
    else:
        all_errors.append(f"[tradeIdentifier] {err}")

    # 2. Validate parties
    ok, err, obj = validate_parties(cdm_json)
    if ok:
        validated["parties"] = f"{len(obj)} parties validated"
    else:
        all_errors.append(f"[parties] {err}")

    # 3. Validate product identifier
    ok, err, obj = validate_product_identifier(cdm_json)
    if ok:
        validated["productIdentifier"] = obj
    else:
        all_errors.append(f"[productIdentifier] {err}")

    # 4. Validate economic terms
    ok, errors, summary = validate_economic_terms(cdm_json)
    if ok:
        validated["economicTerms"] = summary
    else:
        for e in errors:
            all_errors.append(f"[economicTerms] {e}")

    is_valid = len(all_errors) == 0

    if is_valid:
        summary_text = "VALID - all CDM sections passed validation"
    else:
        summary_text = f"INVALID - {len(all_errors)} error(s) found"

    return ValidationResult(
        is_valid=is_valid,
        errors=all_errors,
        warnings=all_warnings,
        validated_objects=validated,
        summary=summary_text
    )


def validate_from_agent_output(agent_output: dict) -> ValidationResult:
    """
    Convenience wrapper - takes the full agent output dict
    (which contains cdmTrade as a key) and validates it.
    """
    cdm_trade = agent_output.get("cdmTrade", {})
    if not cdm_trade:
        return ValidationResult(
            is_valid=False,
            errors=["No cdmTrade found in agent output"],
            warnings=[],
            validated_objects={},
            summary="INVALID - no cdmTrade in output"
        )
    return validate(cdm_trade)


if __name__ == "__main__":

    # Test with a known good CDM output from the agent
    sample_cdm = {
        "tradeIdentifier": [{"assignedIdentifier": [{"identifier": "TB-20260914-001"}]}],
        "tradeDate": {"date": "2026-09-14"},
        "party": [
            {"partyId": [{"identifier": "OUR-BANK", "identifierType": "INTERNAL"}], "name": "OUR BANK PLC", "role": "OUR_BANK"},
            {"partyId": [{"identifier": "JPMORGAN", "identifierType": "INTERNAL"}], "name": "JPMORGAN", "role": "COUNTERPARTY"}
        ],
        "product": {
            "productType": "Rates.GovernmentBond",
            "productIdentifier": [{"identifier": "US91282CJL54", "source": "ISIN"}],
            "economicTerms": {
                "effectiveDate": {"adjustableDate": {"unadjustedDate": "2026-09-16"}},
                "terminationDate": {"adjustableDate": {"unadjustedDate": "2034-08-15"}},
                "payout": [{
                    "interestRatePayout": {
                        "payerReceiver": {"payer": "Party2", "receiver": "Party1"},
                        "rateSpecification": {"fixedRate": {"rateSchedule": {"initialValue": 0.0425}}},
                        "dayCountFraction": "ACT/ACT.ICMA",
                        "calculationPeriodDates": {
                            "terminationDate": {"adjustableDate": {"unadjustedDate": "2034-08-15"}},
                            "calculationPeriodFrequency": {"period": "M", "periodMultiplier": 6}
                        },
                        "principalPayment": {
                            "principalAmount": {"amount": 10000000, "unit": {"currency": "USD"}}
                        }
                    }
                }]
            }
        },
        "dates": {"tradeDate": "2026-09-14", "settlementDate": "2026-09-16", "maturityDate": "2034-08-15"}
    }

    print("=" * 60)
    print("CDM VALIDATION ENGINE - T-006 Test")
    print("=" * 60)

    print("\nTest 1: Valid CDM trade (should PASS)")
    result = validate(sample_cdm)
    print("Result: " + result.summary)
    if result.errors:
        print("Errors:")
        for e in result.errors:
            print("  - " + e)
    print("Validated objects:")
    for k, v in result.validated_objects.items():
        print("  " + k + ": " + str(v))

    print("\nTest 2: Bad coupon rate - percentage instead of decimal (should FAIL)")
    bad_cdm = json.loads(json.dumps(sample_cdm))
    bad_cdm["product"]["economicTerms"]["payout"][0]["interestRatePayout"]["rateSpecification"]["fixedRate"]["rateSchedule"]["initialValue"] = 4.25
    result2 = validate(bad_cdm)
    print("Result: " + result2.summary)
    for e in result2.errors:
        print("  Error: " + e)

    print("\nTest 3: Invalid ISIN - wrong length (should FAIL)")
    bad_cdm2 = json.loads(json.dumps(sample_cdm))
    bad_cdm2["product"]["productIdentifier"][0]["identifier"] = "US123"
    result3 = validate(bad_cdm2)
    print("Result: " + result3.summary)
    for e in result3.errors:
        print("  Error: " + e)

    print("\nTest 4: Maturity before settlement (should FAIL)")
    bad_cdm3 = json.loads(json.dumps(sample_cdm))
    bad_cdm3["product"]["economicTerms"]["terminationDate"]["adjustableDate"]["unadjustedDate"] = "2025-01-01"
    result4 = validate(bad_cdm3)
    print("Result: " + result4.summary)
    for e in result4.errors:
        print("  Error: " + e)
