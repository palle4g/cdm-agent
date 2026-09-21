"""
agent_loop.py
T-007: End-to-end pipeline with validation retry loop (product-agnostic).

Rewritten to remove the old hardcoded government-bond-only schema. Now reuses
mapping_agent.map_trade() (which loads the correct schema from the registry
per product) instead of duplicating the API call and parsing logic. Works
identically for GovernmentBond, FXForward, InterestRateSwap, or any future
product - zero code changes needed when a new product is registered.
"""

import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
from ingestion.format_detector import normalize
from agent.mapping_agent import map_trade
from validation.validator import validate_from_agent_output
from schemas.registry import detect_product_type
from config import MAX_RETRIES, DEFAULT_PRODUCT_TYPE

load_dotenv()


def run_pipeline(raw_input, label="trade", product_type=None):
    """
    Full end-to-end Plan-Act-Reflect pipeline.
    product_type: force a product, or None to auto-detect via the registry.
    """
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

    if product_type is None:
        product_type = detect_product_type(normalized)
        if product_type == "UNKNOWN":
            product_type = DEFAULT_PRODUCT_TYPE
    print("  Product: " + product_type)

    attempts = []
    final_result = None
    validation_result = None
    previous_errors = None
    use_complex_model = False

    # ACT + REFLECT loop
    for attempt_num in range(1, MAX_RETRIES + 1):
        print("\n[ACT] Attempt " + str(attempt_num) + " of " + str(MAX_RETRIES) + "...")

        agent_output = map_trade(
            normalized,
            product_type=product_type,
            use_complex_model=use_complex_model,
            previous_errors=previous_errors
        )

        if "error" in agent_output:
            print("  Agent error: " + agent_output["error"])
            attempts.append({"attempt": attempt_num, "status": "AGENT_ERROR", "errors": [agent_output["error"]], "warnings": []})
            previous_errors = [agent_output["error"]]
            if not use_complex_model:
                use_complex_model = True
                print("  Switching to complex model for retry...")
            continue

        print("[REFLECT] Validating CDM output...")
        validation_result = validate_from_agent_output(agent_output, product_type=product_type)

        attempts.append({
            "attempt": attempt_num,
            "status": "VALID" if validation_result.is_valid else "INVALID",
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
            "model": agent_output.get("_agentModel", "unknown")
        })

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
                if attempt_num >= 2 and not use_complex_model:
                    use_complex_model = True
                    print("  Escalating to complex model...")
            else:
                print("  Max retries reached - flagging for human review")
                final_result = agent_output

    return {
        "label": label,
        "productType": product_type,
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


def print_summary(result):
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY: " + result["label"])
    print("=" * 60)
    print("  Product:  " + result["productType"])
    print("  Format:   " + result["sourceFormat"])
    print("  Status:   " + result["finalStatus"])
    print("  Attempts: " + str(result["totalAttempts"]))
    for a in result["attempts"]:
        status = "PASS" if a["status"] == "VALID" else "FAIL"
        print("  Attempt " + str(a["attempt"]) + ": " + status + " (model: " + a.get("model", "?") + ")")
        for e in a.get("errors", []):
            print("    Error: " + e)


if __name__ == "__main__":
    # Quick smoke test across all three products using their first ground truth file each
    import json
    from config import GROUND_TRUTH_DIR

    test_cases = [
        ("GovernmentBond", "government_bond", "gb_001_pipedelimited.json"),
        ("FXForward", "fx_forward", "fx_001_pipedelimited.json"),
        ("InterestRateSwap", "interest_rate_swap", "irs_001_XML.json"),
    ]

    print("AGENT LOOP - Product-agnostic smoke test across all registered products")

    results = []
    for product_type, folder, filename in test_cases:
        path = os.path.join(GROUND_TRUTH_DIR, folder, filename)
        if not os.path.exists(path):
            print("\nSkipping " + product_type + " - ground truth not found: " + path)
            continue
        gt = json.load(open(path))
        raw = gt["_source"]["raw"]
        result = run_pipeline(raw, label=product_type + " smoke test", product_type=product_type)
        print_summary(result)
        results.append(result)

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    passed = sum(1 for r in results if r["finalStatus"] == "VALID")
    print("Passed: " + str(passed) + " / " + str(len(results)))
    for r in results:
        status = "PASS" if r["finalStatus"] == "VALID" else "FAIL"
        print("  " + status + " | " + r["productType"] + " | " + str(r["totalAttempts"]) + " attempt(s)")
