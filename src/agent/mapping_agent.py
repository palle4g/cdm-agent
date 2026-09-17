"""
mapping_agent.py
T-005: The CDM mapping agent.
Updated: Added reason and missingSourceField to inferred fieldMapping entries.
"""

import json
import os
from dotenv import load_dotenv
import anthropic
import sys

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ingestion.format_detector import normalize

GOVERNMENT_BOND_SCHEMA = """
You are a financial data mapping agent specializing in capital markets.
Your job is to map legacy bank trade data into the ISDA Common Domain Model (CDM).

PRODUCT: Government Bond (Fixed Rate)

TARGET CDM FIELDS - map every source field to one of these exact paths:

tradeIdentifier[0].assignedIdentifier[0].identifier - Unique trade ID
tradeDate.date - Date trade was executed YYYY-MM-DD
party[1].partyId[0].identifier - Counterparty identifier
product.productIdentifier[0].identifier - ISIN CUSIP or SEDOL value
product.productIdentifier[0].source - ID scheme: ISIN, CUSIP, or SEDOL
product.economicTerms.effectiveDate.adjustableDate.unadjustedDate - Settlement date
product.economicTerms.terminationDate.adjustableDate.unadjustedDate - Maturity date
product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.amount - Face value
product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.unit.currency - Currency
product.economicTerms.payout[0].interestRatePayout.rateSpecification.fixedRate.rateSchedule.initialValue - Coupon rate as decimal
product.economicTerms.payout[0].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency - Coupon frequency
product.economicTerms.payout[0].interestRatePayout.dayCountFraction - Day count convention
product.economicTerms.payout[0].interestRatePayout.payerReceiver - Payer and receiver roles

CRITICAL TRANSFORMATION RULES:
1. Coupon rate: if value > 1.0, divide by 100. Example: 4.25 becomes 0.0425
2. SEMI or S or SEMI-ANNUAL maps to period=M periodMultiplier=6
3. ANNUAL or A maps to period=Y periodMultiplier=1
4. QUARTERLY or Q maps to period=M periodMultiplier=3
5. ACT/ACT or ACT/ACT ICMA maps to ACT/ACT.ICMA
6. BUY or B or PURCHASE maps to payer=Party2 receiver=Party1
7. SELL or SALE maps to payer=Party1 receiver=Party2
8. Date format YYYYMMDD with no dashes converts to YYYY-MM-DD
9. Currency: if not present infer from ISIN prefix. US=USD GB=GBP DE=EUR JP=JPY
10. SECURITY IDENTIFIER RULE - always produce TWO separate fieldMapping entries for any security identifier field (ISIN, CUSIP, SEDOL, SEC_ID, security, BOND_ID etc):
    Entry 1: sourceField=<FIELD_NAME>, cdmPath=product.productIdentifier[0].identifier, confidence=HIGH, missingSourceField=false
    Entry 2: sourceField=<FIELD_NAME> (scheme), cdmPath=product.productIdentifier[0].source, confidence=HIGH, missingSourceField=false,
             reason="Scheme inferred from field name and identifier format. Field name contains ISIN/CUSIP/SEDOL or identifier matches known format (12-char alphanumeric = ISIN)."
11. CURRENCY INFERENCE RULE - if no explicit currency field exists in source data, produce this fieldMapping entry:
    sourceField="currency (inferred)"
    cdmPath=product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.unit.currency
    confidence=MEDIUM
    missingSourceField=true
    transformation="inferred from ISIN country prefix"
    reason="No explicit currency field present in source data. Currency derived from ISIN country prefix (US=USD, GB=GBP, DE=EUR, JP=JPY). Human review recommended if ISIN country does not match settlement currency."
    This entry is REQUIRED even when currency is not in source. Never omit it.
12. DAY COUNT INFERENCE RULE - if no explicit day count field exists in source data, produce this fieldMapping entry:
    sourceField="day_count (inferred)"
    cdmPath=product.economicTerms.payout[0].interestRatePayout.dayCountFraction
    confidence=MEDIUM
    missingSourceField=true
    transformation="defaulted to ACT/ACT.ICMA"
    reason="No day count convention field present in source data. Defaulted to ACT/ACT.ICMA which is the standard convention for government bonds per ICMA guidelines. Human review recommended for non-standard instruments."
    This entry is REQUIRED even when day count is not in source. Never omit it.

FIELDMAPPING ENTRY STRUCTURE:
Every fieldMapping entry must include these fields:
- sourceField: name of the source field (or descriptive name for inferred fields)
- cdmPath: exact CDM path
- confidence: HIGH, MEDIUM, or LOW
- transformation: what was done to the value (or "direct mapping" if unchanged)
- missingSourceField: true if this field was not present in source data, false if it was
- reason: (REQUIRED for any entry where missingSourceField=true or confidence is MEDIUM or LOW)
  The reason must explain in plain English:
  1. Why the field was missing or ambiguous
  2. How the value was derived or inferred
  3. What a human reviewer should check

For directly mapped HIGH confidence fields, reason is optional but transformation is always required.

OUTPUT: respond with valid JSON only. No markdown. No backticks. Start response with {
"""


