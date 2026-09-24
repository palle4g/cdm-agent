"""
v2/src/agent/extractor.py

Agent extractor: raw legacy trade record -> IRSTradeInput.

Design:
  - Single Claude Opus 4.6 call using tool_use for structured output
    (Anthropic's recommended structured-output pattern: define a tool whose
    input_schema mirrors the target dataclass; force the model to call it;
    read typed args from the tool_use block).
  - The tool's input_schema is generated from the IRSTradeInput dataclass
    tree, so the schema stays in lock-step with v2/src/schemas.
  - The system prompt embeds the mapping-conventions table from the
    ground-truth README as configuration (which raw vocab maps to which CDM
    values). The agent's job is extraction, not vocabulary invention.

Public API:
    extract_irs_trade(raw_text: str, fmt_hint: str, *, model=..., verbose=False)
        -> IRSTradeInput

Environment: reads ANTHROPIC_API_KEY (from .env if present).
"""
from __future__ import annotations
import os, json, dataclasses, typing
from typing import Optional, List, Any

from dotenv import load_dotenv
import anthropic

from v2.src.schemas.interest_rate_swap import (
    IRSTradeInput, LegInput, PartyInput, TradeIdentifierInput,
)

load_dotenv(".env")

MAX_TOKENS = 8000


# ── dataclass -> JSON Schema (recursive) ─────────────────────────────────────

_PRIMITIVES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _dc_schema(cls) -> dict:
    props, required = {}, []
    for f in dataclasses.fields(cls):
        prop, is_required = _field_schema(f)
        props[f.name] = prop
        if is_required:
            required.append(f.name)
    schema = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


def _field_schema(f: dataclasses.Field) -> tuple[dict, bool]:
    ann = f.type
    schema = _type_schema(ann)
    has_default = (f.default is not dataclasses.MISSING
                   or f.default_factory is not dataclasses.MISSING)
    is_required = not has_default and not _is_optional(ann)
    return schema, is_required


def _is_optional(ann) -> bool:
    if typing.get_origin(ann) is typing.Union:
        return type(None) in typing.get_args(ann)
    return False


def _type_schema(ann) -> dict:
    origin = typing.get_origin(ann)
    if origin is typing.Union:
        non_none = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(non_none) == 1:
            return _type_schema(non_none[0])
        return {"anyOf": [_type_schema(a) for a in non_none]}
    if origin in (list, List):
        item_type = typing.get_args(ann)[0]
        return {"type": "array", "items": _type_schema(item_type)}
    if isinstance(ann, type):
        if ann in _PRIMITIVES:
            return {"type": _PRIMITIVES[ann]}
        if dataclasses.is_dataclass(ann):
            return _dc_schema(ann)
    return {}   # fallback: accept anything


IRS_TRADE_SCHEMA = _dc_schema(IRSTradeInput)


# ── system prompt: mapping conventions the agent needs ───────────────────────

