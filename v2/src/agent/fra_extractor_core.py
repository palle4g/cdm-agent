"""
v2/src/agent/fra_extractor_core.py

Agent extractor for Forward Rate Agreements: raw legacy record -> FRAInput.
Parallels v2/src/agent/extractor_core.py (the IRS extractor) but targets the
much smaller FRAInput schema, so it is kept as its own module rather than
overloading the IRS prompt/tool with FRA-only concepts.

Public API:
    extract_fra_trade_with_model(raw_text, fmt_hint, model, *, verbose=False)
        -> FRAInput
Called by fra_extractor_sonnet.py / fra_extractor_opus.py.
"""
from __future__ import annotations
import dataclasses, typing
from typing import List

from dotenv import load_dotenv
import anthropic

from v2.src.schemas.fra import FRAInput

load_dotenv(".env")

MAX_TOKENS = 4000


# ── dataclass -> JSON Schema (same small utility as the IRS extractor) ───────

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


def _field_schema(f: dataclasses.Field):
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
    return {}


FRA_SCHEMA = _dc_schema(FRAInput)


# ── system prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You extract fields from a raw legacy trade record into a strict schema for
a Forward Rate Agreement (FRA). You will call the `emit_fra_trade` tool
with FRAInput's fields.

TASK
Read the raw record and emit exactly one call to `emit_fra_trade`. Every
field must come from the record — do not invent parties, dates, indices,
notionals, or rates. If the record doesn't state something, omit that
field rather than guessing.

WHAT A FRA IS
A Forward Rate Agreement has exactly ONE settlement period (not a repeating
schedule): a fixed-rate side and a floating-rate side settle net on a single
payment date, based on a rate observed on a single reset date. There is no
calculation period frequency, no multi-period schedule — just:
  - a reset date (when the floating rate is observed / the period begins)
  - a termination date (when the single period ends)
  - a single payment date (when the net amount settles)

FIELD MAPPING

isda_taxonomy: ALWAYS "InterestRate_Fra" for any FRA. Not optional.

reset_date / termination_date: these are given in the record as already-
  adjusted, final dates for the single settlement period (the reset/
  effective date and the termination/maturity date). Store them directly
  as given (ISO format) — do not look for separate business-day-convention
  fields for these two; if the record gives just one date each, that IS
  the adjusted date to use.

payment_date / payment_date_bdc: the single net-settlement date, and its
  business day convention (default "FOLLOWING" if the record names an
  adjustment convention like "adjusted Following").

fixed_leg_payer / floating_leg_payer: which CDM role ("Party1" or "Party2")
  pays the fixed amount vs the floating amount. Read directly from which
  party is named as paying fixed vs floating.

fixing_offset_multiplier / fixing_offset_period / fixing_offset_day_type /
fixing_bdc: when the fixing happens relative to the reset date. "2
  Business Days prior to the Reset Date" -> fixing_offset_multiplier=-2,
  fixing_offset_period="D", fixing_offset_day_type="Business". Negative
  when BEFORE the reset date (the normal case for a FRA fixing).

fixed_leg_payment_freq_multiplier / fixed_leg_payment_freq_period:
  ONLY set these when the record explicitly states a distinct "interest
  period" or "contract period" specifically for the FIXED leg, separate
  from the trade's overall term (e.g. "Fixed Interest Period: 6 Months").
  Split into multiplier+period like any other frequency ("6 Months" ->
  multiplier=6, period="M"). This is a FIXED-leg-only concept — never set
  it based on the floating leg's index tenor, and never invent it if the
  record doesn't separately call it out.

index_tenor_multiplier / index_tenor_period: the floating index's
  designated maturity/tenor (e.g. "Designated Maturity: 6 Months" ->
  multiplier=6, period="M").

Day Count Fractions (DCF):
  A/360, Actual/360 -> ACT/360
  ACT/365F, Actual/365 Fixed -> ACT/365.FIXED
  30E/360 -> 30E/360

Rate quotes (emit as decimals, not percent):
  "4.00%", "4.00 per cent p.a." -> 0.04

Party identifiers:
  Any Legal Entity Identifier (LEI) -> lei_scheme =
    http://www.fpml.org/coding-scheme/external/iso17442, id_type="LEI"
  When a party has an LEI, do NOT also set PartyInput.name — even if the
  record gives a company name/label (e.g. "Party 1 (HSBC)"). FRA records
  in this format identify parties by LEI alone; the name is context for
  you, not a field to populate. Only set name if the record gives NO LEI
  for that party.

Trade identifier schemes: if the record states a scheme URL literally
  (e.g. "scheme www.hsbc.com/swaps/trade-id"), use it verbatim, adding
  "http://" if the record omits the protocol. issuer_key is the key of
  the party that assigned that particular identifier — each party often
  has its own trade reference under its own scheme.

Amounts: notional_amount as a plain number (no commas, no currency code
  inside the value); notional_currency as a 3-letter code.
"""


TOOL = {
    "name": "emit_fra_trade",
    "description": "Emit the extracted FRA trade as a single structured object matching FRAInput.",
    "input_schema": FRA_SCHEMA,
}


# ── build FRAInput from the tool call's JSON ──────────────────────────────────

def _from_dict(cls, data: dict):
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

def extract_fra_trade_with_model(raw_text: str, fmt_hint: str, model: str,
                                  *, verbose: bool = False) -> FRAInput:
    """Extract an FRA using the given model. Called by fra_extractor_sonnet.py / fra_extractor_opus.py."""
    client = anthropic.Anthropic()
    user_msg = (
        f"Format hint: {fmt_hint}\n\n"
        f"Raw record:\n----- BEGIN RECORD -----\n"
        f"{raw_text}\n"
        f"----- END RECORD -----\n\n"
        f"Extract the FRA and call `emit_fra_trade` exactly once."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "emit_fra_trade"},
        messages=[{"role": "user", "content": user_msg}],
    )

    tool_block = next((b for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None:
        text = "".join(getattr(b, "text", "") for b in resp.content)
        raise RuntimeError(f"model did not call emit_fra_trade. Response: {text[:500]}")

    if verbose:
        import json
        print(json.dumps(tool_block.input, indent=2))
        print(f"[usage] in={resp.usage.input_tokens} out={resp.usage.output_tokens}")

    return _from_dict(FRAInput, tool_block.input)
