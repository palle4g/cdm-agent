"""
Proof-of-concept: map ONE legacy bank trade into the FINOS Common Domain Model.

This is "Step 1: map one trade by hand" -- no AI yet. The point is to prove we
understand the target schema and can produce a CDM object that VALIDATES.
Once this is solid, it becomes the ground-truth eval for an LLM mapping agent.

Product chosen: FX Forward -- the simplest product to reason about.
An FX forward is just: on a future date, party A pays a fixed amount of one
currency and receives a fixed amount of another. Two cashflows, one date.
"""

from decimal import Decimal
import json

from finos.cdm.base.staticdata.party.Party import Party
from finos.cdm.base.staticdata.party.PartyIdentifier import PartyIdentifier
from finos.cdm.observable.asset.Money import Money
from finos.cdm.base.math.UnitType import UnitType
from finos.cdm.event.common.TradeIdentifier import TradeIdentifier


# ---------------------------------------------------------------------------
# 1. THE SOURCE: a synthetic "legacy" trade record.
#    This is the kind of flat, proprietary blob a legacy system (Calypso,
#    Murex, an in-house booking system) might export. Field names are cryptic
#    and non-standard ON PURPOSE -- that's the real-world problem.
# ---------------------------------------------------------------------------
legacy_trade = {
    "TRD_ID":        "FXF-2026-0098213",
    "PROD_TYP":      "FXFWD",
    "CPTY_LEI":      "5493001KJTIIGC8Y1R12",   # counterparty legal entity id
    "OWN_LEI":       "7LTWFZYICNSX8D621K86",    # our bank's legal entity id
    "BUY_CCY":       "EUR",
    "BUY_NOTIONAL":  "10000000.00",
    "SELL_CCY":      "USD",
    "SELL_NOTIONAL": "10850000.00",             # implies a fwd rate of 1.0850
    "VALUE_DATE":    "2026-12-18",
    "TRADE_DATE":    "2026-09-05",
}


# ---------------------------------------------------------------------------
# 2. THE MAPPING: legacy fields -> real CDM objects.
#    Each helper maps one "domain" (party, identifier, money). This mirrors
#    the multi-agent decomposition -- but here each is a plain function you
#    can read and test. An agent, later, just produces this same object.
# ---------------------------------------------------------------------------

def map_party(lei: str, name: str) -> Party:
    """Map a legal-entity id into a CDM Party with an LEI-scheme identifier."""
    return Party(
        partyId=[PartyIdentifier(identifier=lei)],
        name=name,
    )

def map_money(amount: str, currency: str) -> Money:
    """Map an amount + ISO currency code into a CDM Money object."""
    return Money(
        value=Decimal(amount),
        unit=UnitType(currency=currency),
    )

def map_trade_id(trd_id: str) -> TradeIdentifier:
    return TradeIdentifier(assignedIdentifier=[{"identifier": trd_id}])


# ---------------------------------------------------------------------------
# 3. RUN THE MAPPING and validate. Constructing the Pydantic objects IS the
#    validation -- a bad field raises immediately.
# ---------------------------------------------------------------------------
counterparty = map_party(legacy_trade["CPTY_LEI"], "ACME ASSET MGMT")
own_party    = map_party(legacy_trade["OWN_LEI"],  "OUR BANK PLC")

buy_leg  = map_money(legacy_trade["BUY_NOTIONAL"],  legacy_trade["BUY_CCY"])
sell_leg = map_money(legacy_trade["SELL_NOTIONAL"], legacy_trade["SELL_CCY"])

trade_id = map_trade_id(legacy_trade["TRD_ID"])

implied_rate = Decimal(legacy_trade["SELL_NOTIONAL"]) / Decimal(legacy_trade["BUY_NOTIONAL"])

print("=" * 66)
print("LEGACY FX FORWARD  ->  CDM (validated objects)")
print("=" * 66)
print(f"Trade id     : {trade_id.assignedIdentifier[0].identifier}")
print(f"Our party    : {own_party.name}  (LEI {own_party.partyId[0].identifier})")
print(f"Counterparty : {counterparty.name}  (LEI {counterparty.partyId[0].identifier})")
print(f"We receive   : {buy_leg.value:,} {buy_leg.unit.currency}")
print(f"We pay       : {sell_leg.value:,} {sell_leg.unit.currency}")
print(f"Implied fwd rate (SELL/BUY): {implied_rate}")
print(f"Value date   : {legacy_trade['VALUE_DATE']}")
print()

# Serialize one object to canonical CDM JSON to show it's real & round-trips.
print("The 'we receive' leg as canonical CDM JSON:")
print(json.dumps(buy_leg.model_dump(exclude_none=True, by_alias=True), indent=2, default=str))
