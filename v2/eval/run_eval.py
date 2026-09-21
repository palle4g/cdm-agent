"""
v2/eval/run_eval.py

Evaluates the CDM mapping agent on the single-currency IRS ground-truth set.

Pipeline per case:
    raw input --extract--> IRSTradeInput --build_irs_trade_state--> CDM dict
    CDM dict  --normalize+diff--> vs expected_cdm.json   =>  pass if 0 diffs

The build + diff halves are already proven (v2/tests/compare_reference.py,
5/5 exact). This harness measures the EXTRACTION step: raw legacy record ->
IRSTradeInput. The builder and the normalizer are imported, not re-defined,
so "correct" means the same thing everywhere.

Extractor plug point:
    --oracle    use the known-correct IRSTradeInput from compare_reference.py
                (proves the harness itself; expect 5/5 pass)
    (default)   call agent_extract(raw_text, fmt) — the real agent. Until it
                is implemented it raises NotImplementedError, which the runner
                reports as an ERROR row rather than crashing.

Run from repo root:
    python v2/eval/run_eval.py --oracle          # harness self-test
    python v2/eval/run_eval.py                    # real agent
    python v2/eval/run_eval.py --oracle basis     # single case
    python v2/eval/run_eval.py --json report.json # machine-readable output
"""
import sys, os, json, argparse
sys.path.insert(0, '.')

from v2.src.builders.cdm_builder import build_irs_trade_state
# reuse the single source of truth for "equal"
from v2.tests.compare_reference import normalize, diff, CASES as ORACLE_CASES

GT_DIR = 'v2/data/ground_truth/interest_rate_swap'

# case -> (subdir, input filename, format hint passed to the extractor)
CASES = {
    "fixedfloat": ("fixedfloat", "input.txt", "pipe_blotter"),
    "ois": ("ois", "input.json", "booking_json"),
    "zerocoupon": ("zerocoupon", "input.txt", "confirmation_text"),
    "basis": ("basis", "input.dat", "fixed_width"),
    "basis-ois": ("basis-ois", "input.txt", "kv_message"),
}


def load_raw(case):
    subdir, fname, fmt = CASES[case]
    with open(os.path.join(GT_DIR, subdir, fname), encoding="utf-8") as f:
        return f.read(), fmt


def load_expected(case):
    subdir = CASES[case][0]
    with open(os.path.join(GT_DIR, subdir, "expected_cdm.json"), encoding="utf-8") as f:
        return json.load(f)


# ── extractor plug point ──────────────────────────────────────────────────────

def oracle_extract(case, raw_text, fmt):
    """Return the known-correct IRSTradeInput (from the compare fixtures)."""
    fixture_fn, _ = ORACLE_CASES[case]
    return fixture_fn()


def agent_extract(raw_text, fmt):
    """
    Real agent: raw legacy record -> IRSTradeInput.
    TODO: wire to v2 agent (LLM extraction against the schema, using the
    mapping-conventions table in the ground-truth README as configuration).
    """
    raise NotImplementedError("agent_extract not implemented yet — use --oracle")


# ── run one case ──────────────────────────────────────────────────────────────

def run_case(case, use_oracle):
    raw_text, fmt = load_raw(case)
    expected = load_expected(case)

    try:
        if use_oracle:
            trade_input = oracle_extract(case, raw_text, fmt)
        else:
            trade_input = agent_extract(raw_text, fmt)
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


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*", help="case names (default: all)")
    ap.add_argument("--oracle", action="store_true",
                    help="use known-correct IRSTradeInput (harness self-test)")
    ap.add_argument("--json", metavar="PATH", help="write full report as JSON")
    ap.add_argument("--show", type=int, default=15, help="max diffs to print per case")
    args = ap.parse_args()

    names = args.cases or list(CASES)
    mode = "ORACLE" if args.oracle else "AGENT"
    print(f"=== IRS extraction eval [{mode}] ===\n")

    results, npass, nfail, nerr = [], 0, 0, 0
    for case in names:
        r = run_case(case, args.oracle)
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

    # exit non-zero if anything didn't pass (useful for CI later)
    sys.exit(0 if (nfail == 0 and nerr == 0) else 1)


if __name__ == "__main__":
    main()
