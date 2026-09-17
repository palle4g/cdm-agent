"""
eval.py
T-008: Evaluation harness (scalable).
Scans data/ground_truth/<product>/ for all .json files, reads the raw input
from each file's _source.raw, runs the agent, and scores against _field_mapping.

Adding a ground truth file automatically adds it to the eval. No code changes.

Usage:
    python src/agent/eval.py                 (evaluates all products)
    python src/agent/eval.py GovernmentBond  (evaluates one product)
"""

import json
import os
import sys
import glob
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
from ingestion.format_detector import normalize
from agent.mapping_agent import map_trade, score_against_ground_truth
from config import GROUND_TRUTH_DIR, EVAL_REPORT_DIR, AGENT_MODEL

load_dotenv()


def run_eval_for_product(product_type):
    """Run eval on every ground truth file for one product."""
    product_dir = os.path.join(GROUND_TRUTH_DIR, product_type_to_folder(product_type))
    if not os.path.isdir(product_dir):
        print("  No folder for " + product_type + " at " + product_dir)
        return []

    files = sorted(glob.glob(os.path.join(product_dir, "*.json")))
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

        results.append({
            "file": name, "accuracy": score["accuracy"],
            "correct": score["correct"], "total": score["total"],
            "status": "OK", "comparison": score["comparison"]
        })

    return results


def product_type_to_folder(product_type):
    """GovernmentBond -> government_bond"""
    out = ""
    for i, ch in enumerate(product_type):
        if ch.isupper() and i > 0:
            out += "_"
        out += ch.lower()
    return out


def run_full_eval(only_product=None):
    print("=" * 60)
    print("CDM MAPPING AGENT - EVALUATION HARNESS (T-008)")
    print("=" * 60)
    print("Started: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Model:   " + AGENT_MODEL)

    # Discover products from folders under ground_truth
    if only_product:
        products = [only_product]
    else:
        products = []
        if os.path.isdir(GROUND_TRUTH_DIR):
            for entry in sorted(os.listdir(GROUND_TRUTH_DIR)):
                full = os.path.join(GROUND_TRUTH_DIR, entry)
                if os.path.isdir(full):
                    # folder government_bond -> GovernmentBond
                    products.append("".join(p.capitalize() for p in entry.split("_")))

    all_results = {}
    total_correct = 0
    total_fields = 0

    for product in products:
        print("\n" + "-" * 50)
        print("PRODUCT: " + product)
        print("-" * 50)
        results = run_eval_for_product(product)
        all_results[product] = results
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
    return report


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    run_full_eval(only)
