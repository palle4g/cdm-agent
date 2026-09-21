"""
Diagnostic for the Payout choice failure.
Run from repo root:  python diag_payout.py
"""
import json, copy
import finos._bundle as b
from rune.runtime.base_data_class import BaseDataClass
from v2.src.builders.ref_resolver import resolve_ancillary_party_refs

PATH = 'v2/data/reference/interest_rate_swap/swaps/irs-fixedfloat.json'
with open(PATH) as f:
    original = json.load(f)

# ── Check 1: where did the payout data go? ───────────────────────────────────
ts = BaseDataClass.rune_deserialize(copy.deepcopy(original), namespace_prefix='finos', validate_model=False)
p0 = ts.trade.product.economicTerms.payout[0]
print("CHECK 1 - payout[0] after loading as-is")
print("  set fields :", {k: type(v).__name__ for k, v in p0.__dict__.items() if v is not None and not k.startswith('__')})
extra = getattr(p0, '__pydantic_extra__', None)
print("  extra keys :", list(extra.keys()) if extra else None)
print()

# ── Check 2: nest each payout under its type name, then roundtrip ────────────
nested = copy.deepcopy(original)
for i, payout in enumerate(nested['trade']['product']['economicTerms']['payout']):
    type_name = payout.pop('@type').split('.')[-1]          # e.g. InterestRatePayout
    nested['trade']['product']['economicTerms']['payout'][i] = {type_name: payout}

print("CHECK 2 - payouts rewritten as {'InterestRatePayout': {...}}")
ts2 = BaseDataClass.rune_deserialize(nested, namespace_prefix='finos', validate_model=False)
resolve_ancillary_party_refs(ts2)

attempts = [
    ("strict=False (validation ON)", dict(strict=False)),
    ("validate_model=False (validation OFF)", dict(validate_model=False)),
]
out = None
for label, kwargs in attempts:
    try:
        out = ts2.rune_serialize(indent=2, **kwargs)
        print(f"  {label}: OK, length {len(out)}")
        break
    except Exception as e:
        root = e.__context__ or e
        print(f"  {label}: FAIL ({type(root).__name__})")
        for line in str(root).splitlines()[:6]:
            print("     ", line[:180])

if out:
    save = 'v2/data/reference/interest_rate_swap/_roundtrip_irs-fixedfloat.json'
    with open(save, 'w') as f:
        f.write(out)
    print("  saved to", save)
    d = json.loads(out)
    p0 = d['trade']['product']['economicTerms']['payout'][0]
    shape = "FLAT @type (matches FINXIS)" if '@type' in p0 else f"NESTED under {list(p0.keys())}"
    print("  payout shape written by library:", shape)
