"""
v2/src/agent/fra_extractor_opus.py
Opus 4.6 FRA extractor — use if Sonnet misreads a harder/free-text FRA record.
"""
import dataclasses
from v2.src.agent.fra_extractor_core import extract_fra_trade_with_model
from v2.src.schemas.fra import FRAInput

MODEL = "claude-opus-4-6"


def extract_fra_trade(raw_text: str, fmt_hint: str, *, verbose: bool = False) -> FRAInput:
    return extract_fra_trade_with_model(raw_text, fmt_hint, MODEL, verbose=verbose)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: python -m v2.src.agent.fra_extractor_opus <fmt_hint> <path>")
        raise SystemExit(2)
    fmt_hint, path = sys.argv[1], sys.argv[2]
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    trade = extract_fra_trade(raw, fmt_hint, verbose=True)
    print("\nParsed FRAInput fields:")
    for fl in dataclasses.fields(trade):
        v = getattr(trade, fl.name)
        show = v if not isinstance(v, list) else f"[{len(v)} items]"
        print(f"  {fl.name} = {show}")
