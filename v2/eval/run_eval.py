"""
v2/eval/run_eval.py

Evaluates the CDM mapping agent on the single-currency IRS ground-truth set.

Pipeline per case:
    raw input --extract--> IRSTradeInput --build_irs_trade_state--> CDM dict
    CDM dict  --normalize+diff--> vs expected_cdm.json   =>  pass if 0 diffs

Build and diff are already proven (v2/tests/compare_reference.py, 5/5 exact).
This harness measures the EXTRACTION step: raw legacy record -> IRSTradeInput.

Run from repo root:
    python v2/eval/run_eval.py --oracle          # harness self-test (uses fixtures)
    python v2/eval/run_eval.py                    # real agent (Claude API)
    python v2/eval/run_eval.py --oracle basis     # single case
    python v2/eval/run_eval.py --json report.json # machine-readable output
    python v2/eval/run_eval.py --model claude-sonnet-4-6
    python v2/eval/run_eval.py --verbose          # print extracted IRSTradeInput
"""
import sys, os, json, argparse
sys.path.insert(0, '.')

from v2.src.builders.cdm_builder import build_irs_trade_state
from v2.tests.compare_reference import normalize, diff, CASES as ORACLE_CASES
from v2.src.agent.extractor_sonnet import extract_irs_trade as extract_sonnet
from v2.src.agent.extractor_opus import extract_irs_trade as extract_opus

GT_DIR = 'v2/data/ground_truth/interest_rate_swap'

CASES = {
    "fixedfloat": ("fixedfloat", "input.txt", "pipe_blotter"),
    "ois":        ("ois", "input.json", "booking_json"),
    "zerocoupon": ("zerocoupon", "input.txt", "confirmation_text"),
    "basis":      ("basis", "input.dat", "fixed_width"),
    "basis-ois":  ("basis-ois", "input.txt", "kv_message"),
    "xccy-fixedfixed": ("xccy-fixedfixed", "input.txt", "fix_tagvalue"),
    "xccy-fixedfloat": ("xccy-fixedfloat", "input.json", "risk_system_json"),
    "xccy-basis":      ("xccy-basis", "input.txt", "term_sheet_text"),
}


def load_raw(case):
    subdir, fname, fmt = CASES[case]
    with open(os.path.join(GT_DIR, subdir, fname), encoding="utf-8") as f:
        return f.read(), fmt


def load_expected(case):
    subdir = CASES[case][0]
    with open(os.path.join(GT_DIR, subdir, "expected_cdm.json"), encoding="utf-8") as f:
        return json.load(f)


def oracle_extract(case, raw_text, fmt):
    fixture_fn, _ = ORACLE_CASES[case]
    return fixture_fn()


def run_case(case, use_oracle, extractor_choice, verbose):
    raw_text, fmt = load_raw(case)
    expected = load_expected(case)
    try:
        if use_oracle:
            trade_input = oracle_extract(case, raw_text, fmt)
        else:
            extract_fn = extract_sonnet if extractor_choice == "sonnet" else extract_opus
            trade_input = extract_fn(raw_text, fmt, verbose=verbose)
    except NotImplementedError as e:
        return {"case": case, "status": "ERROR", "error": str(e), "diffs": None}
    except Exception as e:
        return {"case": case, "status": "ERROR",
                "error": f"{type(e).__name__}: {e}", "diffs": None}

    built = build_irs_trade_state(trade_input)
    diffs = []
    diff(normalize(built), normalize(expected), "", diffs)
    return {
        "case": case,
        "status": "PASS" if not diffs else "FAIL",
        "diff_count": len(diffs),
        "diffs": [{"kind": k, "path": p, "ours": a, "ref": b} for k, p, a, b in diffs],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*", help="case names (default: all)")
    ap.add_argument("--oracle", action="store_true",
                    help="use known-correct IRSTradeInput (harness self-test)")
    ap.add_argument("--extractor", choices=["sonnet", "opus"], default="sonnet",
                    help="which extractor to use: sonnet (cheaper) or opus (more accurate); default: sonnet")
    ap.add_argument("--json", metavar="PATH", help="write full report as JSON")
    ap.add_argument("--show", type=int, default=15, help="max diffs to print per case")
    ap.add_argument("--verbose", action="store_true",
                    help="print the extracted IRSTradeInput per case")
    args = ap.parse_args()

    names = args.cases or list(CASES)
    mode = "ORACLE" if args.oracle else f"AGENT ({args.extractor})"
    print(f"=== IRS extraction eval [{mode}] ===\n")

    results, npass, nfail, nerr = [], 0, 0, 0
    for case in names:
        r = run_case(case, args.oracle, args.extractor, args.verbose)
        results.append(r)
        if r["status"] == "PASS":
            npass += 1
            print(f"  {case:12s} PASS")
        elif r["status"] == "FAIL":
            nfail += 1
            print(f"  {case:12s} FAIL  ({r['diff_count']} diffs)")
            for d in r["diffs"][:args.show]:
                print(f"       [{d['kind']}] {d['path']}")
                if d["ours"] is not None:
                    print(f"           ours: {json.dumps(d['ours'])[:120]}")
                if d["ref"] is not None:
                    print(f"           ref : {json.dumps(d['ref'])[:120]}")
            if r["diff_count"] > args.show:
                print(f"       ... and {r['diff_count'] - args.show} more")
        else:
            nerr += 1
            print(f"  {case:12s} ERROR ({r['error']})")

    print(f"\n{npass} pass, {nfail} fail, {nerr} error  /  {len(names)} cases")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "summary": {"pass": npass, "fail": nfail,
                       "error": nerr, "total": len(names)}, "results": results},
                      f, indent=2)
        print(f"report written: {args.json}")

    sys.exit(0 if (nfail == 0 and nerr == 0) else 1)


if __name__ == "__main__":
    main()
