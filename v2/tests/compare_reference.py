"""
v2/tests/compare_reference.py

Builds each single-currency IRS reference trade with the plain-dict builder
and diffs the output against the FINXIS reference file. Supersedes
compare_fixedfloat.py.

Normalization before comparing (both sides):
  - '@key' / '@ref' bare hash ids (generator artifacts) dropped
  - key ids canonicalised by the JSON path of their FIRST REFERENCE (S1..,
    E1..) and refs remapped, so id spellings AND definition-encounter
    order don't count as diffs. Two structurally identical docs get the
    same canonical names even if their `party[]` and `counterparty[]`
    sections were emitted in a different sequence.
  - key definitions that nothing references are dropped (cosmetic)
  - refs to keys defined nowhere in the file become 'UNRESOLVED:<id>' on
    both sides (e.g. basis-ois's dangling 'primaryBusinessCenters')

Wrong ref targets still surface as diffs (at the ref site or at the
downstream sibling values), so the fairness fix does not mask real bugs.

Run from repo root:  python v2/tests/compare_reference.py [name ...]
Names: fixedfloat, ois, zerocoupon, basis, basis-ois (default: all)
"""
import sys, json, copy
sys.path.insert(0, '.')

from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput
)
from v2.src.builders.cdm_builder import build_irs_trade_state

REF_DIR = 'v2/data/reference/interest_rate_swap'

LEI_SCHEME = "http://www.fpml.org/coding-scheme/external/iso17442"
SWAPSWIRE_TID = "http://www.swapswire.com/spec/2001/trade-id-1-0"
SWAPSWIRE_MA = "http://www.swapswire.com/spec/2001/master-agreement-type-1-0"

PARTY_A = PartyInput(key="partyA", lei="549300ABANKV6BYQOWM67",
                     lei_scheme=LEI_SCHEME, id_type="LEI", name='A BANK("ABANK")')
PARTY_B = PartyInput(key="partyB", lei="529900CPTY57S5UCBB52",
                     lei_scheme=LEI_SCHEME, id_type="LEI",
                     name='SELL SECURITIES CO LTD ("Counterparty")')


def _fixedfloat():
    return IRSTradeInput(
        trade_date="2018-11-15", trade_id="FpML-test-7",
        isda_taxonomy="InterestRate_IRSwap_FixedFloat",
        other_taxonomy="InterestRate::VanillaSwap",
        parties=[PARTY_A, PARTY_B,
                 PartyInput(key="dco", lei="123456QQQQ57S5UCBB11",
                            lei_scheme=LEI_SCHEME, id_type="LEI",
                            name="ABC CENTRAL PARTY CLEARING SVC LTD")],
        party1_key="partyB", party2_key="partyA",
        trade_identifiers=[TradeIdentifierInput(
            issuer_key="partyA",
            id_scheme="http://www.partyA.com/swaps/trade-id",
            id_value="FpML-test-7")],
        calc_agent_key="partyA",
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=3672000000, notional_currency="EUR",
                     floating_index="EUR-EONIA-AVERAGE", day_count_fraction="ACT/360",
                     effective_date="2018-11-16", effective_date_bdc="NONE",
                     termination_date="2023-11-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="NONE",
                     calc_period_multiplier=1, calc_period="M", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     payment_offset_multiplier=1, payment_offset_period="D",
                     payment_offset_day_type="Business"),
            LegInput(payer="Party2", receiver="Party1", leg_type="fixed",
                     notional_amount=3672000000, notional_currency="EUR",
                     fixed_rate=0.002, day_count_fraction="ACT/360",
                     effective_date="2018-11-16", effective_date_bdc="NONE",
                     termination_date="2023-11-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="NONE",
                     calc_period_multiplier=1, calc_period="M", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     payment_offset_multiplier=1, payment_offset_period="D",
                     payment_offset_day_type="Business"),
        ])


