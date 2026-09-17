"""
agent_loop.py
T-007: End-to-end pipeline with validation retry loop.
Plan-Act-Reflect loop connecting all components.
"""

import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ingestion.format_detector import normalize
from validation.validator import validate_from_agent_output

MAX_RETRIES = 3

GOVERNMENT_BOND_SCHEMA = """
You are a financial data mapping agent specializing in capital markets.
Map legacy bank trade data into the ISDA Common Domain Model (CDM).

PRODUCT: Government Bond (Fixed Rate)

TARGET CDM FIELDS:
tradeIdentifier[0].assignedIdentifier[0].identifier - Unique trade ID
tradeDate.date - Date trade was executed YYYY-MM-DD
party[1].partyId[0].identifier - Counterparty identifier
product.productIdentifier[0].identifier - ISIN CUSIP or SEDOL
product.productIdentifier[0].source - ID scheme ISIN CUSIP SEDOL
product.economicTerms.effectiveDate.adjustableDate.unadjustedDate - Settlement date
product.economicTerms.terminationDate.adjustableDate.unadjustedDate - Maturity date
product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.amount - Face value
product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.unit.currency - Currency
product.economicTerms.payout[0].interestRatePayout.rateSpecification.fixedRate.rateSchedule.initialValue - Coupon rate as decimal
product.economicTerms.payout[0].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency - Coupon frequency
product.economicTerms.payout[0].interestRatePayout.dayCountFraction - Day count convention
product.economicTerms.payout[0].interestRatePayout.payerReceiver - Payer and receiver roles

TRANSFORMATION RULES:
1. Coupon rate: if value > 1.0, divide by 100. Example: 4.25 becomes 0.0425
2. SEMI or S or SEMI-ANNUAL maps to period=M periodMultiplier=6
3. ANNUAL or A maps to period=Y periodMultiplier=1
4. QUARTERLY or Q maps to period=M periodMultiplier=3
5. ACT/ACT or ACT/ACT ICMA maps to ACT/ACT.ICMA
6. BUY or B or PURCHASE maps to payer=Party2 receiver=Party1
7. SELL or SALE maps to payer=Party1 receiver=Party2
8. Date YYYYMMDD converts to YYYY-MM-DD
9. Currency: infer from ISIN prefix if missing. US=USD GB=GBP DE=EUR

CRITICAL: Your response must be a raw JSON object. No markdown. No backticks. No ```json. Just the JSON object starting with { and ending with }.

Required structure:
{"cdmTrade":{"tradeIdentifier":[{"assignedIdentifier":[{"identifier":"..."}]}],"tradeDate":{"date":"YYYY-MM-DD"},"party":[{"partyId":[{"identifier":"OUR-BANK","identifierType":"INTERNAL"}],"name":"OUR BANK PLC","role":"OUR_BANK"},{"partyId":[{"identifier":"...","identifierType":"INTERNAL"}],"name":"...","role":"COUNTERPARTY"}],"product":{"productType":"Rates.GovernmentBond","productIdentifier":[{"identifier":"...","source":"ISIN"}],"economicTerms":{"effectiveDate":{"adjustableDate":{"unadjustedDate":"YYYY-MM-DD"}},"terminationDate":{"adjustableDate":{"unadjustedDate":"YYYY-MM-DD"}},"payout":[{"interestRatePayout":{"payerReceiver":{"payer":"Party2","receiver":"Party1"},"rateSpecification":{"fixedRate":{"rateSchedule":{"initialValue":0.0000}}},"dayCountFraction":"ACT/ACT.ICMA","calculationPeriodDates":{"terminationDate":{"adjustableDate":{"unadjustedDate":"YYYY-MM-DD"}},"calculationPeriodFrequency":{"period":"M","periodMultiplier":6}},"principalPayment":{"principalAmount":{"amount":0,"unit":{"currency":"USD"}}}}}]}},"dates":{"tradeDate":"YYYY-MM-DD","settlementDate":"YYYY-MM-DD","maturityDate":"YYYY-MM-DD"}},"fieldMapping":[{"sourceField":"...","cdmPath":"...","confidence":"HIGH","transformation":"..."}],"mappingNotes":[],"missingFields":[]}
"""