SYSTEM_PROMPT = """\
You extract fields from a raw legacy trade record into a strict schema.
The target schema is `IRSTradeInput` from an Interest Rate Swap mapping
pipeline; you will call the `emit_irs_trade` tool with its fields.

TASK
Read the raw record and emit exactly one call to `emit_irs_trade`. Every
field must come from the record — do not invent parties, dates, indices,
notionals, rates, or identifiers. If the record does not say something, omit
that field (do not guess a default).

═══════════════════════════════════════════════════════════════════════════
 CRITICAL RULES — read these before anything else
═══════════════════════════════════════════════════════════════════════════

1. NEVER INVENT DATA. If the input doesn't state a master agreement,
   confirmation, party name, identifier type, or any other field, leave it
   out entirely. A missing field is better than a wrong one.

2. ALWAYS EXTRACT isda_taxonomy. Every record names a product type or
   classification (e.g. "PRODUCT=IRS", "SUBTYPE=FIXED_FLOAT", "product_code=
   IRS_OIS", "PRODUCT=IRS BASIS"). Map it to the ISDA taxonomy code:
     IRS fixed/float         -> "InterestRate_IRSwap_FixedFloat"
     IRS fixed/float OIS     -> "InterestRate_IRSwap_FixedFloat_OIS"
     IRS fixed/float zero    -> "InterestRate_IRSwap_FixedFloat_ZeroCoupon"
     IRS basis (float/float) -> "InterestRate_IRSwap_Basis"
     IRS basis OIS           -> "InterestRate_IRSwap_Basis_OIS"
     Cross-currency fixed/fixed  -> "InterestRate_CrossCurrency_FixedFixed"
     Cross-currency fixed/float  -> "InterestRate_CrossCurrency_FixedFloat"
     Cross-currency basis        -> "InterestRate_CrossCurrency_Basis"
   Set isda_taxonomy to this value. It is NOT optional — every IRS trade
   has one. A trade with two different leg currencies is cross-currency.

3. LEG TYPE DISCRIMINATION. A leg is "fixed" if and only if a fixed rate
   value is given for it (e.g. RATE=0.20 PCT, fixed_rate_pct=3.537,
   "Fixed Rate: 3.00 per cent"). A leg is "floating" if it names a floating
   rate index (e.g. INDEX=EUR-EONIA-AVERAGE, rate_index=GBP-SONIA).
   Never emit a floating leg when the input says TYPE=FIXED with a rate
   value, and never emit a fixed leg when the input names an index.

4. RESET BLOCK — ALWAYS POPULATE FOR FLOATING LEGS that have any reset or
   fixing information. If the input gives reset frequency, fixing offset,
   or reset-relative-to for a floating leg, you MUST emit ALL of:
     reset_freq_multiplier, reset_freq_period, reset_bdc,
     fixing_offset_multiplier, fixing_offset_period, fixing_bdc
   The builder suppresses the entire reset block when reset_freq_multiplier
   is None, so omitting it silently drops all reset/fixing data.
   If the input gives NO reset frequency, fixing lag, or reset-relative-to
   for a floating leg, leave the entire reset block absent — do not infer
   one from the index type or market convention.

5. FREQUENCY FIELDS ARE ALWAYS SPLIT INTO multiplier + period.
   WRONG: period="3M"   (compound form — NEVER do this)
   RIGHT: calc_period_multiplier=3, calc_period="M"
   This applies to calc_period, payment_freq, reset_freq, index_tenor,
   fixing_offset, and payment_offset. The period value is always a single
   letter: "M", "Y", "W", "D", "T".

6. FIXING OFFSET SIGN. The fixing_offset_multiplier is NEGATIVE when the
   fixing happens BEFORE the reset date. "2 Business Days prior" or
   "2D PRIOR" means fixing_offset_multiplier = -2, not +2. "0 days" is 0.

7. PARTY NAMES — preserve the FULL name as given, including any parenthesized
   suffix. "A BANK("ABANK")" is the complete name; do not truncate it to
   "A BANK". Same for "SELL SECURITIES CO LTD ("Counterparty")".

8. PARTIES WITHOUT LEI. When a party is identified only by a generic label
   (e.g. "Party 1", "Party 2") or a dummy/test identifier:
   - lei field = the identifier value AS GIVEN (e.g. "Party 1", "Bank A")
   - Do NOT set id_type (omit it entirely) — only set id_type="LEI" when
     the record provides an actual LEI code (17+ alphanumeric chars)
   - Do NOT set party name when the only name is the same as the identifier
     label (e.g. don't set name="Party 1" when lei="Party 1" — it's redundant)
   - For dummy/test environments: lei_scheme =
       http://www.fpml.org/coding-scheme/dummy-party-id
     and do NOT set id_type.
   - For generic FpML-external identifiers: lei_scheme =
       http://www.fpml.org/coding-scheme/external

9. TERMINATION DATE vs FIRST PERIOD START DATE. These are different:
   - termination_date = when the trade ENDS (the maturity date, usually
     years in the future from the effective date)
   - first_period_start_date = when the first calculation period begins
     (often the trade date, before the effective date)
   Never use the first period start date or effective date as the
   termination date. READ EACH DATE FIELD INDEPENDENTLY — do not let the
   year from one date bleed into another. Example:
     Trade Date: 20 February 2018
     Effective Date: 22 February 2018
     Termination Date: 22 February 2020    <- NOTE: year is 2020, not 2018
     First Period Start: 20 February 2018
   Here termination_date = "2020-02-22" (not 2018). The day/month may
   match the effective date but the YEAR is different — read it from the
   termination line itself.

   reset_relative_to: ONLY set this when the record EXPLICITLY states what
   resets are relative to (e.g. "PERIOD_START", "CALC_PERIOD_END",
   "RSTREL=PERIOD-START"). If the record is silent, OMIT it.

10. DATE READING — READ EACH DATE FROM ITS OWN LABEL. When several dates
    appear close together, read each one from its own line/field only.
    Example from a confirmation letter:
      Trade Date:              20 February 2018   -> trade_date = 2018-02-20
      Effective Date:          22 February 2018   -> effective_date = 2018-02-22
      Termination Date:        22 February 2020   -> termination_date = 2020-02-22
      First Period Start Date: 20 February 2018   -> first_period_start_date = 2018-02-20
    The day "20" in Trade Date and First Period Start Date is not the same
    as the day "22" in Effective Date. Read the DAY from each line
    independently — do not copy the day from a nearby date.
    Date format rule: "DD Month YYYY" means day=DD, not any digits from
    YYYY. In "20 February 2018": day=20, month=02, year=2018. The "18"
    at the end of the year is NOT the day. Always take the FIRST number
    in the date string as the day.

═══════════════════════════════════════════════════════════════════════════
 MAPPING CONVENTIONS (raw vocab -> the value you must emit)
═══════════════════════════════════════════════════════════════════════════

Party identifiers
  - Any Legal Entity Identifier (LEI, 20 chars alphanumeric): lei_scheme =
      http://www.fpml.org/coding-scheme/external/iso17442
      id_type = "LEI"
  - Generic external party (no LEI recorded, e.g. "Party 1"): lei_scheme =
      http://www.fpml.org/coding-scheme/external
      Do NOT set id_type.
  - Dummy party (test environments, e.g. "Bank A"): lei_scheme =
      http://www.fpml.org/coding-scheme/dummy-party-id
      Do NOT set id_type.

Party name labels: when the record lists a party under a short label
  such as "Party A" / "Party B" (even as a table row heading rather than
  prose, e.g. "Party A: LEI 5493...") treat that label as the party's name
  — set PartyInput.name to it. Do not skip a name just because it appears
  as a heading rather than a full legal entity name.

Party1/Party2 role assignment
  The party1_key and party2_key fields identify which party plays which
  counterparty role. Read them from the input record:
  - If the record says "PARTY_1=<name>" or "cpty_role=PARTY_1", that party's
    key is party1_key.
  - If the record says "Party 1 pays leg 1", the party identified as
    "Party 1" in the parties section is party1_key.
  - On legs, payer/receiver use "Party1" / "Party2" (these are the CDM
    counterparty role names, not the party keys).

Trade identifiers
  - VREFDUAL=Y (or equivalent "same ref assigned by both parties"): emit
    TWO TradeIdentifierInput entries with the same id_value and id_scheme,
    one with issuer_key = party1 key and one with issuer_key = party2 key.
  - Universal Transaction Identifier (UTI): id_scheme =
      http://www.fpml.org/coding-scheme/external/uti
  - SwapsWire venue trade id: id_scheme =
      http://www.swapswire.com/spec/2001/trade-id-1-0
  - partyA internal id: http://www.partyA.com/swaps/trade-id
  - BankA/BankB commodity trade ids: each bank's ref is captured in
    the OTHER bank's scheme:
      party1/partyA ref -> issuer_key=party1, id_scheme=http://www.bankB.com/swaps/com-trade-id
      party2/partyB ref -> issuer_key=party2, id_scheme=http://www.bankA.com/swaps/com-trade-id
  - issuer_key is the party key that issued the identifier.

Identifier type conversion: when the record names a specific identifier
  type in prose (e.g. "Unique Swap Identifier", "Unique Transaction ID",
  "Unique Product Identifier"), convert it to PascalCase with no spaces
  for identifier_type:
    "Unique Swap Identifier" / "USI"  -> "UniqueSwapIdentifier"
    "Unique Transaction ID" / "UTI"   -> "UniqueTransactionIdentifier"
  Always set identifier_type when the record names the identifier's type,
  even informally or abbreviated.

Known regulatory identifier schemes:
  USI (Unique Swap Identifier) scheme ->
    http://www.fpml.org/coding-scheme/external/usi
  CFTC NSA (National Swap Data Repository / NSA) issuer scheme ->
    http://www.fpml.org/coding-scheme/external/nsa/cftc
  These are specific FpML coding-scheme URIs — use them exactly as given
  here; do not invent a different domain (e.g. a cftc.gov URL) even if the
  record only describes the scheme in words ("CFTC NSA coding scheme").

Master agreement / documentation
  - "ISDA Master" -> master_agreement_type = "ISDAMaster",
      master_agreement_scheme =
      http://www.swapswire.com/spec/2001/master-agreement-type-1-0
  - "Confirmation exists"/"CONF=Y" AND either a confirmation definitions
    vintage is named (e.g. "ISDA2006") or the record explicitly states
    a confirmation -> has_confirmation = true; confirmation_definitions
    if a vintage is named.
  - Do NOT set has_confirmation=true or emit contractDetails just because
    the raw record is formatted as a "Confirmation letter" — only set it
    when the record has an explicit field or statement about a bilateral
    confirmation agreement (e.g. "CONF=Y", "confirmation_exists: true",
    "CONFDEF=ISDA2006"). A trade confirmation letter is the record FORMAT,
    not a statement that a confirmation agreement exists.

Product identifier (commodity/GTR)
  - product_id_scheme =
      http://www.dtcc.com/coding-scheme/external/GTR-Product-Id
  - product_id_source = "Other"

other_taxonomy
  - If the record has a classification like "InterestRate::VanillaSwap"
    or "CLASSIFICATION=InterestRate::VanillaSwap", set other_taxonomy.

primary_asset_class
  - If the record names a primary asset class (e.g. "Commodity"),
    set primary_asset_class.

Business Day Conventions (BDC) — normalize:
  MF, ModFoll, Modified Following, MOD FOLL -> MODFOLLOWING
  Preceding                                 -> PRECEDING
  None, NONE                                -> NONE
  Following                                 -> FOLLOWING

Day Count Fractions (DCF):
  A/360, Actual/360           -> ACT/360
  ACT/365F, Actual/365 Fixed, ACT/365F -> ACT/365.FIXED
  ACT/ACT ISDA                -> ACT/ACT.ISDA
  30E/360                     -> 30E/360

Frequencies and periods — ALWAYS split:
  "3M" -> multiplier=3, period="M"
  "1Y" -> multiplier=1, period="Y"
  "1W" -> multiplier=1, period="W"
  "1D" -> multiplier=1, period="D"
  "0D" -> multiplier=0, period="D"
  NEVER emit period="3M" — that is the compound form.

Roll convention:
  Emit as a string with NO leading zeros. ROLL=09 -> "9", ROLL=16 -> "16",
  ROLL=1 -> "1". Read the value literally from the input; do not substitute
  "NONE" unless the input actually says NONE or the roll convention is absent.

Pay/reset relative-to:
  PERIOD_END / at period end / CALC_PERIOD_END -> CalculationPeriodEndDate
  PERIOD_START / at period start               -> CalculationPeriodStartDate

Rate quotes (emit as decimals, not percent):
  "0.20 PCT", "0.20%", "20 bps"    -> 0.002
  "3.537 (pct)", "3.537%"          -> 0.03537
  "3.00 per cent per annum"        -> 0.03
  "-1BP"                            -> -0.0001

Fixing offset sign:
  "2 Business Days prior"  -> fixing_offset_multiplier = -2
  "2D PRIOR"               -> fixing_offset_multiplier = -2
  "0 days" / "0D"          -> fixing_offset_multiplier = 0

  The multiplier is NEGATIVE when the fixing is BEFORE the reset date.
  Only use a positive value when the fixing is AFTER the reset date.

Fixing dayType:
  Only emit fixing_offset_day_type when the record explicitly says
  "Business" or "TYPE=BUSINESS" or "Business Days". If the fixing is
  "0D" with no day type mentioned, omit fixing_offset_day_type.

Calculation agent:
  role "INDEPENDENT" / "independent calc agent" / "CALC_AGENT_STYLE=
  INDEPENDENT" -> set calc_agent_key to that party's key.

Business centers:
  A named centers reference like "PRIMARY" / "primary business
  centers" / "CENTERS=PRIMARY" -> external key "primaryBusinessCenters"
  on the relevant *_bc_ref fields (effective_date_bc_ref,
  termination_date_bc_ref, calc_period_bc_ref, payment_bc_ref,
  fixing_bc_ref, reset_bc_ref).
  Set ONLY the refs the record actually places on each date. If leg 1's
  effective date carries no center reference but leg 2's does, reflect
  that exactly. Do not blanket-apply centers to all dates unless the
  record does.

Unnamed floating index (e.g. GOFO): floating_index_is_named = false.
  The value still goes in floating_index (as the identifier).

Upfront/fee payment:
  Populate upfront_payment_* fields when the record describes a one-off
  fee at trade or effective date; identify payer/receiver by party key.

Zero-coupon / single-payment legs:
  When the record says "single payment at Termination" or "zero coupon"
  or the period covers the entire term:
    calc_period_multiplier=1, calc_period="T", roll_convention="NONE"
    payment_freq_multiplier=1, payment_freq_period="T"

LEG payer/receiver:
  Use "Party1" / "Party2" (matching counterparty roles). "PARTY1 pays"
  / "we_pay when we are Party1" / "CPTY1_PAYS" / "paid by Party1" ->
  payer="Party1", receiver="Party2".

Amounts:
  Emit notional_amount as a plain number (no commas, no currency code
  inside the value). notional_currency is a 3-letter code (or "XAU").

═══════════════════════════════════════════════════════════════════════════
 CROSS-CURRENCY SWAPS — additional fields
═══════════════════════════════════════════════════════════════════════════
These fields apply ONLY to cross-currency trades (two different leg
currencies). Do not set them for single-currency trades.

Principal exchange (principal_initial / principal_final / principal_intermediate):
  Cross-currency swaps exchange principal; single-currency swaps normally
  do not. Read which exchanges occur:
    "INITIAL,FINAL,INTERMEDIATE" / "Initial, Final, and Intermediate"
      -> principal_initial=true, principal_final=true, principal_intermediate=true
    "Intermediate only" -> only principal_intermediate=true
  If the record gives actual exchange AMOUNTS and DATES for the initial and
  final exchange (not just a yes/no), populate principal_schedule with:
    initial_date, initial_payer, initial_receiver, initial_amount, initial_currency
    final_date, final_payer, final_receiver, final_amount, final_currency
  If only booleans are given (no amounts/dates), leave principal_schedule unset.

Named date keys (cpd_key, payment_dates_key, reset_dates_key):
  Only set these when the record shows one leg's dates are referenced by
  another part of the trade (most commonly: an FX-linked notional on this
  leg references this leg's own reset or payment dates "relative to the
  leg's own reset dates" / "relative to the leg's own payment dates").
  Use a short descriptive name (e.g. "floatingResetDates",
  "floatingPaymentDates", "fixedCalcPeriodDatesJPY"). If nothing references
  a leg's dates, leave these unset — the builder assigns positional keys.

FX-linked notional (fx_linked_notional on a leg):
  Set this when the record says a leg's notional is FX-linked, FX-reset,
  mark-to-market, or "notional recalculated from an FX fixing" — i.e. there
  is NO static notional amount for that leg. Populate:
    varying_notional_currency: the currency the notional is expressed in
    fixing_offset_multiplier/period/day_type/bdc: when the FX rate is fixed,
      relative to a reference date (see date_relative_to_key)
    date_relative_to_key: the named key (see above) of the date the FX
      fixing is relative to — either this leg's own reset dates/payment
      dates key, or "tradeDate" if relative to the trade date itself
    source_provider: the FX rate source (e.g. "BankOfJapan", "Telerate")
    source_page / source_page_heading: only if the record names a specific
      quote page (e.g. "WM Company LDN 11am Mid", heading "USD/EUR")
    fixing_time, fixing_business_center: the time and center the FX rate
      is observed (e.g. "17:00:00", "JPTO")
    interim_multiplier/period/day_type/bdc: offset for interim exchange
      payment dates (often "0 days" — same as the reset/payment date)
    interim_date_relative_to_key: same rule as date_relative_to_key, for
      the interim exchange payment date
  When a leg has fx_linked_notional set, notional_amount may still be
  populated if the record gives a current/static notional value alongside
  the FX-linked schedule (e.g. "current notional: USD 2,034.95, subject to
  FX reset each period") — report BOTH in that case. Only leave
  notional_amount as None if the record gives no value at all for that leg.

  PAIRING RULE: whenever you set fx_linked_notional on a leg, you MUST also
  set quantity_reference_key on that same leg (invent a short descriptive
  key if the record doesn't literally name one, e.g. "notionalScheduleJPY").
  The two fields always go together in the CDM shape — never set one
  without the other.

  OFFSET SIGN — do not confuse this with the periodic reset-fixing
  convention above. fixing_offset_multiplier and interim_multiplier on an
  FX-linked notional are a SEPARATE concept from a leg's own reset/fixing
  offset, and are NOT assumed negative by default. Read the explicit
  direction word in the record:
    "before" / "prior to" / "preceding" the reference date -> negative
    "after" / "following" the reference date               -> positive
  If the record gives a lag with NO direction word at all, do not guess —
  ask yourself whether the record says "before"/"after" anywhere nearby;
  if truly silent on direction, prefer a positive value (the reference
  date is usually the earliest point the fixing could occur relative to).

quantity_reference_key:
  Set this to a dangling external key name (invented, descriptive — e.g.
  "notionalScheduleJPY", "fixed_notional_schedule") when the record
  describes an FX-linked notional but does not literally name the
  cross-reference key. This models the CDM quantityReference field, which
  in real trades often points to a schedule maintained elsewhere.

settlement_currency:
  Set per-leg when the record specifies a settlement currency distinct
  from the notional currency conversation (common in xccy basis swaps
  with cash settlement terms).

cashflow_matches_parameters:
  Set to false when the record explicitly states cashflows do not match
  the calculated parameters (a compliance/booking flag in complex xccy
  trades). Omit entirely if not mentioned.

tradedate_key:
  Set IRSTradeInput.tradedate_key = "tradeDate" only when the record shows
  an FX-linked notional referencing the trade date itself (date_relative_to_key
  or interim_date_relative_to_key = "tradeDate"). Otherwise leave unset.

additional_taxonomies:
  Populate with TaxonomyInput entries when the record gives product
  classification codes beyond the ISDA taxonomy:
    CFI code (ISO 10962)            -> source="CFI", value=<code>,
                                        value_scheme=http://www.fpml.org/coding-scheme/external/product-classification/iso10962
    EMIR contract type              -> source="EMIR", value=<code>,
                                        value_scheme=http://www.dtcc.com/coding-scheme/external/product-classification/emir-contract-type
  primary_asset_class (e.g. "InterestRate") goes on IRSTradeInput directly,
  not in additional_taxonomies.

Trade identifiers with direct issuer LEI (no party cross-reference):
  When a trade identifier's issuer is given as an LEI/scheme directly,
  rather than a reference to a party already listed in parties[], use
  issuer_lei + issuer_scheme on TradeIdentifierInput instead of issuer_key.

CDM envelope constants (for reference only — set by the builder, not you):
  @model=cdm, @type=cdm.event.common.TradeState,
  @version=0.0.0.master-SNAPSHOT
"""


