"""
v2/tests/compare_fixedfloat.py

Builds the irs-fixedfloat trade with the plain-dict builder and diffs the
output against the FINXIS reference file.

Normalization before comparing (both sides):
  - '@key' / '@ref' bare hash ids (generator artifacts) are dropped
  - '@key:scoped' / '@key:external' ids are canonicalised (S1.., E1.. in
    traversal order) and '@ref:scoped' / '@ref:external' remapped to match,
    so differing id spellings don't count as diffs — only structure and
    values do.

Run from repo root:  python v2/tests/compare_fixedfloat.py
"""
import sys, json, copy
sys.path.insert(0, '.')

from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput
)
from v2.src.builders.cdm_builder import build_irs_trade_state

REF = 'v2/data/reference/interest_rate_swap/swaps/irs-fixedfloat.json'

# ── input fixture: the irs-fixedfloat trade described as agent-extracted fields
input_data = IRSTradeInput(
    trade_date="2018-11-15",
    trade_id="FpML-test-7",
    isda_taxonomy="InterestRate_IRSwap_FixedFloat",
    other_taxonomy="InterestRate::VanillaSwap",
    parties=[
        PartyInput(key="partyA", lei="549300ABANKV6BYQOWM67",
                   lei_scheme="http://www.fpml.org/coding-scheme/external/iso17442",
                   name='A BANK("ABANK")'),
        PartyInput(key="partyB", lei="529900CPTY57S5UCBB52",
                   lei_scheme="http://www.fpml.org/coding-scheme/external/iso17442",
                   name='SELL SECURITIES CO LTD ("Counterparty")'),
        PartyInput(key="dco", lei="123456QQQQ57S5UCBB11",
                   lei_scheme="http://www.fpml.org/coding-scheme/external/iso17442",
                   name="ABC CENTRAL PARTY CLEARING SVC LTD"),
    ],
    party1_key="partyB",
    party2_key="partyA",
    trade_identifiers=[
        TradeIdentifierInput(issuer_key="partyA",
                             id_scheme="http://www.partyA.com/swaps/trade-id",
                             id_value="FpML-test-7"),
    ],
    calc_agent_key="partyA",
    legs=[
        LegInput(  # floating leg: Party1 pays EONIA
            payer="Party1", receiver="Party2", leg_type="floating",
            notional_amount=3672000000, notional_currency="EUR",
            floating_index="EUR-EONIA-AVERAGE",
            day_count_fraction="ACT/360",
            effective_date="2018-11-16", effective_date_bdc="NONE",
            termination_date="2023-11-16", termination_date_bdc="MODFOLLOWING",
            calc_period_bdc="NONE",
            calc_period_multiplier=1, calc_period="M", roll_convention="16",
            payment_freq_multiplier=1, payment_freq_period="M",
            pay_relative_to="CalculationPeriodEndDate", payment_bdc="MODFOLLOWING",
            payment_offset_multiplier=1, payment_offset_period="D",
            payment_offset_day_type="Business",
        ),
        LegInput(  # fixed leg: Party2 pays 0.2%
            payer="Party2", receiver="Party1", leg_type="fixed",
            notional_amount=3672000000, notional_currency="EUR",
            fixed_rate=0.002,
            day_count_fraction="ACT/360",
            effective_date="2018-11-16", effective_date_bdc="NONE",
            termination_date="2023-11-16", termination_date_bdc="MODFOLLOWING",
            calc_period_bdc="NONE",
            calc_period_multiplier=1, calc_period="M", roll_convention="16",
            payment_freq_multiplier=1, payment_freq_period="M",
            pay_relative_to="CalculationPeriodEndDate", payment_bdc="MODFOLLOWING",
            payment_offset_multiplier=1, payment_offset_period="D",
            payment_offset_day_type="Business",
        ),
    ],
)


# ── normalization ─────────────────────────────────────────────────────────────

def _collect_defs(node, defs):
    if isinstance(node, dict):
        for kind, prefix in (("@key:scoped", "S"), ("@key:external", "E")):
            if kind in node:
                key = (kind, node[kind])
                if key not in defs:
                    defs[key] = f"{prefix}{sum(1 for k in defs if k[0] == kind) + 1}"
        for v in node.values():
            _collect_defs(v, defs)
    elif isinstance(node, list):
        for item in node:
            _collect_defs(item, defs)


def _normalize(node, defs):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ("@key", "@ref"):
                continue  # generator hash artifacts
            if k == "@key:scoped":
                out[k] = defs.get(("@key:scoped", v), v)
            elif k == "@key:external":
                out[k] = defs.get(("@key:external", v), v)
            elif k == "@ref:scoped":
                out[k] = defs.get(("@key:scoped", v), f"UNRESOLVED:{v}")
            elif k == "@ref:external":
                out[k] = defs.get(("@key:external", v), f"UNRESOLVED:{v}")
            else:
                out[k] = _normalize(v, defs)
        return out
    if isinstance(node, list):
        return [_normalize(item, defs) for item in node]
    if isinstance(node, float) and node.is_integer():
        return int(node)
    return node


def normalize(doc):
    defs = {}
    _collect_defs(doc, defs)
    return _normalize(copy.deepcopy(doc), defs)


# ── diff ──────────────────────────────────────────────────────────────────────

def diff(ours, ref, path, out):
    if isinstance(ours, dict) and isinstance(ref, dict):
        for k in sorted(set(ours) | set(ref)):
            p = f"{path}.{k}" if path else k
            if k not in ours:
                out.append(("MISSING (in ours)", p, None, ref[k]))
            elif k not in ref:
                out.append(("EXTRA (not in reference)", p, ours[k], None))
            else:
                diff(ours[k], ref[k], p, out)
    elif isinstance(ours, list) and isinstance(ref, list):
        if len(ours) != len(ref):
            out.append(("LIST LENGTH", path, len(ours), len(ref)))
        for i, (a, b) in enumerate(zip(ours, ref)):
            diff(a, b, f"{path}[{i}]", out)
    else:
        if ours != ref:
            out.append(("VALUE", path, ours, ref))


# ── run ───────────────────────────────────────────────────────────────────────

ours_raw = build_irs_trade_state(input_data)
with open(REF) as f:
    ref_raw = json.load(f)

with open('v2/tests/out_irs-fixedfloat.json', 'w') as f:
    json.dump(ours_raw, f, indent=2)

ours = normalize(ours_raw)
ref = normalize(ref_raw)

diffs = []
diff(ours, ref, "", diffs)

print(f"builder output saved: v2/tests/out_irs-fixedfloat.json")
print(f"differences vs reference: {len(diffs)}")
for kind, path, a, b in diffs[:40]:
    print(f"  [{kind}] {path}")
    if a is not None:
        print(f"      ours: {json.dumps(a)[:150]}")
    if b is not None:
        print(f"      ref : {json.dumps(b)[:150]}")
if len(diffs) > 40:
    print(f"  ... and {len(diffs) - 40} more")
if not diffs:
    print("EXACT MATCH (after key normalization)")
