# T-002: CDM Schema Reference — Government Bond (Fixed Rate)

**Task:** T-002 — CDM Schema Exploration  
**Product:** Government Bond (Fixed Rate Coupon)  
**CDM Version:** FINOS CDM 7.3.0  
**Date:** September 14, 2026  
**Status:** Complete — use this as the agent's reference for mapping any legacy bond trade

---

## 1. What Is a Government Bond (in plain English)?

A government bond is a loan from an investor to a government. The government:
- Borrows a fixed amount of money (the **notional** or **face value**)
- Pays regular interest (the **coupon**) at a fixed rate, on a schedule
- Returns the full amount borrowed at the end (the **maturity date**)

Example: "US Treasury 4.25% due 2034" means:
- Face value: $10,000,000
- The government pays 4.25% of that per year (split into semi-annual payments)
- On August 15, 2034 it repays the full $10,000,000

The CDM represents this as: two parties + one interest rate payout leg (fixed rate)
+ principal repayment + product identifier (ISIN).

---

## 2. CDM Object Structure for a Government Bond

```
TradeState
└── Trade
    ├── tradeIdentifier[]          ← trade ID (e.g. "TB-20260914-001")
    ├── tradeDate                  ← when the trade was agreed
    ├── party[]                    ← buyer and seller
    ├── counterparty[]             ← roles (buyer/seller)
    └── tradableProduct
        └── product
            └── NonTransferableProduct
                ├── productIdentifier[]    ← ISIN, CUSIP, SEDOL
                └── economicTerms
                    └── EconomicTerms
                        ├── effectiveDate      ← settlement / issue date
                        ├── terminationDate    ← maturity date
                        └── payout[]
                            └── InterestRatePayout
                                ├── payerReceiver      ← who pays, who receives
                                ├── rateSpecification  ← fixed rate details
                                │   └── FixedRateSpecification
                                │       └── rateSchedule
                                │           └── initialValue  ← e.g. 0.0425
                                ├── dayCountFraction   ← e.g. ACT/ACT.ICMA
                                ├── calculationPeriodDates
                                │   ├── effectiveDate      ← coupon start date
                                │   ├── terminationDate    ← maturity date
                                │   └── calculationPeriodFrequency
                                │       ├── period         ← M, Y, etc.
                                │       └── periodMultiplier ← e.g. 6 (for 6M)
                                ├── paymentDates       ← coupon payment schedule
                                └── principalPayment   ← face value repayment
                                    └── principalAmount
                                        ├── amount     ← e.g. 10000000
                                        └── currency   ← e.g. USD
```

---

## 3. Field-by-Field Reference

### 3.1 Trade Identifier

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `tradeIdentifier[0].assignedIdentifier[0].identifier` | StrWithMeta | YES | The trade's unique ID in the booking system |

**Common legacy field names:**
`TRADE_NUM`, `TRD_ID`, `DEAL_REF`, `TRADE_REF`, `ORDER_ID`, `BOOKING_ID`

---

### 3.2 Trade Date

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `tradeDate.date` | date (YYYY-MM-DD) | YES | The date the trade was agreed/executed |

**Common legacy field names:**
`TRADE_DT`, `TRADE_DATE`, `BOOKING_DATE`, `EXEC_DATE`, `TRD_DT`

---

### 3.3 Parties

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `party[0].partyId[0].identifier` | StrWithMeta | YES | Our bank's identifier (LEI, BIC, or internal code) |
| `party[0].name` | StrWithMeta | NO | Our bank's name |
| `party[1].partyId[0].identifier` | StrWithMeta | YES | Counterparty identifier |
| `party[1].name` | StrWithMeta | NO | Counterparty name |

**Common legacy field names for counterparty:**
`CPTY_CODE`, `CPTY_LEI`, `COUNTERPARTY`, `CPTY_ID`, `CLIENT_ID`, `BROKER_CODE`

**Common legacy field names for own bank:**
`OWN_LEI`, `BOOK_ENTITY`, `TRADING_ENTITY`, `DESK_CODE`

---