TOOL = {
    "name": "emit_irs_trade",
    "description": ("Emit the extracted IRS trade as a single structured "
                    "object matching the IRSTradeInput schema."),
    "input_schema": IRS_TRADE_SCHEMA,
}


# ── build IRSTradeInput from the tool call's JSON ────────────────────────────

def _from_dict(cls, data: dict):
    """Recursively build a dataclass instance from a dict, ignoring extras."""
    if data is None:
        return None
    kwargs = {}
    field_types = {f.name: f.type for f in dataclasses.fields(cls)}
    for name, val in data.items():
        if name not in field_types:
            continue
        kwargs[name] = _coerce(field_types[name], val)
    return cls(**kwargs)


def _coerce(ann, val):
    if val is None:
        return None
    origin = typing.get_origin(ann)
    if origin is typing.Union:
        non_none = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(non_none) == 1:
            return _coerce(non_none[0], val)
    if origin in (list, List):
        item_type = typing.get_args(ann)[0]
        return [_coerce(item_type, v) for v in val]
    if isinstance(ann, type) and dataclasses.is_dataclass(ann):
        return _from_dict(ann, val)
    return val


# ── public entry point ──────────────────────────────────────────────────────

def extract_irs_trade_with_model(
    raw_text: str,
    fmt_hint: str,
    model: str,
    *,
    verbose: bool = False,
) -> IRSTradeInput:
    """Extract a trade using the given model. Called by extractor_sonnet.py / extractor_opus.py."""
    client = anthropic.Anthropic()   # picks up ANTHROPIC_API_KEY from env
    user_msg = (
        f"Format hint: {fmt_hint}\n\n"
        f"Raw record:\n----- BEGIN RECORD -----\n"
        f"{raw_text}\n"
        f"----- END RECORD -----\n\n"
        f"Extract the trade and call `emit_irs_trade` exactly once."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "emit_irs_trade"},
        messages=[{"role": "user", "content": user_msg}],
    )

    tool_block = next((b for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        text = "".join(getattr(b, "text", "") for b in resp.content)
        raise RuntimeError(f"model did not call emit_irs_trade. Response: {text[:500]}")

    if verbose:
        print(json.dumps(tool_block.input, indent=2))
        print(f"[usage] in={resp.usage.input_tokens} out={resp.usage.output_tokens}")

    return _from_dict(IRSTradeInput, tool_block.input)


# ── CLI for a quick manual smoke test ───────────────────────────────────────

