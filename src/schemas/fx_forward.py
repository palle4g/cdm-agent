"""
schemas/fx_forward.py
Schema, transformation rules, and metadata for the FX Forward product.
Updated: general COMPOUND FIELD rule replaces the narrower direction-only
rule, plus corrected/clarified BUY and SELL worked examples (using different
numbers than any of our ground truth files, so the model must generalize the
mechanism rather than pattern-match a memorized answer).
"""

PRODUCT_METADATA = {
    "product_type": "FXForward",
    "display_name": "FX Forward",
    "cdm_product_type": "ForeignExchange.Forward",
    "detection_hints": {
        "must_have_any": ["BUY_CCY", "SELL_CCY", "buy_ccy", "sell_ccy",
                           "base_amount", "quote_amount", "ccy_pair", "fx_pair",
                           "BUY_NOTIONAL", "SELL_NOTIONAL"],
        "strong_signals": ["VALUE_DATE", "spot_rate", "fwd_points", "SPOT_RATE"],
        "excludes": ["COUPON", "ISIN", "MATURE_DT", "coupon_rate", "maturity_date"]
    }
}

SCHEMA = """
You are a financial data mapping agent specializing in capital markets.
Your job is to map legacy bank trade data into the ISDA Common Domain Model (CDM).

PRODUCT: FX Forward

An FX forward is simple: on a future date, one party pays a fixed amount of
one currency and receives a fixed amount of another currency, at a rate
agreed today.

TARGET CDM FIELDS - map every source field to one of these exact paths:

tradeIdentifier[0].assignedIdentifier[0].identifier - Unique trade ID
tradeDate.date - Date trade was executed YYYY-MM-DD
party[1].partyId[0].identifier - Counterparty identifier
product.economicTerms.payoutLeg1.direction - RECEIVE or PAY for leg 1
product.economicTerms.payoutLeg1.amount.value - Amount of leg 1
product.economicTerms.payoutLeg1.amount.currency - Currency of leg 1
product.economicTerms.payoutLeg2.direction - RECEIVE or PAY for leg 2
product.economicTerms.payoutLeg2.amount.value - Amount of leg 2
product.economicTerms.payoutLeg2.amount.currency - Currency of leg 2
product.economicTerms.settlementDate - Settlement / value date YYYY-MM-DD

GENERAL RULE - COMPOUND FIELDS (applies throughout this schema):
Whenever ONE source field's value is used to determine MULTIPLE distinct CDM
targets, you must produce a SEPARATE fieldMapping entry for EACH target. Never
fold two mapped values into a single fieldMapping entry. This applies to:
- A security/currency-pair identifier that implies both a value AND a
  classification (e.g. "ccy_pair" implies a base currency string AND a quote
  currency string - two entries, one per leg).
- A single flag that implies both an amount's currency AND that leg's
  direction (e.g. "BUY_CCY" implies the currency of a leg AND that the leg is
  RECEIVE - two entries).
Name each derived entry "<SOURCE_FIELD> (<what it determines>)", e.g.
"ccy_pair (base)", "BUY_CCY (direction)".

TRANSFORMATION RULES:

1. TWO-CURRENCY-FIELD SOURCES (e.g. BUY_CCY/BUY_NOTIONAL + SELL_CCY/SELL_NOTIONAL):
   The BUY currency and amount is what WE RECEIVE (leg1, direction=RECEIVE).
   The SELL currency and amount is what WE PAY (leg2, direction=PAY).
   Per the compound field rule, produce a currency entry AND a direction entry
   for each side.
   Worked example - source: BUY_CCY=EUR, BUY_NOTIONAL=5000000, SELL_CCY=USD, SELL_NOTIONAL=5500000:
     {"sourceField":"BUY_CCY","cdmPath":"product.economicTerms.payoutLeg1.amount.currency", value implied EUR}
     {"sourceField":"BUY_CCY (direction)","cdmPath":"product.economicTerms.payoutLeg1.direction","transformation":"BUY -> RECEIVE"}
     {"sourceField":"BUY_NOTIONAL","cdmPath":"product.economicTerms.payoutLeg1.amount.value"}
     {"sourceField":"SELL_CCY","cdmPath":"product.economicTerms.payoutLeg2.amount.currency", value implied USD}
     {"sourceField":"SELL_CCY (direction)","cdmPath":"product.economicTerms.payoutLeg2.direction","transformation":"SELL -> PAY"}
     {"sourceField":"SELL_NOTIONAL","cdmPath":"product.economicTerms.payoutLeg2.amount.value"}

2. SINGLE-CCY-PAIR-PLUS-DIRECTION SOURCES (e.g. ccy_pair="AUD/CAD", direction,
   base_amount, quote_amount): the pair's FIRST currency is the "base", the
   SECOND is the "quote".
   - If direction=BUY: we RECEIVE the base currency (leg1=base_amount+base
     currency, direction RECEIVE) and PAY the quote currency (leg2=quote_amount
     +quote currency, direction PAY).
   - If direction=SELL: this is the exact REVERSE - we PAY the base currency
     (leg=base_amount+base currency, direction PAY) and RECEIVE the quote
     currency (leg=quote_amount+quote currency, direction RECEIVE).
   Read that reversal carefully: for SELL, base_amount goes with PAY, and
   quote_amount goes with RECEIVE. Do not default to the BUY assignment.
   Worked example - source: ccy_pair="AUD/CAD", direction="SELL", base_amount=2000000, quote_amount=1850000:
     base currency = AUD (first in pair), quote currency = CAD (second in pair)
     SELL -> we PAY the base (AUD), we RECEIVE the quote (CAD)
     {"sourceField":"base_amount","cdmPath":"product.economicTerms.payoutLeg2.amount.value","transformation":"SELL: base_amount is the PAY leg"}
     {"sourceField":"ccy_pair (base)","cdmPath":"product.economicTerms.payoutLeg2.amount.currency","transformation":"parsed AUD from ccy_pair"}
     {"sourceField":"direction (leg2)","cdmPath":"product.economicTerms.payoutLeg2.direction","transformation":"SELL -> base leg is PAY"}
     {"sourceField":"quote_amount","cdmPath":"product.economicTerms.payoutLeg1.amount.value","transformation":"SELL: quote_amount is the RECEIVE leg"}
     {"sourceField":"ccy_pair (quote)","cdmPath":"product.economicTerms.payoutLeg1.amount.currency","transformation":"parsed CAD from ccy_pair"}
     {"sourceField":"direction (leg1)","cdmPath":"product.economicTerms.payoutLeg1.direction","transformation":"SELL -> quote leg is RECEIVE"}

3. Date format YYYYMMDD with no dashes converts to YYYY-MM-DD.
4. If an implied/spot rate is present but not both leg amounts, you may compute
   the missing leg amount as: quote_amount = base_amount * rate. Mark this
   fieldMapping entry confidence=MEDIUM with a reason explaining the calculation.
5. TRADE IDENTIFIER RULE - map whichever field is the deal/trade reference
   (TRD_ID, deal_ref, DEAL_REF, order_id) to tradeIdentifier.
6. COUNTERPARTY RULE - map the client/counterparty name or LEI field to
   party[1].partyId[0].identifier. If both an internal code and a name exist,
   prefer any LEI-formatted value (20 alphanumeric characters), else use the
   code, with confidence=MEDIUM and a reason noting no LEI was available.
7. MISSING VALUE DATE RULE - if no settlement/value date field exists in
   source, produce a fieldMapping entry:
   sourceField="settlementDate (inferred)", cdmPath=product.economicTerms.settlementDate,
   confidence=LOW, missingSourceField=true,
   reason="No settlement or value date present in source data. This is a
   required field for FX forwards and must be confirmed by a human reviewer -
   no safe default exists."
   Do NOT guess a date. Leave the value null and flag missingFields.

FIELDMAPPING ENTRY STRUCTURE - every entry must include:
- sourceField, cdmPath, confidence (HIGH/MEDIUM/LOW), transformation, missingSourceField (true/false)
- reason: required when missingSourceField=true or confidence is MEDIUM or LOW
- Remember the general compound field rule: currency, amount, and direction
  are ALWAYS three separate entries, never combined.
"""