def _ois():
    return IRSTradeInput(
        trade_date="2023-02-16", trade_id="FpML-test-7c",
        isda_taxonomy="InterestRate_IRSwap_FixedFloat_OIS",
        parties=[PARTY_A, PARTY_B],
        party1_key="partyA", party2_key="partyB",
        trade_identifiers=[TradeIdentifierInput(
            issuer_key="partyA",
            id_scheme="http://www.partyA.com/swaps/trade-id",
            id_value="FpML-test-7c")],
        master_agreement_type="ISDAMaster", master_agreement_scheme=SWAPSWIRE_MA,
        has_confirmation=True,
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=1100000, notional_currency="GBP",
                     floating_index="GBP-SONIA-OIS Compound",
                     day_count_fraction="ACT/365.FIXED",
                     effective_date="2023-02-16", effective_date_bdc="NONE",
                     termination_date="2033-02-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=1, calc_period="Y", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="Y",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodEndDate",
                     fixing_offset_multiplier=0, fixing_offset_period="D",
                     fixing_bdc="PRECEDING",
                     reset_freq_multiplier=1, reset_freq_period="Y",
                     reset_bdc="MODFOLLOWING"),
            LegInput(payer="Party2", receiver="Party1", leg_type="fixed",
                     notional_amount=1100000, notional_currency="GBP",
                     fixed_rate=0.03537, day_count_fraction="ACT/365.FIXED",
                     effective_date="2023-02-16", effective_date_bdc="NONE",
                     termination_date="2033-02-16", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=1, calc_period="Y", roll_convention="16",
                     payment_freq_multiplier=1, payment_freq_period="Y",
                     payment_bdc="MODFOLLOWING"),
        ])


def _zerocoupon():
    return IRSTradeInput(
        trade_date="2018-02-20", trade_id="IRS858TH30",
        isda_taxonomy="InterestRate_IRSwap_FixedFloat_ZeroCoupon",
        parties=[
            PartyInput(key="party1", lei="Party 1",
                       lei_scheme="http://www.fpml.org/coding-scheme/external"),
            PartyInput(key="party2", lei="Party 2",
                       lei_scheme="http://www.fpml.org/coding-scheme/external"),
        ],
        party1_key="party1", party2_key="party2",
        trade_identifiers=[TradeIdentifierInput(
            issuer_key="party1",
            id_scheme="http://www.fpml.org/coding-scheme/external/uti",
            id_value="IRS858TH30", id_version=1)],
        upfront_payment_amount=200, upfront_payment_currency="USD",
        upfront_payment_date="2018-02-22",
        upfront_payer_key="party1", upfront_receiver_key="party2",
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="fixed",
                     notional_amount=100000, notional_currency="GBP",
                     fixed_rate=0.03, day_count_fraction="30E/360",
                     effective_date="2018-02-22", effective_date_bdc="MODFOLLOWING",
                     termination_date="2020-02-22", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     first_period_start_date="2018-02-20",
                     calc_period_multiplier=1, calc_period="T", roll_convention="NONE",
                     payment_freq_multiplier=1, payment_freq_period="T",
                     payment_bdc="MODFOLLOWING"),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=100000, notional_currency="GBP",
                     floating_index="GBP-LIBOR-ISDA",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     day_count_fraction="ACT/360",
                     effective_date="2018-02-22", effective_date_bdc="MODFOLLOWING",
                     termination_date="2020-02-22", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="NONE",
                     first_period_start_date="2018-02-20", first_period_start_bdc="NONE",
                     calc_period_multiplier=3, calc_period="M", roll_convention="22",
                     payment_freq_multiplier=1, payment_freq_period="T",
                     payment_bdc="MODFOLLOWING",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING",
                     compounding_method="Flat"),
        ])


def _basis():
    return IRSTradeInput(
        trade_date="2021-04-07", trade_id="58005869",
        isda_taxonomy="InterestRate_IRSwap_Basis",
        parties=[PARTY_A, PARTY_B],
        party1_key="partyA", party2_key="partyB",
        trade_identifiers=[
            TradeIdentifierInput(issuer_key="partyA",
                                 id_scheme=SWAPSWIRE_TID, id_value="58005869"),
            TradeIdentifierInput(issuer_key="partyB",
                                 id_scheme=SWAPSWIRE_TID, id_value="58005869"),
        ],
        master_agreement_type="ISDAMaster", master_agreement_scheme=SWAPSWIRE_MA,
        has_confirmation=True, confirmation_definitions="ISDA2006",
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=150000000, notional_currency="USD",
                     floating_index="USD-SIFMA Municipal Swap Index",
                     day_count_fraction="ACT/ACT.ISDA",
                     effective_date="2021-04-09", effective_date_bdc="NONE",
                     termination_date="2026-04-09", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="9",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=0, fixing_offset_period="D",
                     fixing_bdc="PRECEDING",
                     reset_freq_multiplier=1, reset_freq_period="W",
                     reset_bdc="MODFOLLOWING"),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=150000000, notional_currency="USD",
                     floating_index="USD-LIBOR-BBA",
                     index_tenor_multiplier=3, index_tenor_period="M",
                     day_count_fraction="ACT/360",
                     effective_date="2021-04-09", effective_date_bdc="NONE",
                     termination_date="2026-04-09", termination_date_bdc="MODFOLLOWING",
                     calc_period_bdc="MODFOLLOWING",
                     calc_period_multiplier=3, calc_period="M", roll_convention="9",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     payment_bdc="MODFOLLOWING",
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING"),
        ])


