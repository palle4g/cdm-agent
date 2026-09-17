"""
mapping_agent.py
T-005: The CDM mapping agent.
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

CRITICAL TRANSFORMATION RULES:
1. Coupon rate: if value > 1.0, divide by 100. Example: 4.25 becomes 0.0425
2. SEMI or S or SEMI-ANNUAL maps to period=M periodMultiplier=6
3. ANNUAL or A maps to period=Y periodMultiplier=1
4. QUARTERLY or Q maps to period=M periodMultiplier=3
5. ACT/ACT or ACT/ACT ICMA maps to ACT/ACT.ICMA
6. BUY or B or PURCHASE maps to payer=Party2 receiver=Party1
7. SELL or S or SALE maps to payer=Party1 receiver=Party2
8. Date format YYYYMMDD with no dashes converts to YYYY-MM-DD
9. Currency: if not present infer from ISIN prefix. US=USD GB=GBP DE=EUR

IMPORTANT FOR FIELD MAPPING OUTPUT:
- Use the exact full CDM paths shown above
- For FREQ use ONE entry: product.economicTerms.payout[0].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency
- For SIDE use ONE entry: product.economicTerms.payout[0].interestRatePayout.payerReceiver
- For ISIN use ONE entry: product.productIdentifier[0].identifier

OUTPUT: respond with valid JSON only, no markdown, no backticks, no explanation.

{
  "productTypeDetected": "Rates.GovernmentBond",
  "cdmTrade": {
    "tradeIdentifier": [{"assignedIdentifier": [{"identifier": "..."}]}],
    "tradeDate": {"date": "YYYY-MM-DD"},
    "party": [
      {"partyId": [{"identifier": "OUR-BANK", "identifierType": "INTERNAL"}], "name": "OUR BANK PLC", "role": "OUR_BANK"},
      {"partyId": [{"identifier": "...", "identifierType": "INTERNAL"}], "name": "...", "role": "COUNTERPARTY"}
    ],
    "product": {
      "productType": "Rates.GovernmentBond",
      "productIdentifier": [{"identifier": "...", "source": "ISIN"}],
      "economicTerms": {
        "effectiveDate": {"adjustableDate": {"unadjustedDate": "YYYY-MM-DD"}},
        "terminationDate": {"adjustableDate": {"unadjustedDate": "YYYY-MM-DD"}},
        "payout": [{
          "interestRatePayout": {
            "payerReceiver": {"payer": "Party2", "receiver": "Party1"},
            "rateSpecification": {"fixedRate": {"rateSchedule": {"initialValue": 0.0000}}},
            "dayCountFraction": "ACT/ACT.ICMA",
            "calculationPeriodDates": {
              "terminationDate": {"adjustableDate": {"unadjustedDate": "YYYY-MM-DD"}},
              "calculationPeriodFrequency": {"period": "M", "periodMultiplier": 6}
            },
            "principalPayment": {
              "principalAmount": {"amount": 0, "unit": {"currency": "USD"}}
            }
          }
        }]
      }
    },
    "dates": {
      "tradeDate": "YYYY-MM-DD",
      "settlementDate": "YYYY-MM-DD",
      "maturityDate": "YYYY-MM-DD"
    }
  },
  "fieldMapping": [
    {"sourceField": "...", "cdmPath": "...", "confidence": "HIGH", "transformation": "..."}
  ],
  "mappingNotes": ["any ambiguities or assumptions made"],
  "missingFields": ["list of required CDM fields not found in source"]
}
"""


def map_trade(normalized_fields, product_type="GovernmentBond"):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    fields_text = json.dumps(normalized_fields, indent=2)
    user_message = "Map this legacy trade data to CDM format.\n\nSOURCE DATA:\n" + fields_text + "\n\nRespond with valid JSON only."

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=GOVERNMENT_BOND_SCHEMA,
        messages=[{"role": "user", "content": user_message}]
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
        result["_agentModel"] = "claude-sonnet-4-6"
        result["_sourceFormat"] = normalized_fields.get("_format", "UNKNOWN")
        return result
    except json.JSONDecodeError as e:
        return {"error": str(e), "rawResponse": raw_text}


def score_against_ground_truth(agent_output, ground_truth_path):
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
    return {"accuracy": str(accuracy) + "%", "correct": correct, "total": total, "comparison": comparison}


if __name__ == "__main__":

    sample_a = "TRADE_NUM|SEC_ID|ISIN|SEC_DESC|SIDE|QTY|PRICE|YIELD|ACCRUED_INT|SETTLE_AMT|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT\nTB-20260914-001|UST-10Y|US91282CJL54|US TREASURY 4.25% 08/2034|BUY|10000000|98.750|4.42|21250.00|9896250.00|JPMORGAN|2026-09-14|2026-09-16|2034-08-15|4.25|SEMI|ACT/ACT"

    print("=" * 60)
    print("CDM MAPPING AGENT - T-005 Test")
    print("=" * 60)

    print("\nStep 1: Detecting format and normalizing...")
    normalized = normalize(sample_a)
    print("Format detected: " + normalized.get("_format", "UNKNOWN"))
    print("Fields found: " + str(len(normalized) - 1))

    print("\nStep 2: Running mapping agent...")
    result = map_trade(normalized)

    if "error" in result:
        print("ERROR: " + result["error"])
    else:
        print("Product detected: " + str(result.get("productTypeDetected")))
        print("Source format: " + str(result.get("_sourceFormat")))

        print("\n--- CDM Trade Output ---")
        print(json.dumps(result.get("cdmTrade", {}), indent=2))

        print("\n--- Field Mappings ---")
        for fm in result.get("fieldMapping", []):
            conf = fm.get("confidence", "?")
            src = fm.get("sourceField", "?")
            cdm = fm.get("cdmPath", "?")
            trans = fm.get("transformation", "")
            if trans:
                print("  [" + conf + "] " + src + " -> " + cdm + " [" + trans + "]")
            else:
                print("  [" + conf + "] " + src + " -> " + cdm)

        notes = result.get("mappingNotes", [])
        if notes:
            print("\n--- Agent Notes ---")
            for note in notes:
                print("  - " + note)

        missing = result.get("missingFields", [])
        if missing:
            print("\n--- Missing Fields ---")
            for field in missing:
                print("  MISSING: " + field)

        print("\nStep 3: Scoring against ground truth...")
        gt_path = "data/ground_truth/ground_truth_A.json"
        if os.path.exists(gt_path):
            score = score_against_ground_truth(result, gt_path)
            print("\n  Accuracy: " + score["accuracy"] + " (" + str(score["correct"]) + "/" + str(score["total"]) + " fields correct)")
            print("\n  Field-by-field:")
            for c in score["comparison"]:
                if c["correct"]:
                    print("  CORRECT: " + c["sourceField"])
                else:
                    print("  WRONG:   " + c["sourceField"])
                    print("      Expected: " + c["groundTruth"])
                    print("      Got:      " + c["agentOutput"])
        else:
            print("  Ground truth file not found - skipping scoring")