def strip_markdown(text):
    """Remove markdown code fences from agent response."""
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                return part
    return text


def run_agent_call(client, normalized_fields, previous_errors=None):
    """Single call to the mapping agent."""
    fields_text = json.dumps(normalized_fields, indent=2)

    if previous_errors:
        error_text = "\n".join(["- " + e for e in previous_errors])
        user_message = (
            "Map this legacy trade data to CDM format.\n\n"
            "SOURCE DATA:\n" + fields_text + "\n\n"
            "VALIDATION ERRORS TO FIX:\n" + error_text + "\n\n"
            "Return raw JSON only. No markdown. No backticks. Start your response with {"
        )
    else:
        user_message = (
            "Map this legacy trade data to CDM format.\n\n"
            "SOURCE DATA:\n" + fields_text + "\n\n"
            "Return raw JSON only. No markdown. No backticks. Start your response with {"
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=GOVERNMENT_BOND_SCHEMA,
        messages=[{"role": "user", "content": user_message}]
    )

    raw_text = strip_markdown(response.content[0].text)

    try:
        parsed = json.loads(raw_text)
        # If agent returned the trade directly without cdmTrade wrapper
        if "cdmTrade" not in parsed and "tradeIdentifier" in parsed:
            parsed = {
                "cdmTrade": parsed,
                "fieldMapping": [],
                "mappingNotes": [],
                "missingFields": []
            }
        return parsed
    except json.JSONDecodeError as e:
        return {"error": "JSON parse failed: " + str(e), "rawResponse": raw_text[:200]}


