"""
v2/src/agent/extractor_opus.py
Opus 4.6 extractor — more accurate; use for free-text confirmations and complex xccy term sheets.
"""
import dataclasses
from v2.src.agent.extractor_core import extract_irs_trade_with_model
from v2.src.schemas.interest_rate_swap import IRSTradeInput

MODEL = "claude-opus-4-6"


def extract_irs_trade(raw_text: str, fmt_hint: str, *, verbose: bool = False) -> IRSTradeInput:
    return extract_irs_trade_with_model(raw_text, fmt_hint, MODEL, verbose=verbose)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: python -m v2.src.agent.extractor_opus <fmt_hint> <path>")
        raise SystemExit(2)
    fmt_hint, path = sys.argv[1], sys.argv[2]
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    trade = extract_irs_trade(raw, fmt_hint, verbose=True)
    print("\nParsed IRSTradeInput fields:")
    for fl in dataclasses.fields(trade):
        v = getattr(trade, fl.name)
        show = v if not isinstance(v, list) else f"[{len(v)} items]"
        print(f"  {fl.name} = {show}")