### 3.4 Product Identifier (ISIN / CUSIP)

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `product.NonTransferableProduct.productIdentifier[0].identifier` | StrWithMeta | YES | ISIN, CUSIP, or SEDOL of the bond |
| `product.NonTransferableProduct.productIdentifier[0].source` | ProductIdTypeEnum | YES | ID scheme: `ISIN`, `CUSIP`, `SEDOL`, `RIC` |

**Common legacy field names:**
`ISIN`, `SEC_ID`, `CUSIP`, `SEDOL`, `SECURITY_ID`, `BOND_ID`, `INSTRUMENT_ID`

**ProductIdTypeEnum valid values:**
`ISIN`, `CUSIP`, `SEDOL`, `RIC`, `FIGI`, `Bloomberg`, `INTERNAL`

---

### 3.5 Effective Date (Settlement / Issue Date)

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `economicTerms.effectiveDate.adjustableDate.unadjustedDate` | date | YES | When the bond was issued / when settlement occurs |

**Common legacy field names:**
`SETTLE_DT`, `SETTLEMENT_DATE`, `SETTLE_DATE`, `VALUE_DATE`,
`ISSUE_DATE`, `START_DATE`, `EFFECTIVE_DATE`

---

### 3.6 Maturity Date (Termination Date)

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `economicTerms.terminationDate.adjustableDate.unadjustedDate` | date | YES | When the bond matures and principal is repaid |

**Common legacy field names:**
`MATURE_DT`, `MATURITY_DATE`, `EXPIRY_DATE`, `TERMINATION_DATE`,
`MAT_DATE`, `END_DATE`, `MATURE_DATE`

---

### 3.7 Face Value / Notional (Principal)

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `InterestRatePayout.principalPayment.principalAmount.amount` | Decimal | YES | The face value of the bond (what gets repaid at maturity) |
| `InterestRatePayout.principalPayment.principalAmount.unit.currency` | StrWithMeta | YES | ISO currency code (e.g. USD, EUR, GBP, JPY) |

**Common legacy field names for amount:**
`QTY`, `QUANTITY`, `FACE_VALUE`, `NOTIONAL`, `NOMINAL`, `PAR_VALUE`,
`PRINCIPAL`, `SETTLE_AMT` (note: settle_amt may include accrued interest — check)

**Common legacy field names for currency:**
`CCY`, `CURRENCY`, `SETTLE_CCY`, `BOND_CCY`, `DENOM_CCY`

---

### 3.8 Coupon Rate (Fixed Rate)

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `InterestRatePayout.rateSpecification.FixedRateSpecification.rateSchedule.initialValue` | Decimal | YES | The annual coupon rate as a decimal (e.g. 4.25% = 0.0425) |

**CRITICAL:** Legacy systems store rates in different formats:
- As a percentage: `4.25` → must convert to `0.0425` for CDM
- As a decimal: `0.0425` → use as-is
- As basis points: `425` → must convert to `0.0425`

**Common legacy field names:**
`COUPON`, `COUPON_RATE`, `INTEREST_RATE`, `CPN_RATE`, `RATE`,
`FIXED_RATE`, `BOND_RATE`, `CPN`

---

### 3.9 Coupon Frequency

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `calculationPeriodDates.calculationPeriodFrequency.period` | PeriodEnum | YES | Time unit: `M` (month), `Y` (year) |
| `calculationPeriodDates.calculationPeriodFrequency.periodMultiplier` | int | YES | Number of periods (e.g. 6 for semi-annual = every 6 months) |

**Frequency mapping from legacy values:**

| Legacy Value | period | periodMultiplier | Meaning |
|---|---|---|---|
| `ANNUAL`, `A`, `1` | `Y` | `1` | Once per year |
| `SEMI`, `SEMI-ANNUAL`, `S`, `2` | `M` | `6` | Every 6 months |
| `QUARTERLY`, `Q`, `4` | `M` | `3` | Every 3 months |
| `MONTHLY`, `M`, `12` | `M` | `1` | Every month |

