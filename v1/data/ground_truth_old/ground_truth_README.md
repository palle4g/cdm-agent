# Ground Truth Dataset — T-003
# Government Bond (Fixed Rate) — 3 Source Formats

This folder contains the hand-mapped ground truth CDM JSON files
for the government bond product type. These are the correct answers
the agent is graded against.

## Files

| File | Source Format | Trade ID | Face Value | Notes |
|---|---|---|---|---|
| ground_truth_A.json | Pipe-delimited | TB-20260914-001 | $10,000,000 | All fields present, HIGH confidence |
| ground_truth_B.json | JSON API export | BOND-2026-8821 | $5,000,000 | All fields present, LEI available for counterparty |
| ground_truth_C.json | Fixed-width mainframe | TB0091234 | $10,000,000 | Missing trade date, settlement date — most challenging |

## All three trades are the SAME bond

ISIN: US91282CJL54  
Bond: US Treasury 4.25% due August 15, 2034  
Coupon: 4.25% semi-annual, ACT/ACT ICMA  
This is intentional — same bond, different source systems,
different field names, different completeness. The agent must
produce structurally identical CDM output regardless of which
format it receives.

## Ground Truth JSON Structure

Each file contains four sections:

- `_metadata` — what this file is, notes on mapping decisions
- `_source` — the raw legacy input exactly as received
- `_field_mapping` — every field mapped with confidence and any transformations
- `cdmTrade` — the correct CDM output the agent should produce

## Key Transformations to Watch

The agent must handle these correctly to pass:

1. Coupon rate: 4.25 (percentage) -> 0.0425 (decimal)
2. SEMI / S / SEMI-ANNUAL -> period=M, periodMultiplier=6
3. ACT/ACT / ACT/ACT ICMA -> ACT_ACT_ICMA (enum)
4. B / BUY / PURCHASE -> receiver=Party1, payer=Party2
5. MAT_DATE 20340815 (YYYYMMDD) -> 2034-08-15 (ISO)
6. Currency inference from ISIN prefix (Sample C only)

## How to Use These for Grading

When the agent maps a new trade:
1. Run the agent on the raw source field
2. Compare its output to the `cdmTrade` section of the ground truth
3. Compare its `_field_mapping` to the ground truth `_field_mapping`
4. Score per field: correct path = 1, wrong path = 0, missing = 0
5. Overall accuracy = correct fields / total mappable fields

## Next Steps

- Add 5 more bond trades from different source systems (T-003 extended)
- Add ground truth for FX Forward product type
- Use these files as few-shot examples in the agent prompt (T-005)
