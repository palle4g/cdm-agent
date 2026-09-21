"""
v2/src/builders/ref_resolver.py

Workaround for rune-runtime 2.2.1: BaseDataClass.resolve_references()
does not resolve references inside list-typed reference fields
(e.g. AncillaryParty.partyReference: list[Party | BaseReference | None]).

PR #38 fixed the list-of-objects-containing-references case. This helper
covers the remaining list-that-IS-the-reference case until upstream fix.

Follow-up on: https://github.com/finos/rune-python-runtime/issues/37

Usage:
    ts = TradeState.model_validate(data)
    ts.resolve_references()
    resolve_ancillary_party_refs(ts)     # workaround
    result = ts.rune_serialize()
"""
from rune.runtime.metadata import UnresolvedReference


def _party_lookup(trade):
    """Build {external_key -> Party} from trade.party[]."""
    lookup = {}
    for party in (trade.party or []):
        meta = party.__dict__.get('__rune_metadata', {})
        ext_key = meta.get('@key:external')
        if ext_key:
            lookup[ext_key] = party
    return lookup


def resolve_ancillary_party_refs(trade_state):
    """
    Replace any UnresolvedReference in trade.ancillaryParty[].partyReference[]
    with the actual Party object from trade.party[].
    Silently skips entries whose key doesn't map to any known party.
    """
    trade = trade_state.trade
    if not trade or not trade.ancillaryParty:
        return

    lookup = _party_lookup(trade)

    for ap in trade.ancillaryParty:
        if not ap.partyReference:
            continue
        for i, ref in enumerate(ap.partyReference):
            if isinstance(ref, UnresolvedReference):
                target = lookup.get(ref.key)
                if target is not None:
                    ap.partyReference[i] = target
