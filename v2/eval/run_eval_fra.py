"""
v2/eval/run_eval_fra.py

Evaluates the FRA extraction pipeline: raw legacy record -> FRAInput ->
build_fra_trade_state -> normalized diff vs the FINXIS reference file.
Mirrors v2/eval/run_eval.py's structure but targets the FRA schema/builder.

Run from repo root:
    python v2/eval/run_eval_fra.py --oracle          # harness self-test
    python v2/eval/run_eval_fra.py                    # real agent (default: sonnet)
    python v2/eval/run_eval_fra.py --extractor opus
    python v2/eval/run_eval_fra.py --verbose
"""
import sys, os, json, argparse
sys.path.insert(0, '.')

from v2.src.builders.fra_builder import build_fra_trade_state
from v2.tests.compare_reference import normalize, diff, _fra as oracle_fra_fixture
from v2.src.agent.fra_extractor_sonnet import extract_fra_trade as extract_sonnet
from v2.src.agent.fra_extractor_opus import extract_fra_trade as extract_opus

GT_DIR = 'v2/data/ground_truth/fra/fra'
FMT_HINT = "deal_ticket_text"


def load_raw():
    with open(os.path.join(GT_DIR, 'input.txt'), encoding='utf-8') as f:
        return f.read()


def load_expected():
    with open(os.path.join(GT_DIR, 'expected_cdm.json'), encoding='utf-8') as f:
        return json.load(f)


def run(use_oracle, extractor_choice, verbose, show=25):
    expected = load_expected()
    try:
        if use_oracle:
            fra_input = oracle_fra_fixture()
        else:
            raw_text = load_raw()
            extract_fn = extract_sonnet if extractor_choice == "sonnet" else extract_opus
            fra_input = extract_fn(raw_text, FMT_HINT, verbose=verbose)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return 1

    built = build_fra_trade_state(fra_input)
    diffs = []
    diff(normalize(built), normalize(expected), "", diffs)

    mode = "ORACLE" if use_oracle else f"AGENT ({extractor_choice})"
    if not diffs:
        print(f"[{mode}] fra   PASS")
        return 0
    print(f"[{mode}] fra   FAIL  ({len(diffs)} diffs)")
    for kind, path, a, b in diffs[:show]:
        print(f"    [{kind}] {path}")
        if a is not None:
            print(f"        ours: {json.dumps(a)[:130]}")
        if b is not None:
            print(f"        ref : {json.dumps(b)[:130]}")
    if len(diffs) > show:
        print(f"    ... and {len(diffs) - show} more")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", action="store_true", help="use known-correct FRAInput (harness self-test)")
    ap.add_argument("--extractor", choices=["sonnet", "opus"], default="sonnet")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    sys.exit(run(args.oracle, args.extractor, args.verbose))
