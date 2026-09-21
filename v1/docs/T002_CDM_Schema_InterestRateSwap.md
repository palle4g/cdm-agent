# T-002: CDM Schema Reference — Interest Rate Swap

**Task:** T-002 — CDM Schema Exploration (Product #3)
**Product:** Interest Rate Swap (Fixed vs Floating)
**CDM Version:** FINOS CDM 7.3.0
**Status:** Complete — 3/3 ground truth files at 100% accuracy

---

## 1. What Is an Interest Rate Swap?

Two parties exchange interest payments on the same notional, for a set
period. One side pays a FIXED rate; the other pays a FLOATING rate (an
index like SOFR or EURIBOR, plus a spread), reset periodically. No
principal changes hands — only the interest difference.

---

## 2. CDM Object Structure

```
product.economicTerms
├── effectiveDate           (swap start)
├── terminationDate         (swap end)
└── payout[0]  <- FIXED leg
│   └── interestRatePayout
│       ├── payerReceiver
│       ├── rateSpecification.fixedRate.rateSchedule.initialValue
│       ├── dayCountFraction
│       ├── calculationPeriodDates.calculationPeriodFrequency
│       └── principalPayment.principalAmount  <- notional, SHARED by both legs
└── payout[1]  <- FLOATING leg
    └── interestRatePayout
        ├── rateSpecification.floatingRate.index   (e.g. SOFR)
        ├── rateSpecification.floatingRate.spread
        ├── dayCountFraction
        └── calculationPeriodDates.calculationPeriodFrequency
```

**Critical structural point:** the notional and currency are mapped ONCE, on
payout[0] (the fixed leg) only. Do not duplicate them on payout[1] — CDM
understands both legs share the same principal by the swap's structure.

---

## 3. Field Mapping Table

| CDM Path | Typical Source Names |
|---|---|
| `tradeIdentifier[...]` | tradeId, deal_id, TRD_ID |
| `party[1].partyId[0].identifier` | counterparty LEI (preferred) or short code |
| `economicTerms.effectiveDate` | effectiveDate, EFF_DT |
| `economicTerms.terminationDate` | terminationDate, TERM_DT |
| `payout[0]...principalAmount.amount` | notional, NOTIONAL |
| `payout[0]...principalAmount.unit.currency` | currency, CCY, or `<tag>_currency` if it was an XML attribute |
| `payout[0]...fixedRate.rateSchedule.initialValue` | fixedRate, FIX_RATE, fixed_rate |
| `payout[0]...calculationPeriodFrequency` | fixedFreq, FIX_FREQ |
| `payout[0]...dayCountFraction` | fixedDayCount, FIX_DCF |
| `payout[0]...payerReceiver` | derived — see Section 4 |
| `payout[1]...floatingRate.index` | floatIndex, FLT_INDEX (SOFR, EURIBOR, SONIA) |
| `payout[1]...floatingRate.spread` | spread, float_spread (defaulted to 0.0 if absent) |
| `payout[1]...calculationPeriodFrequency` | floatFreq, FLT_FREQ |
| `payout[1]...dayCountFraction` | floatDayCount, FLT_DCF |

---

## 4. Payer/Receiver Logic

- If source explicitly says we pay fixed (`PAY_FIXED`, `pay_receive="PAY_FIXED"`):
  `payer=Party1, receiver=Party2`.
- If source says we receive fixed / pay floating (`pay_receive="RECEIVE_FIXED"`):
  `payer=Party2, receiver=Party1`.
- If no explicit flag exists: **default to us paying fixed** (standard bank
  hedging convention), confidence=MEDIUM, with a reason explaining the
  assumption.

**Naming rule (mandatory):** the fieldMapping entry for this decision must be
named `"<SOURCE_FIELD> (payer/receiver)"` — e.g. `"pay_receive (payer/receiver)"`
or, when defaulted from the counterparty field, `"CPTY (payer/receiver)"`.
This is a separate entry from the counterparty identifier mapping itself.

---

## 5. Bugs Found and Fixed During Development

**XML attributes silently dropped (T-004 bug, not a schema bug).** The
original `format_detector.py` XML parser only read element text content, not
attributes. A source like `<notional currency="USD">25000000</notional>`
produced only `"notional": "25000000"` — the currency was lost before the
agent ever saw it. Fixed in `format_detector.py`: attributes now surface as
`"<tag>_<attribute>"` fields (e.g. `"notional_currency": "USD"`).

**Ground truth predated the parser fix.** Two ground truth entries described
field names (`"notional (currency)"`, `"counterparty"` as an identifier) that
were artifacts of the broken parser, not real field names. Once the parser
was fixed, `"notional_currency"` and `"counterparty_lei"` became the real,
correct field names, and the ground truth was corrected to match — this was
fixing an outdated answer key, not "cheating" the eval (see the
CONFIGURATION_REFERENCE.md note on this distinction).

**Payer/receiver naming (4th occurrence of the Compound Field pattern).**
Same root cause as the FX Forward direction bug — the schema described the
payer/receiver *logic* without specifying what to *name* that fieldMapping
entry. Fixed with an explicit, mandatory naming convention plus a worked
example, matching the pattern established for the other three products.

**One observed run flapped between MEDIUM confidence and MISSING** on the
payer/receiver entry across two consecutive identical calls — this was
confirmed to be LLM non-determinism (temperature-driven variance in exact
label phrasing), not a reproducible bug. A third run passed cleanly. Worth
remembering: if a field fails once, rerun before concluding there's a real
gap — see `python src/agent/eval.py <Product> <file>` for fast single-file
retries.