def _basis_ois():
    BC = "primaryBusinessCenters"   # dangling reference, as in the source file
    return IRSTradeInput(
        trade_date="2021-08-18", trade_id="BankA1234",
        isda_taxonomy="InterestRate_IRSwap_Basis_OIS",
        primary_asset_class="Commodity",
        product_id_value="Commodity:Metals:Precious:LoanLease:Cash",
        product_id_scheme="http://www.dtcc.com/coding-scheme/external/GTR-Product-Id",
        product_id_source="Other",
        parties=[
            PartyInput(key="party1", lei="Bank A",
                       lei_scheme="http://www.fpml.org/coding-scheme/dummy-party-id",
                       name="Bank a"),
            PartyInput(key="party2", lei="Bank B",
                       lei_scheme="http://www.fpml.org/coding-scheme/dummy-party-id",
                       name="Bank B"),
        ],
        party1_key="party1", party2_key="party2",
        trade_identifiers=[
            TradeIdentifierInput(issuer_key="party1",
                                 id_scheme="http://www.bankB.com/swaps/com-trade-id",
                                 id_value="BankA1234"),
            TradeIdentifierInput(issuer_key="party2",
                                 id_scheme="http://www.bankA.com/swaps/com-trade-id",
                                 id_value="BankB5678"),
        ],
        has_confirmation=True,
        legs=[
            LegInput(payer="Party1", receiver="Party2", leg_type="floating",
                     notional_amount=100, notional_currency="XAU",
                     floating_index="USD-SOFR-OIS Compound",
                     day_count_fraction="ACT/365.FIXED",
                     effective_date="2021-08-18", effective_date_bdc="MODFOLLOWING",
                     termination_date="2022-08-18", termination_date_bdc="MODFOLLOWING",
                     termination_date_bc_ref=BC,
                     calc_period_bdc="MODFOLLOWING", calc_period_bc_ref=BC,
                     calc_period_multiplier=3, calc_period="M", roll_convention="1",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     first_payment_date="2021-11-18",
                     payment_bdc="MODFOLLOWING", payment_bc_ref=BC,
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     fixing_bc_ref=BC,
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING", reset_bc_ref=BC),
            LegInput(payer="Party2", receiver="Party1", leg_type="floating",
                     notional_amount=100, notional_currency="XAU",
                     floating_index="GOFO", floating_index_is_named=False,
                     spread=-0.0001,
                     day_count_fraction="ACT/365.FIXED",
                     effective_date="2021-08-18", effective_date_bdc="MODFOLLOWING",
                     effective_date_bc_ref=BC,
                     termination_date="2022-08-18", termination_date_bdc="MODFOLLOWING",
                     termination_date_bc_ref=BC,
                     calc_period_bdc="MODFOLLOWING", calc_period_bc_ref=BC,
                     calc_period_multiplier=3, calc_period="M", roll_convention="1",
                     payment_freq_multiplier=3, payment_freq_period="M",
                     first_payment_date="2021-11-18",
                     payment_bdc="MODFOLLOWING", payment_bc_ref=BC,
                     reset_relative_to="CalculationPeriodStartDate",
                     fixing_offset_multiplier=-2, fixing_offset_period="D",
                     fixing_offset_day_type="Business", fixing_bdc="NONE",
                     fixing_bc_ref=BC,
                     reset_freq_multiplier=3, reset_freq_period="M",
                     reset_bdc="MODFOLLOWING", reset_bc_ref=BC),
        ])


CASES = {
    "fixedfloat": (_fixedfloat, f"{REF_DIR}/swaps/irs-fixedfloat.json"),
    "ois": (_ois, f"{REF_DIR}/swaps/irs-fixedfloat-ois.json"),
    "zerocoupon": (_zerocoupon, f"{REF_DIR}/swaps/irs-fixedfloat-zerocoupon.json"),
    "basis": (_basis, f"{REF_DIR}/cross_currency/irs-basis.json"),
    "basis-ois": (_basis_ois, f"{REF_DIR}/cross_currency/irs-basis-ois.json"),
}


# ── normalization (identity-aware) ────────────────────────────────────────────
# Canonicalize each key id by the JSON PATH of its first reference. Two
# structurally identical docs get the same canonical names regardless of the
# depth-first order in which their key DEFINITIONS happen to be encountered
# (e.g. our builder and the reference emit `party[]` at different positions).
# Wrong ref targets still surface: the failure moves from the ref number
# itself to the downstream sibling values at the target, which is semantically
# the right place for it.

def _walk(node, path, first_ref):
    if isinstance(node, dict):
        for k, v in node.items():
            child_path = f"{path}.{k}" if path else k
            if k == "@ref:scoped":
                first_ref.setdefault(("@key:scoped", v), child_path)
            elif k == "@ref:external":
                first_ref.setdefault(("@key:external", v), child_path)
            else:
                _walk(v, child_path, first_ref)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", first_ref)


def _apply(node, mapping):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in ("@key", "@ref"):
                continue
            if k in ("@key:scoped", "@key:external"):
                if (k, v) in mapping:
                    out[k] = mapping[(k, v)]
                # unreferenced defs dropped (cosmetic)
            elif k == "@ref:scoped":
                out[k] = mapping.get(("@key:scoped", v), f"UNRESOLVED:{v}")
            elif k == "@ref:external":
                out[k] = mapping.get(("@key:external", v), f"UNRESOLVED:{v}")
            else:
                out[k] = _apply(v, mapping)
        return out
    if isinstance(node, list):
        return [_apply(item, mapping) for item in node]
    if isinstance(node, float) and node.is_integer():
        return int(node)
    return node


def normalize(doc):
    first_ref = {}
    _walk(doc, "", first_ref)
    mapping, counters = {}, {"@key:scoped": 0, "@key:external": 0}
    ordered = sorted(first_ref.items(), key=lambda kv: (kv[0][0], kv[1]))
    for (kind, ident), _path in ordered:
        counters[kind] += 1
        prefix = "S" if kind == "@key:scoped" else "E"
        mapping[(kind, ident)] = f"{prefix}{counters[kind]}"
    result = _apply(copy.deepcopy(doc), mapping)
    # Sort party[] by first partyId identifier value so positional order
    # (which is semantically meaningless in CDM) doesn't cause false diffs.
    parties = result.get('trade', {}).get('party', [])
    if parties:
        def _party_sort_key(p):
            ids = p.get('partyId', [{}])
            return ids[0].get('identifier', {}).get('@data', '') if ids else ''
        result['trade']['party'] = sorted(parties, key=_party_sort_key)
    return result


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

def run_case(name, show=25):
    fixture_fn, ref_path = CASES[name]
    ours_raw = build_irs_trade_state(fixture_fn())
    with open(ref_path) as f:
        ref_raw = json.load(f)
    out_path = f"v2/tests/out_{name}.json"
    with open(out_path, 'w') as f:
        json.dump(ours_raw, f, indent=2)
    diffs = []
    diff(normalize(ours_raw), normalize(ref_raw), "", diffs)
    status = "EXACT MATCH" if not diffs else f"{len(diffs)} diffs"
    print(f"{name:12s} {status}   (output: {out_path})")
    for kind, path, a, b in diffs[:show]:
        print(f"    [{kind}] {path}")
        if a is not None:
            print(f"        ours: {json.dumps(a)[:130]}")
        if b is not None:
            print(f"        ref : {json.dumps(b)[:130]}")
    if len(diffs) > show:
        print(f"    ... and {len(diffs) - show} more")
    return len(diffs)


if __name__ == "__main__":
    names = sys.argv[1:] or list(CASES)
    total = sum(run_case(n) for n in names)
    print(f"\ntotal diffs across {len(names)} files: {total}")
