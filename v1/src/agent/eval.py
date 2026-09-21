"""
eval.py
T-008: Evaluation harness (scalable) + wired into T-009 Observation Store.

Every trade run through eval is now also stored permanently in the
Observation Store (data/observation_store.db) - real conversions, not demo
data. This works identically for every product, no per-product code.

Usage:
    python src/agent/eval.py                              (all products, all files)
    python src/agent/eval.py FXForward                     (one product, all its files)
    python src/agent/eval.py FXForward fx_002_JSON.json    (one product, one specific file)
    python src/agent/eval.py FXForward fx_002              (one product, matches any file starting with fx_002)
"""

import json
import os
import re
import sys
import glob
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
from ingestion.format_detector import normalize
from agent.mapping_agent import map_trade, score_against_ground_truth
from schemas.registry import list_products
from registry.observation_store import init_db, store_conversion
from config import GROUND_TRUTH_DIR, EVAL_REPORT_DIR, AGENT_MODEL

load_dotenv()


def product_type_to_folder(product_type):
    """GovernmentBond -> government_bond, FXForward -> fx_forward"""
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', product_type)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()


def discover_products_with_ground_truth():
    """For every REGISTERED product type, check if a matching ground truth folder exists."""
    found = []
    for product_type in list_products():
        folder = product_type_to_folder(product_type)
        full_path = os.path.join(GROUND_TRUTH_DIR, folder)
        if os.path.isdir(full_path):
            found.append((product_type, full_path))
    return found


def run_eval_for_product(product_type, product_dir, file_filter=None):
    """
    Run eval on ground truth files for one product.
    Each successful run is stored in the Observation Store (T-009).
    """
    files = sorted(glob.glob(os.path.join(product_dir, "*.json")))

    if file_filter:
        if file_filter.endswith(".json"):
            files = [f for f in files if os.path.basename(f) == file_filter]
        else:
            files = [f for f in files if os.path.basename(f).startswith(file_filter)]

        if not files:
            print("  No ground truth file matching '" + file_filter + "' found in " + product_dir)
            return []

    results = []

    for f in files:
        with open(f, "r") as fh:
            gt = json.load(fh)
        raw = gt.get("_source", {}).get("raw")
        name = os.path.basename(f)

        if not raw:
            print("  SKIP " + name + " (no _source.raw)")
            continue

        print("\n  Running: " + name)
        normalized = normalize(raw)
        agent_output = map_trade(normalized, product_type=product_type)

        if "error" in agent_output:
            print("    ERROR: " + agent_output["error"])
            results.append({"file": name, "accuracy": "0%", "correct": 0, "total": 0, "status": "ERROR"})
            continue

        score = score_against_ground_truth(agent_output, f)
        print("    " + score["accuracy"] + " (" + str(score["correct"]) + "/" + str(score["total"]) + ")")
        for c in score["comparison"]:
            if not c["correct"]:
                print("      WRONG: " + c["sourceField"] + " expected " + c["groundTruth"] + " got " + c["agentOutput"])

        # T-009: store this real conversion in the Observation Store.
        # Same call for every product - product_type is just a data value.
        conversion_id = store_conversion(product_type, normalized, agent_output, accuracy=score["accuracy"])
        print("    Stored in Observation Store as conversion id " + str(conversion_id))

        results.append({
            "file": name, "accuracy": score["accuracy"],
            "correct": score["correct"], "total": score["total"],
            "status": "OK", "comparison": score["comparison"],
            "conversionId": conversion_id
        })

    return results


def run_full_eval(only_product=None, only_file=None):
    print("=" * 60)
    print("CDM MAPPING AGENT - EVALUATION HARNESS (T-008)")
    print("=" * 60)
    print("Started: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Model:   " + AGENT_MODEL)
    if only_product:
        print("Filter:  product=" + only_product + (", file=" + only_file if only_file else ""))

    # Make sure the Observation Store exists before we start storing to it
    init_db()

    discovered = discover_products_with_ground_truth()

    if only_product:
        discovered = [(p, d) for p, d in discovered if p == only_product]
        if not discovered:
            print("No ground truth folder found for product: " + only_product)
            print("Registered products: " + ", ".join(list_products()))
            return None

    all_results = {}
    total_correct = 0
    total_fields = 0

    for product_type, product_dir in discovered:
        print("\n" + "-" * 50)
        print("PRODUCT: " + product_type)
        print("-" * 50)
        results = run_eval_for_product(product_type, product_dir, file_filter=only_file)
        all_results[product_type] = results
        for r in results:
            total_correct += r.get("correct", 0)
            total_fields += r.get("total", 0)

    overall = round((total_correct / total_fields * 100), 1) if total_fields > 0 else 0

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print("Overall accuracy: " + str(overall) + "% (" + str(total_correct) + "/" + str(total_fields) + " fields)")
    for product, results in all_results.items():
        passed = sum(1 for r in results if r.get("correct", 0) == r.get("total", 0) and r.get("total", 0) > 0)
        print("\n  " + product + ": " + str(passed) + "/" + str(len(results)) + " files at 100%")
        for r in results:
            mark = "PASS" if (r.get("correct", 0) == r.get("total", 0) and r.get("total", 0) > 0) else "PARTIAL"
            print("    " + mark + " | " + r["file"] + " | " + r.get("accuracy", "0%"))

    if not only_file:
        report = {
            "runAt": datetime.now().isoformat(),
            "model": AGENT_MODEL,
            "overallAccuracy": str(overall) + "%",
            "totalCorrect": total_correct,
            "totalFields": total_fields,
            "products": all_results
        }
        report_path = os.path.join(EVAL_REPORT_DIR, "eval_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print("\nFull report saved: " + report_path)

    return {"overallAccuracy": overall, "products": all_results}


if __name__ == "__main__":
    only_product = sys.argv[1] if len(sys.argv) > 1 else None
    only_file = sys.argv[2] if len(sys.argv) > 2 else None
    run_full_eval(only_product, only_file)
