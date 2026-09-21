# Ground Truth — Interest Rate Swap (single currency)

Ground-truth pairs for evaluating the CDM mapping agent on the 5 proven
single-currency IRS products.

## Layout

```
v2/data/ground_truth/interest_rate_swap/
  fixedfloat/   input.txt    expected_cdm.json
  ois/          input.json   expected_cdm.json
  zerocoupon/   input.txt    expected_cdm.json
  basis/        input.dat    expected_cdm.json
  basis-ois/    input.txt    expected_cdm.json
```

- `input.*` — authored raw legacy-format record (see formats below). Each
  contains exactly the economic and party information of the trade, in a
  format style banks actually produce. Formats deliberately vary per case
  to test format-robustness of extraction.
- `expected_cdm.json` — byte-identical copy of the FINXIS reference file.
  These are the eval answer keys.

| case | input format style | reference file |
|---|---|---|
| fixedfloat | pipe-delimited EOD blotter extract | swaps/irs-fixedfloat.json |
| ois | internal booking-system JSON dump | swaps/irs-fixedfloat-ois.json |
| zerocoupon | free-text trade confirmation letter | swaps/irs-fixedfloat-zerocoupon.json |
| basis | fixed-width mainframe extract | cross_currency/irs-basis.json |
| basis-ois | MQ-style key=value capture message | cross_currency/irs-basis-ois.json |

## Eval design

The agent's task is **extraction**: raw input → `IRSTradeInput`
(v2/src/schemas/interest_rate_swap.py). The build step
(`build_irs_trade_state`) is deterministic and separately proven against
the reference files (v2/tests/compare_reference.py, 5/5 exact match), so:

```
agent extraction        proven builder            normalized diff
raw input ─────────► IRSTradeInput ─────────► CDM dict ─────────► vs expected_cdm.json
```

Score = diff count after the same normalization compare_reference.py uses
(canonical key ids, unreferenced keys dropped). 0 diffs = pass.
The oracle `IRSTradeInput` for each case is the fixture in
compare_reference.py — usable directly for extraction-level scoring too.

## Mapping conventions (agent configuration, not in raw inputs)

Raw bank records don't carry CDM coding-scheme URIs or CDM enum spellings.
These constants/translations are part of the mapping configuration the
agent is given, NOT information it must find in the input:

| concept | raw vocabulary → CDM value |
|---|---|
| LEI scheme URI | any LEI → `http://www.fpml.org/coding-scheme/external/iso17442`, identifierType `LEI` |
| generic party scheme (no LEI) | → `http://www.fpml.org/coding-scheme/external` |
| dummy party scheme (test env) | → `http://www.fpml.org/coding-scheme/dummy-party-id` |
| UTI scheme | → `http://www.fpml.org/coding-scheme/external/uti` |
| SwapsWire trade id scheme | → `http://www.swapswire.com/spec/2001/trade-id-1-0` |
| SwapsWire master agr. scheme | → `http://www.swapswire.com/spec/2001/master-agreement-type-1-0` |
| partyA internal trade id scheme | → `http://www.partyA.com/swaps/trade-id` |
| BankA/BankB com trade id schemes | → `http://www.bankA.com/swaps/com-trade-id` / `http://www.bankB.com/swaps/com-trade-id` (note: each party's ref lives in the *other* bank's scheme) |
| GTR product id scheme | → `http://www.dtcc.com/coding-scheme/external/GTR-Product-Id`, source `Other` |
| BDC vocab | `MF` / `MOD FOLL` / `Modified Following` → `MODFOLLOWING`; `PRECEDING`→`PRECEDING`; `NONE`→`NONE` |
| DCF vocab | `A/360`,`Actual/360`→`ACT/360`; `ACT/365F`→`ACT/365.FIXED`; `ACT/ACT ISDA`→`ACT/ACT.ISDA`; `30E/360`→`30E/360` |
| pay/reset relative-to | `PERIOD_END`→`CalculationPeriodEndDate`; `PERIOD_START`→`CalculationPeriodStartDate` |
| "at maturity" / zero coupon | calc & payment frequency period `T` (Term), multiplier 1, roll `NONE` |
| rate quotes | `0.20 PCT`/`3.537 (pct)` → decimals 0.002 / 0.03537; `-1BP` → -0.0001 |
| Party1/Party2 | counterparty enum values `Party1`/`Party2`; payer/receiver on legs use these role names |
| calc agent "INDEPENDENT" | ancillary role + calculationAgentParty `CalculationAgentIndependent` |
| business centers `PRIMARY` | external reference `primaryBusinessCenters` (schedule itself not in file — dangling by design, as in the venue record) |
| unnamed index (e.g. GOFO) | identifier only; omit `floatingRateIndex` value |
| CDM envelope | `@model` `cdm`, `@type` `cdm.event.common.TradeState`, `@version` `0.0.0.master-SNAPSHOT` |

## Provenance / caveat for finance review

Raw inputs are **authored** (banks' real legacy formats are proprietary);
they were derived from the reference files' content, not from production
systems. Realism of field vocabulary and layout is open for critique —
corrections to the raw formats are welcome and cheap; the expected outputs
are untouched FINXIS reference files and are not ours to edit.
