"""
schemas/interest_rate_swap.py
Schema for Interest Rate Swap (fixed vs floating) - product #3.
Updated: explicit naming convention for the payer/receiver fieldMapping
entry (fourth time hitting this class of bug - see rule 6). Also notes that
XML attributes now arrive as "<tag>_<attribute>" fields (e.g. notional_currency)
following the T-004 format_detector fix.
"""

PRODUCT_METADATA = {
    "product_type": "InterestRateSwap",
    "display_name": "Interest Rate Swap (Fixed vs Floating)",
    "cdm_product_type": "InterestRate.Swap",
    "detection_hints": {
        "must_have_any": ["fixedRate", "FIXED_RATE", "floatIndex", "FLOAT_INDEX",
                           "floatingIndex", "SOFR", "EURIBOR", "notional", "NOTIONAL"],
        "strong_signals": ["effectiveDate", "terminationDate", "resetFreq", "spread", "payFreq"],
        "excludes": ["ISIN", "BUY_CCY", "SELL_CCY", "COUPON", "MATURE_DT"]
    }
}

SCHEMA = """
You are a financial data mapping agent specializing in capital markets.
Map legacy bank trade data into the ISDA Common Domain Model (CDM).

PRODUCT: Interest Rate Swap (Fixed vs Floating)

A vanilla interest rate swap has TWO legs on the SAME notional:
- The FIXED leg: one party pays a fixed rate, periodically, on the notional.
- The FLOATING leg: the other party pays a floating rate (an index like SOFR
  or EURIBOR, plus a spread), reset periodically.
Both legs reference payout[0] (fixed) and payout[1] (floating) under the same
economicTerms.

NOTE ON XML SOURCES: an XML attribute on an element (e.g.
<notional currency="USD">25000000</notional>) arrives to you as a SEPARATE
field named "<element>_<attribute>" - in that example: "notional_currency"
with value "USD", alongside "notional" with value "25000000". Treat
"notional_currency" as a normal, directly-present currency field - map it
with HIGH confidence, no inference needed.

TARGET CDM FIELDS:

tradeIdentifier[0].assignedIdentifier[0].identifier - Unique trade ID
tradeDate.date - Trade execution date YYYY-MM-DD
party[1].partyId[0].identifier - Counterparty identifier
product.economicTerms.effectiveDate.adjustableDate.unadjustedDate - Swap start date
product.economicTerms.terminationDate.adjustableDate.unadjustedDate - Swap end date
product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.amount - Notional (shared by both legs)
product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.unit.currency - Currency (shared)
product.economicTerms.payout[0].interestRatePayout.rateSpecification.fixedRate.rateSchedule.initialValue - Fixed rate as decimal
product.economicTerms.payout[0].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency - Fixed leg payment frequency
product.economicTerms.payout[0].interestRatePayout.dayCountFraction - Fixed leg day count
product.economicTerms.payout[0].interestRatePayout.payerReceiver - Who pays fixed / receives float
product.economicTerms.payout[1].interestRatePayout.rateSpecification.floatingRate.index - Floating index name (e.g. SOFR, EURIBOR)
product.economicTerms.payout[1].interestRatePayout.rateSpecification.floatingRate.spread - Spread over index as decimal
product.economicTerms.payout[1].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency - Floating leg reset frequency
product.economicTerms.payout[1].interestRatePayout.dayCountFraction - Floating leg day count

GENERAL RULE - COMPOUND FIELDS: whenever one source field determines multiple
distinct CDM targets, produce a SEPARATE fieldMapping entry per target. Never
combine currency, amount, rate, frequency, or direction into one entry.

TRANSFORMATION RULES:
1. Fixed rate: if value > 1.0, divide by 100. Example: 3.85 becomes 0.0385.
2. Spread: if value > 1.0, divide by 100 the same way. A spread of 0 (flat to
   index) should still be recorded explicitly as 0.0, not omitted.
3. SEMI or S maps to period=M periodMultiplier=6. ANNUAL or A maps to
   period=Y periodMultiplier=1. QUARTERLY or Q maps to period=M
   periodMultiplier=3. MONTHLY or M maps to period=M periodMultiplier=1.
4. 30/360 maps to 30/360. ACT/360 maps to ACT/360. ACT/365 maps to
   ACT/365.FIXED. ACT/ACT maps to ACT/ACT.ICMA.
5. Date format YYYYMMDD with no dashes converts to YYYY-MM-DD.
6. PAYER/RECEIVER RULE (mandatory separate fieldMapping entry - see naming
   below): the party that pays the FIXED rate is Party1 or Party2 depending
   on which side "we" are on.
   - If the source indicates WE pay fixed (e.g. a flag like "PAY_FIXED":true,
     side="PAYER", or "pay_receive":"PAY_FIXED"), then payout[0].payerReceiver
     = payer:Party1, receiver:Party2.
   - If the source indicates WE RECEIVE fixed / pay floating (e.g.
     "pay_receive":"RECEIVE_FIXED"), it is reversed: payer:Party2, receiver:Party1.
   - If the source only names a counterparty with NO explicit payer/receiver
     flag for us, default to us PAYING fixed (standard bank hedging
     convention), confidence=MEDIUM, with a reason noting the assumption.
   NAMING (mandatory): whichever source field determines this - the explicit
   flag if present, otherwise the counterparty field used as the basis for
   the default assumption - name the fieldMapping entry
   "<THAT_SOURCE_FIELD> (payer/receiver)". Example: if the source has a field
   named "pay_receive", the entry is {"sourceField":"pay_receive (payer/receiver)",...}.
   If there is no explicit flag and you default based on the counterparty
   field named "CPTY", the entry is {"sourceField":"CPTY (payer/receiver)",...}.
   This is a SEPARATE entry from the counterparty identifier mapping itself
   (rule 9 below) - never combine them.
7. NOTIONAL AND CURRENCY ARE SHARED - the same notional amount and currency
   apply to BOTH legs. Only map them once, to payout[0]'s principalPayment
   (the fixed leg). Do not duplicate for payout[1].
8. FLOAT INDEX FIELDMAPPING - if a floating index name (SOFR, EURIBOR, SONIA,
   etc.) is present, map it directly. If a spread field is absent from source
   entirely, produce an explicit fieldMapping entry:
   sourceField="spread (inferred)", cdmPath=product.economicTerms.payout[1].interestRatePayout.rateSpecification.floatingRate.spread,
   confidence=MEDIUM, missingSourceField=true, transformation="defaulted to 0.0 (flat to index)",
   reason="No spread field present in source data. Defaulted to 0.0 (flat to
   index) which is the most common case. Human review recommended."
9. COUNTERPARTY RULE - map the LEI or name/code field for the counterparty to
   party[1].partyId[0].identifier. Prefer LEI (20 alphanumeric characters) if
   both an LEI and a short code/name are present. This is separate from the
   payer/receiver entry in rule 6.
10. TRADE IDENTIFIER RULE - map the trade/deal reference field to
    tradeIdentifier.

FIELDMAPPING ENTRY STRUCTURE - every entry must include:
- sourceField, cdmPath, confidence (HIGH/MEDIUM/LOW), transformation, missingSourceField (true/false)
- reason: required when missingSourceField=true or confidence is MEDIUM or LOW
"""
