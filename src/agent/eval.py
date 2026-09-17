"""
eval.py
T-008: Evaluation harness.

Runs the mapping agent against all ground truth files and
reports accuracy per sample, per field, and overall.
This is the scorecard that tells you if the agent is improving.

Usage:
    python src/agent/eval.py
"""

import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
from ingestion.format_detector import normalize
from agent.mapping_agent import map_trade, score_against_ground_truth

load_dotenv()

# Ground truth files and their corresponding raw inputs
EVAL_CASES = [
    {
        "id": "GT-BOND-001",
        "label": "Sample A - pipe-delimited",
        "ground_truth": "data/ground_truth/ground_truth_A.json",
        "raw_input": "TRADE_NUM|SEC_ID|ISIN|SEC_DESC|SIDE|QTY|PRICE|YIELD|ACCRUED_INT|SETTLE_AMT|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT\nTB-20260914-001|UST-10Y|US91282CJL54|US TREASURY 4.25% 08/2034|BUY|10000000|98.750|4.42|21250.00|9896250.00|JPMORGAN|2026-09-14|2026-09-16|2034-08-15|4.25|SEMI|ACT/ACT"
    },
    {
        "id": "GT-BOND-002",
        "label": "Sample B - JSON",
        "ground_truth": "data/ground_truth/ground_truth_B.json",
        "raw_input": '{"deal_id":"BOND-2026-8821","security":"US91282CJL54","description":"US TREASURY NOTE 4.25 08/15/2034","transaction_type":"PURCHASE","face_value":5000000,"currency":"USD","coupon_rate":4.25,"payment_frequency":"SEMI-ANNUAL","day_count_basis":"ACT/ACT ICMA","trade_date":"2026-09-14","settlement_date":"2026-09-16","maturity_date":"2034-08-15","counterparty":"GOLDMAN SACHS","counterparty_lei":"784F5XWPLTWKTBV3E584"}'
    },
    {
        "id": "GT-BOND-003",
        "label": "Sample C - fixed-width",
        "ground_truth": "data/ground_truth/ground_truth_C.json",
        "raw_input": "TRADE_ID  ISIN          SIDE QTY        PRICE    COUPON FREQ MAT_DATE   CPTY\nTB0091234 US91282CJL54  B    10000000   98.7500  4.2500 S    20340815   BARC"
    }
]


def run_eval_case(case: dict) -> dict:
    """
    Run the agent on one eval case and score it.
    Returns a result dict with accuracy and field details.
    """
    print("\n" + "-" * 50)
    print("Running: " + case["label"])
    print("-" * 50)

    # Check ground truth exists
    if not os.path.exists(case["ground_truth"]):
        print("  ERROR: Ground truth file not found: " + case["ground_truth"])
        return {
            "id": case["id"],
            "label": case["label"],
            "status": "ERROR",
            "error": "Ground truth file not found",
            "accuracy": "0%",
            "correct": 0,
            "total": 0
        }

    # Step 1: Normalize
    normalized = normalize(case["raw_input"])
    source_format = normalized.get("_format", "UNKNOWN")
    print("  Format: " + source_format)
    print("  Fields: " + str(len(normalized) - 1))

    # Step 2: Run agent
    print("  Running agent...")
    agent_output = map_trade(normalized)

    if "error" in agent_output:
        print("  ERROR: " + agent_output["error"])
        return {
            "id": case["id"],
            "label": case["label"],
            "status": "AGENT_ERROR",
            "error": agent_output["error"],
            "accuracy": "0%",
            "correct": 0,
            "total": 0
        }

    # Step 3: Score
    score = score_against_ground_truth(agent_output, case["ground_truth"])
    print("  Accuracy: " + score["accuracy"] + " (" + str(score["correct"]) + "/" + str(score["total"]) + ")")

    # Print field details
    for c in score["comparison"]:
        if c["correct"]:
            print("    CORRECT: " + c["sourceField"])
        else:
            print("    WRONG:   " + c["sourceField"])
            print("      Expected: " + c["groundTruth"])
            print("      Got:      " + c["agentOutput"])

    return {
        "id": case["id"],
        "label": case["label"],
        "sourceFormat": source_format,
        "status": "OK",
        "accuracy": score["accuracy"],
        "correct": score["correct"],
        "total": score["total"],
        "comparison": score["comparison"]
    }


def run_full_eval() -> dict:
    """
    Run all eval cases and produce a full report.
    """
    print("=" * 60)
    print("CDM MAPPING AGENT - EVALUATION HARNESS")
    print("T-008: Full accuracy report across all ground truth cases")
    print("=" * 60)
    print("Started: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Cases:   " + str(len(EVAL_CASES)))

    results = []
    total_correct = 0
    total_fields = 0

    for case in EVAL_CASES:
        result = run_eval_case(case)
        results.append(result)
        total_correct += result.get("correct", 0)
        total_fields += result.get("total", 0)

    # Overall accuracy
    overall = round((total_correct / total_fields * 100), 1) if total_fields > 0 else 0

    # Summary report
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print("Overall accuracy: " + str(overall) + "% (" + str(total_correct) + "/" + str(total_fields) + " fields)")
    print()

    for r in results:
        status = "PASS" if r.get("correct", 0) == r.get("total", 0) else "PARTIAL"
        if r.get("status") in ["ERROR", "AGENT_ERROR"]:
            status = "ERROR"
        print("  " + status + " | " + r["label"] + " | " + r.get("accuracy", "0%"))

    # Identify any consistent failure patterns
    all_wrong = {}
    for r in results:
        for c in r.get("comparison", []):
            if not c["correct"]:
                field = c["sourceField"]
                if field not in all_wrong:
                    all_wrong[field] = []
                all_wrong[field].append(r["label"])

    if all_wrong:
        print("\nFields failing across multiple cases:")
        for field, cases in all_wrong.items():
            print("  " + field + " -> failing in: " + ", ".join(cases))
    else:
        print("\nNo consistent failure patterns - all fields mapping correctly.")

    # Save results to file
    report = {
        "runAt": datetime.now().isoformat(),
        "overallAccuracy": str(overall) + "%",
        "totalCorrect": total_correct,
        "totalFields": total_fields,
        "cases": results
    }

    report_path = "data/eval_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print("\nFull report saved: " + report_path)

    return report


if __name__ == "__main__":
    run_full_eval()