def run_pipeline(raw_input, label="trade"):
    """Full end-to-end pipeline with Plan-Act-Reflect loop."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    started_at = datetime.now().isoformat()

    print("\n" + "=" * 60)
    print("PIPELINE: " + label)
    print("=" * 60)

    # PLAN
    print("\n[PLAN] Detecting format and normalizing...")
    normalized = normalize(raw_input)
    source_format = normalized.get("_format", "UNKNOWN")
    field_count = len(normalized) - 1
    print("  Format: " + source_format)
    print("  Fields: " + str(field_count))

    attempts = []
    final_result = None
    validation_result = None
    previous_errors = None

    # ACT + REFLECT loop
    for attempt_num in range(1, MAX_RETRIES + 1):
        print("\n[ACT] Attempt " + str(attempt_num) + " of " + str(MAX_RETRIES) + "...")

        agent_output = run_agent_call(client, normalized, previous_errors)

        if "error" in agent_output:
            print("  Agent error: " + agent_output["error"])
            attempts.append({"attempt": attempt_num, "status": "AGENT_ERROR", "error": agent_output["error"], "errors": [agent_output["error"]], "warnings": []})
            previous_errors = [agent_output["error"]]
            continue

        print("[REFLECT] Validating CDM output...")
        validation_result = validate_from_agent_output(agent_output)

        attempt_record = {
            "attempt": attempt_num,
            "status": "VALID" if validation_result.is_valid else "INVALID",
            "errors": validation_result.errors,
            "warnings": validation_result.warnings
        }
        attempts.append(attempt_record)

        if validation_result.is_valid:
            print("  Validation PASSED on attempt " + str(attempt_num))
            final_result = agent_output
            break
        else:
            print("  Validation FAILED - " + str(len(validation_result.errors)) + " error(s):")
            for e in validation_result.errors:
                print("    - " + e)
            previous_errors = validation_result.errors

            if attempt_num < MAX_RETRIES:
                print("  Retrying with error feedback...")
            else:
                print("  Max retries reached - flagging for human review")
                final_result = agent_output

    pipeline_result = {
        "label": label,
        "sourceFormat": source_format,
        "fieldCount": field_count,
        "totalAttempts": len(attempts),
        "finalStatus": "VALID" if (validation_result and validation_result.is_valid) else "NEEDS_REVIEW",
        "attempts": attempts,
        "cdmTrade": final_result.get("cdmTrade", {}) if final_result else {},
        "fieldMapping": final_result.get("fieldMapping", []) if final_result else [],
        "mappingNotes": final_result.get("mappingNotes", []) if final_result else [],
        "missingFields": final_result.get("missingFields", []) if final_result else [],
        "startedAt": started_at,
        "completedAt": datetime.now().isoformat()
    }

    return pipeline_result


def print_summary(result):
    """Print a clean summary of the pipeline result."""
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY: " + result["label"])
    print("=" * 60)
    print("  Format:   " + result["sourceFormat"])
    print("  Status:   " + result["finalStatus"])
    print("  Attempts: " + str(result["totalAttempts"]))

    for a in result["attempts"]:
        status = "PASS" if a["status"] == "VALID" else "FAIL"
        print("  Attempt " + str(a["attempt"]) + ": " + status)
        if a.get("errors"):
            for e in a["errors"]:
                print("    Error: " + e)

    if result["finalStatus"] == "VALID":
        cdm = result.get("cdmTrade", {})
        product = cdm.get("product", {})
        identifiers = product.get("productIdentifier", [{}])
        isin = identifiers[0].get("identifier", "unknown") if identifiers else "unknown"
        terms = product.get("economicTerms", {})
        payouts = terms.get("payout", [{}])
        irp = payouts[0].get("interestRatePayout", {}) if payouts else {}
        rate = irp.get("rateSpecification", {}).get("fixedRate", {}).get("rateSchedule", {}).get("initialValue", "?")
        maturity = terms.get("terminationDate", {}).get("adjustableDate", {}).get("unadjustedDate", "?")
        print("\n  CDM Summary:")
        print("  ISIN:     " + isin)
        print("  Rate:     " + str(rate))
        print("  Maturity: " + maturity)


if __name__ == "__main__":

    sample_a = "TRADE_NUM|SEC_ID|ISIN|SEC_DESC|SIDE|QTY|PRICE|YIELD|ACCRUED_INT|SETTLE_AMT|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT\nTB-20260914-001|UST-10Y|US91282CJL54|US TREASURY 4.25% 08/2034|BUY|10000000|98.750|4.42|21250.00|9896250.00|JPMORGAN|2026-09-14|2026-09-16|2034-08-15|4.25|SEMI|ACT/ACT"

    sample_b = '{"deal_id":"BOND-2026-8821","security":"US91282CJL54","description":"US TREASURY NOTE 4.25 08/15/2034","transaction_type":"PURCHASE","face_value":5000000,"currency":"USD","coupon_rate":4.25,"payment_frequency":"SEMI-ANNUAL","day_count_basis":"ACT/ACT ICMA","trade_date":"2026-09-14","settlement_date":"2026-09-16","maturity_date":"2034-08-15","counterparty":"GOLDMAN SACHS","counterparty_lei":"784F5XWPLTWKTBV3E584"}'

    sample_c = "TRADE_ID  ISIN          SIDE QTY        PRICE    COUPON FREQ MAT_DATE   CPTY\nTB0091234 US91282CJL54  B    10000000   98.7500  4.2500 S    20340815   BARC"

    print("CDM MAPPING AGENT LOOP - T-007 Test")
    print("Testing all 3 sample formats end-to-end with validation")

    results = []

    result_a = run_pipeline(sample_a, "Sample A - pipe-delimited")
    print_summary(result_a)
    results.append(result_a)

    result_b = run_pipeline(sample_b, "Sample B - JSON")
    print_summary(result_b)
    results.append(result_b)

    result_c = run_pipeline(sample_c, "Sample C - fixed-width")
    print_summary(result_c)
    results.append(result_c)

    print("\n" + "=" * 60)
    print("FINAL REPORT - All 3 Samples")
    print("=" * 60)
    passed = sum(1 for r in results if r["finalStatus"] == "VALID")
    print("Passed: " + str(passed) + " / " + str(len(results)))
    for r in results:
        status = "PASS" if r["finalStatus"] == "VALID" else "FAIL"
        print("  " + status + " | " + r["label"] + " | " + str(r["totalAttempts"]) + " attempt(s)")
