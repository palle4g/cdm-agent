# T-002: CDM Schema Reference — FX Forward

**Task:** T-002 — CDM Schema Exploration (Product #2)
**Product:** FX Forward
**CDM Version:** FINOS CDM 7.3.0
**Status:** Complete — 3/3 ground truth files at 100% accuracy

---

## 1. What Is an FX Forward?

A bilateral agreement to exchange two currencies at a future date, at a rate
agreed today. Simpler than a bond: no coupon, no maturity in the bond sense —
just two cashflows (legs) that happen once, on the settlement date.

---

## 2. CDM Object Structure

```
product.economicTerms
├── payoutLeg1
│   ├── direction        (RECEIVE or PAY)
│   └── amount
│       ├── value
│       └── currency
├── payoutLeg2
│   ├── direction        (opposite of leg1)
│   └── amount
│       ├── value
│       └── currency
└── settlementDate
```

Unlike the bond, there is no `productIdentifier` (no ISIN) and no
`interestRatePayout` wrapper — FX forwards use the simpler `payoutLeg1`/`payoutLeg2`
structure directly under `economicTerms`.

---

## 3. Source Patterns Seen (two distinct styles)

**Style A — two currency/notional pairs:**
`BUY_CCY`, `BUY_NOTIONAL`, `SELL_CCY`, `SELL_NOTIONAL`. The BUY side is what
we RECEIVE; the SELL side is what we PAY.

**Style B — currency pair + direction + base/quote amounts:**
`ccy_pair` (e.g. "GBP/JPY"), `direction` ("BUY" or "SELL"), `base_amount`,
`quote_amount`. The pair's first currency is the "base", second is "quote".
- BUY: receive base, pay quote.
- SELL: **reverse** — pay base, receive quote. (This reversal was a real bug
  source — see Section 5.)

---

## 4. Field Mapping Table

| CDM Path | Typical Source Names |
|---|---|
| `tradeIdentifier[0].assignedIdentifier[0].identifier` | TRD_ID, deal_ref, DEAL_REF |
| `tradeDate.date` | TRADE_DATE, booking_date |
| `party[1].partyId[0].identifier` | CPTY_LEI, client_lei, counterparty |
| `product.economicTerms.payoutLeg1.direction` | derived from BUY/SELL flag |
| `product.economicTerms.payoutLeg1.amount.value` | BUY_NOTIONAL, base_amount, quote_amount (depends on direction) |
| `product.economicTerms.payoutLeg1.amount.currency` | BUY_CCY, or parsed from ccy_pair |
| `product.economicTerms.payoutLeg2.direction` | derived from BUY/SELL flag |
| `product.economicTerms.payoutLeg2.amount.value` | SELL_NOTIONAL, base_amount, quote_amount |
| `product.economicTerms.payoutLeg2.amount.currency` | SELL_CCY, or parsed from ccy_pair |
| `product.economicTerms.settlementDate` | VALUE_DATE, settle, settlement_date |

---

## 5. Bugs Found and Fixed During Development

**Direction combined into currency entry.** The agent correctly computed
RECEIVE/PAY internally but didn't give it a separate `fieldMapping` entry —
it silently folded direction into the currency mapping. Fixed by adding an
explicit rule requiring direction as its own entry, named
`"<SOURCE_FIELD> (direction)"`, with a worked example in the schema prompt.

**SELL logic inverted for ccy_pair style.** When direction=SELL, the agent
initially assigned `base_amount` to the RECEIVE leg (correct only for BUY).
Fixed by adding an explicit worked SELL example with different numbers than
any ground truth file, forcing the model to generalize the mechanism rather
than memorize an answer.

**ccy_pair currency values missing separate entries entirely.** Same class
of bug as direction — the base/quote currency values were correct in
`cdmTrade` but had no standalone `fieldMapping` entry. Generalized into one
rule: "COMPOUND FIELD RULE — whenever one source field determines multiple
distinct CDM targets, produce a separate entry per target." This single rule
has since prevented the same bug from recurring on the third product.

**Naming mismatch between schema examples and ground truth.** The schema's
worked example used `"ccy_pair (base currency)"` while ground truth expected
`"ccy_pair (base)"` — functionally identical mapping, but the exact-string
scorer saw it as missing. Lesson: schema worked-example field names must
match ground truth naming exactly, character for character.

---

*See docs/CONFIGURATION_REFERENCE.md Section 7 for the general "Compound
Field Rule" this section's bugs led to.*