def map_trade(normalized_fields, product_type="GovernmentBond"):
    """Core mapping function."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    fields_text = json.dumps(normalized_fields, indent=2)

    has_currency = any(k.lower() in ["currency", "ccy", "bond_ccy", "settle_ccy"] for k in normalized_fields.keys())
    has_day_count = any(k.lower() in ["day_count", "dcf", "day_cnt", "basis", "day_count_basis"] for k in normalized_fields.keys())

    reminders = []
    if not has_currency:
        reminders.append("No currency field in source - apply rule 11: add currency (inferred) entry with missingSourceField=true and full reason")
    if not has_day_count:
        reminders.append("No day count field in source - apply rule 12: add day_count (inferred) entry with missingSourceField=true and full reason")

    reminder_text = ""
    if reminders:
        reminder_text = "\n\nREMINDERS FOR THIS INPUT:\n" + "\n".join(["- " + r for r in reminders])

    user_message = (
        "Map this legacy trade data to CDM format.\n\n"
        "SOURCE DATA:\n" + fields_text +
        reminder_text +
        "\n\nApply rules 10, 11, 12. Include reason field on all inferred or MEDIUM/LOW confidence entries. Return raw JSON only. Start with {"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=GOVERNMENT_BOND_SCHEMA,
        messages=[{"role": "user", "content": user_message}]
    )

    raw_text = response.content[0].text.strip()
    if "```" in raw_text:
        parts = raw_text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw_text = part
                break
    raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
        result["_agentModel"] = "claude-sonnet-4-6"
        result["_sourceFormat"] = normalized_fields.get("_format", "UNKNOWN")
        return result
    except json.JSONDecodeError as e:
        return {"error": str(e), "rawResponse": raw_text}


def score_against_ground_truth(agent_output, ground_truth_path):
    """Compare agent output against ground truth using best-match scoring."""
    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)

    gt_mappings = {
        m["source_field"]: m["cdm_path"]
        for m in ground_truth.get("_field_mapping", [])
        if "NOT MAPPED" not in m["cdm_path"]
    }

    agent_mappings = {}
    for m in agent_output.get("fieldMapping", []):
        src = m.get("sourceField", "")
        cdm = m.get("cdmPath", "")
        if "UNMAPPED" not in cdm and "NOT MAPPED" not in cdm:
            if src not in agent_mappings:
                agent_mappings[src] = []
            agent_mappings[src].append(cdm)

    correct = 0
    total = len(gt_mappings)
    comparison = []

    for source_field, gt_cdm_path in gt_mappings.items():
        agent_paths = agent_mappings.get(source_field, ["MISSING"])
        best_match = "MISSING"
        is_correct = False
        for path in agent_paths:
            if path == gt_cdm_path:
                best_match = path
                is_correct = True
                break
            elif path.startswith(gt_cdm_path) or gt_cdm_path.startswith(path):
                best_match = path
                is_correct = True
                break
        if not is_correct and agent_paths:
            best_match = agent_paths[0]
        if is_correct:
            correct += 1
        comparison.append({
            "sourceField": source_field,
            "groundTruth": gt_cdm_path,
            "agentOutput": best_match,
            "correct": is_correct
        })

    accuracy = round((correct / total * 100), 1) if total > 0 else 0
    return {
        "accuracy": str(accuracy) + "%",
        "correct": correct,
        "total": total,
        "comparison": comparison
    }


if __name__ == "__main__":

    # Test with Sample C (fixed-width) since it has the most inferred fields
    sample_c = "TRADE_ID  ISIN          SIDE QTY        PRICE    COUPON FREQ MAT_DATE   CPTY\nTB0091234 US91282CJL54  B    10000000   98.7500  4.2500 S    20340815   BARC"

    print("=" * 60)
    print("CDM MAPPING AGENT - Testing inferred field reasons")
    print("Sample C (fixed-width) - most inferred fields")
    print("=" * 60)

    normalized = normalize(sample_c)
    print("Format: " + normalized.get("_format", "UNKNOWN"))
    print("Fields: " + str(len(normalized) - 1))

    print("\nRunning agent...")
    result = map_trade(normalized)

    if "error" in result:
        print("ERROR: " + result["error"])
    else:
        print("\n--- Field Mappings (showing inferred fields) ---")
        for fm in result.get("fieldMapping", []):
            src = fm.get("sourceField", "?")
            cdm = fm.get("cdmPath", "?")
            conf = fm.get("confidence", "?")
            missing = fm.get("missingSourceField", False)
            reason = fm.get("reason", "")
            trans = fm.get("transformation", "")

            print("\n  [" + conf + "] " + src)
            print("    -> " + cdm)
            if trans:
                print("    Transformation: " + trans)
            if missing:
                print("    INFERRED (not in source)")
            if reason:
                print("    Reason: " + reason)

        print("\nScoring against ground truth...")
        gt_path = "data/ground_truth/ground_truth_C.json"
        if os.path.exists(gt_path):
            score = score_against_ground_truth(result, gt_path)
            print("Accuracy: " + score["accuracy"] + " (" + str(score["correct"]) + "/" + str(score["total"]) + ")")
            for c in score["comparison"]:
                status = "CORRECT" if c["correct"] else "WRONG"
                print("  " + status + ": " + c["sourceField"])
