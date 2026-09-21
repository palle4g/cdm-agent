"""
test_roundtrip.py — full roundtrip test with rune_patches applied.
Run from repo root:  python test_roundtrip.py
"""
import sys
sys.path.insert(0, '.')

# MUST be first, before any finos import
import v2.src.builders.rune_patches  # noqa: F401

import json
import finos._bundle as b
from rune.runtime.base_data_class import BaseDataClass
from v2.src.builders.ref_resolver import resolve_ancillary_party_refs
from v2.src.builders.cdm_format import load_reference_file

PATH = 'v2/data/reference/interest_rate_swap/swaps/irs-fixedfloat.json'
# transform ALL flat-@type choice fields into nested form
data = load_reference_file(PATH)

# ── load ─────────────────────────────────────────────────────────────────────
ts = BaseDataClass.rune_deserialize(data, namespace_prefix='finos', validate_model=False)
resolve_ancillary_party_refs(ts)
print('[1] deserialize + ref workaround: OK')

# ── serialize with full validation ───────────────────────────────────────────
try:
    out = ts.rune_serialize(indent=2)
    print(f'[2] rune_serialize (validation ON): OK, length {len(out)}')
except Exception as e:
    root = e.__context__ or e
    print(f'[2] rune_serialize (validation ON): FAIL ({type(root).__name__})')
    for line in str(root).splitlines()[:10]:
        print('   ', line[:180])
    try:
        out = ts.rune_serialize(indent=2, validate_model=False)
        print(f'[2b] rune_serialize (validation OFF): OK, length {len(out)}')
    except Exception as e2:
        root2 = e2.__context__ or e2
        print(f'[2b] rune_serialize (validation OFF): FAIL ({type(root2).__name__})')
        for line in str(root2).splitlines()[:10]:
            print('   ', line[:180])
        sys.exit(1)

# ── save + report shape ──────────────────────────────────────────────────────
save = 'v2/data/reference/interest_rate_swap/_roundtrip_irs-fixedfloat.json'
with open(save, 'w') as f:
    f.write(out)
print(f'[3] saved: {save}')

d = json.loads(out)
p0 = d['trade']['product']['economicTerms']['payout'][0]
if '@type' in p0:
    print('[4] payout shape written: FLAT @type (matches FINXIS reference)')
else:
    print(f'[4] payout shape written: NESTED under {list(p0.keys())}')