**Common legacy field names:**
`FREQ`, `COUPON_FREQ`, `PAY_FREQ`, `COUPON_FREQUENCY`,
`PAYMENT_FREQUENCY`, `PERIOD`

---

### 3.10 Day Count Convention

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `InterestRatePayout.dayCountFraction` | DayCountFractionEnum | YES | How interest days are counted between coupon periods |

**Day count mapping from legacy values:**

| Legacy Value | CDM Enum Value | Common For |
|---|---|---|
| `ACT/ACT`, `ACT/ACT ICMA`, `ICMA` | `ACT_ACT_ICMA` | Government bonds (most common) |
| `ACT/ACT ISDA`, `ISDA` | `ACT_ACT_ISDA` | US Treasuries |
| `30/360`, `30360` | `_30_360` | US corporate bonds |
| `ACT/360` | `ACT_360` | Money market instruments |
| `ACT/365`, `ACT/365F` | `ACT_365_FIXED` | UK gilts, some Asian bonds |

**Common legacy field names:**
`DAY_COUNT`, `DAY_CNT`, `DCF`, `DAY_COUNT_FRACTION`,
`ACCRUAL_BASIS`, `BASIS`

---

### 3.11 Buy/Sell Direction

| CDM Path | CDM Type | Required | Description |
|---|---|---|---|
| `InterestRatePayout.payerReceiver.payer` | CounterpartyRoleEnum | YES | Who pays the coupon: `Party1` or `Party2` |
| `InterestRatePayout.payerReceiver.receiver` | CounterpartyRoleEnum | YES | Who receives the coupon |

**Direction mapping:**
- If `SIDE = BUY`: we are the receiver (we bought the bond, issuer pays us)
- If `SIDE = SELL`: we are the payer (we sold the bond, we pay the buyer)

**Common legacy field names:**
`SIDE`, `BUY_SELL`, `DIRECTION`, `TRANS_TYPE`, `ACTION`,
`POSITION_TYPE`, `TRD_SIDE`

---

### 3.12 Accrued Interest (supplementary — not always mapped to CDM directly)

**Common legacy field names:**
`ACCRUED_INT`, `ACCRUED_INTEREST`, `AI`, `ACCRUED`

**Note:** Accrued interest is a calculated value (not a CDM structural field).
It is derived from: face value × coupon rate × days since last coupon / day count basis.
If present in the source data, flag it as a cross-check value rather than mapping it directly.

---

### 3.13 Price / Yield (supplementary)

**Common legacy field names for price:**
`PRICE`, `CLEAN_PRICE`, `DIRTY_PRICE`, `MKT_PRICE`

**Common legacy field names for yield:**
`YIELD`, `YTM`, `YIELD_TO_MATURITY`

**Note:** In CDM, price/yield are represented in the TradableProduct's
`priceQuantity` structure. For Phase 1 mapping, capture these values
but mark as P1 (nice to have) — focus on structural fields first.

---

## 4. Complete Legacy-to-CDM Mapping Table

This is the master reference the agent uses. For any government bond trade,
every source field should map to one of these CDM paths.

| CDM Path | Required | Typical Legacy Names | Notes |
|---|---|---|---|
| `tradeIdentifier[0].assignedIdentifier[0].identifier` | YES | TRADE_NUM, TRD_ID, DEAL_REF | |
| `tradeDate.date` | YES | TRADE_DT, TRADE_DATE, EXEC_DATE | |
| `party[0].partyId[0].identifier` | YES | OWN_LEI, BOOK_ENTITY | Our bank |
| `party[1].partyId[0].identifier` | YES | CPTY_CODE, CPTY_LEI, CLIENT_ID | Counterparty |
| `productIdentifier[0].identifier` | YES | ISIN, CUSIP, SEC_ID | Bond ID |
| `productIdentifier[0].source` | YES | — | Infer from format of ID |
| `economicTerms.effectiveDate` | YES | SETTLE_DT, ISSUE_DATE, VALUE_DATE | |
| `economicTerms.terminationDate` | YES | MATURE_DT, MATURITY_DATE, MAT_DATE | |
| `principalPayment.principalAmount.amount` | YES | QTY, FACE_VALUE, NOTIONAL, PRINCIPAL | |
| `principalPayment.principalAmount.unit.currency` | YES | CCY, CURRENCY, BOND_CCY | |
| `rateSchedule.initialValue` | YES | COUPON, COUPON_RATE, RATE | Watch for % vs decimal |
| `calculationPeriodFrequency.period` | YES | FREQ, COUPON_FREQ | Infer from frequency string |
| `calculationPeriodFrequency.periodMultiplier` | YES | FREQ, COUPON_FREQ | Infer from frequency string |
| `dayCountFraction` | YES | DAY_COUNT, DCF, BASIS | Map to DayCountFractionEnum |
| `payerReceiver.payer` | YES | SIDE, BUY_SELL, DIRECTION | Infer from BUY/SELL flag |
| `payerReceiver.receiver` | YES | SIDE, BUY_SELL, DIRECTION | Opposite of payer |

---

## 5. Sample Trades — Ground Truth Inputs for T-003

These are the sample legacy formats that will be used to build the
ground truth dataset in T-003. The agent must map each of these
correctly to the CDM structure above.

### Sample A — Pipe-delimited (typical back-office export)
```
TRADE_NUM|SEC_ID|ISIN|SEC_DESC|SIDE|QTY|PRICE|YIELD|ACCRUED_INT|SETTLE_AMT|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT
TB-20260914-001|UST-10Y|US91282CJL54|US TREASURY 4.25% 08/2034|BUY|10000000|98.750|4.42|21250.00|9896250.00|JPMORGAN|2026-09-14|2026-09-16|2034-08-15|4.25|SEMI|ACT/ACT
```

### Sample B — JSON (modern API export)
```json
{
  "deal_id": "BOND-2026-8821",
  "security": "US91282CJL54",
  "description": "US TREASURY NOTE 4.25 08/15/2034",
  "transaction_type": "PURCHASE",
  "face_value": 5000000,
  "currency": "USD",
  "clean_price": 98.75,
  "accrued_interest": 10625.00,
  "settlement_amount": 4948125.00,
  "coupon_rate": 4.25,
  "payment_frequency": "SEMI-ANNUAL",
  "day_count_basis": "ACT/ACT ICMA",
  "trade_date": "2026-09-14",
  "settlement_date": "2026-09-16",
  "maturity_date": "2034-08-15",
  "counterparty": "GOLDMAN SACHS",
  "counterparty_lei": "784F5XWPLTWKTBV3E584"
}
```

### Sample C — Fixed-width mainframe format
```
TRADE_ID  ISIN          SIDE QTY        PRICE    COUPON FREQ MAT_DATE   CPTY
TB0091234 US91282CJL54  B    10000000   98.7500  4.2500 S    20340815   BARC
```

---

## 6. Key Validation Rules

When the agent produces a CDM mapping for a government bond, validate:

1. **ISIN format**: must be 2 letters + 9 alphanumeric + 1 check digit (12 chars total)
2. **Coupon rate**: must be between 0.0 and 1.0 (decimal). If > 1.0, it's a percentage — divide by 100
3. **Maturity date > settlement date**: always. If not, flag as data error
4. **Day count enum**: must match exactly one of the valid DayCountFractionEnum values
5. **Currency**: must be a valid ISO 4217 3-letter code (USD, EUR, GBP, JPY, etc.)
6. **Face value**: must be a positive number. Government bonds are typically multiples of 1,000

---

## 7. What Goes in the docs Folder

Save this file as:
```
D:\projects\cdm-agent\docs\T002_CDM_Schema_GovernmentBond.md
```

The next product type (Interest Rate Swap) will be saved as:
```
D:\projects\cdm-agent\docs\T002_CDM_Schema_InterestRateSwap.md
```

And so on for each product type. These documents collectively become
the agent's knowledge base — injected into the prompt at runtime.

---

*End of T-002 document. Next task: T-003 — Hand-map ground truth dataset.*
*Take the three sample trades above and manually produce the correct CDM*
*JSON for each one. That becomes your eval set for grading the agent.*
