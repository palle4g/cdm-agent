# Configuration Reference & Project Glossary
# CDM Mapping Agent

This document is the single source of truth for what every setting, term, and
value in this project means. When you (or anyone) returns to this project,
start here. Keep this file updated as the project grows.

Last updated: 2026-09-17

---

## 1. What This Project Does

The CDM Mapping Agent takes financial trade data stored in any legacy bank
format (CSV, JSON, XML, fixed-width mainframe, etc.) and converts it into the
ISDA Common Domain Model (CDM) - the open-source industry standard maintained
by FINOS. It is the Phase 0 data-normalization foundation for the larger
TP-GPT (Trade & Position GPT) vision.

The pipeline: raw legacy trade -> format detection -> AI mapping agent ->
CDM validation -> retry if needed -> validated CDM output.

---

## 2. Confidence Levels (HIGH / MEDIUM / LOW)

Every field the agent maps carries a confidence level. This tells a human
reviewer how much to trust that particular mapping.

| Level | Meaning | What triggers it | Human action |
|---|---|---|---|
| HIGH | The field name clearly and unambiguously matches a CDM field. No guessing involved. | Direct field-name match (e.g. TRADE_DT -> tradeDate). Value used as-is or with a deterministic transform. | Usually auto-accepted. No review needed. |
| MEDIUM | The value was inferred, derived, or the field name was ambiguous. | Currency inferred from ISIN prefix; day count defaulted; short counterparty code with no LEI. | Flagged for human review. |
| LOW | The field is missing, highly ambiguous, or the agent is unsure. | Required field absent from source; conflicting values; unknown field. | Always requires human review. |

The REVIEW_THRESHOLD setting (below) decides which levels get auto-accepted
versus flagged for the Critique UI.

---

## 3. Inferred Fields

When a required CDM field is NOT present in the source data, the agent must
still produce it - but it marks the mapping with:
- missingSourceField = true
- confidence = MEDIUM (usually)
- a reason explaining (a) why it was missing, (b) how the value was derived,
  (c) what a human should check.

Example: a fixed-width mainframe file has no currency field. The agent infers
USD from the ISIN prefix "US" and records:
  reason = "No explicit currency field present in source data. Currency
  derived from ISIN country prefix US=USD. Human review recommended if ISIN
  country does not match settlement currency."

Never accept an "inferred" field without a reason. That is a bug.

---

## 4. Environment Variables (.env file)

The .env file holds settings that change per environment or per run. It lives
in the project root and is NEVER committed to git (it is in .gitignore because
it contains the API key). Edit .env, save, and the next script run picks up
the change automatically - no code edits, no restart.

| Variable | Valid values | Default | What it does |
|---|---|---|---|
| ANTHROPIC_API_KEY | your sk-ant-... key | (none) | Credential for calling Claude. Only needed in agent mode. |
| CDM_RUN_MODE | agent, human, hybrid | agent | Who does the mapping. See section 5. |
| CDM_AGENT_MODEL | any Claude model id | claude-sonnet-4-6 | Model for standard mappings. |
| CDM_AGENT_MODEL_COMPLEX | any Claude model id | (same as AGENT_MODEL) | Model used on retry / for hard cases. |
| CDM_AGENT_MAX_TOKENS | integer | 4000 | Max tokens the agent may return. |
| CDM_MAX_RETRIES | integer | 3 | How many times to retry a failed mapping before flagging for review. |
| CDM_DEFAULT_PRODUCT_TYPE | GovernmentBond, UNKNOWN, etc. | UNKNOWN | Fallback when product type cannot be detected. UNKNOWN forces human review rather than a wrong guess. |
| CDM_REVIEW_THRESHOLD | HIGH, MEDIUM, LOW | MEDIUM | Which confidence levels get auto-accepted. See section 6. |
| CDM_VERSION | version string | 7.3.0 | Which finos-cdm version this project targets. |
| CDM_DEFAULT_DAY_COUNT | a CDM day count enum | ACT/ACT.ICMA | Default day count for government bonds when not in source. |

You can change any of these at any time. The change takes effect the next time
you run any script. You do NOT edit .env before every run - only when you want
something different.

---

## 5. Run Modes (CDM_RUN_MODE)

| Mode | What happens | When to use |
|---|---|---|
| agent | Claude maps the trade automatically. API key required. | Normal operation, development, high-volume processing. |
| human | No API call. A human supplies the mapping manually; the system only validates it. API key NOT required. | Sensitive data that cannot leave the bank; creating ground truth; when no API access. |
| hybrid | Claude maps first, then a human always reviews before the result is saved. | Production with oversight; regulated environments. |

---

## 6. Review Threshold (CDM_REVIEW_THRESHOLD)

Decides which mappings are auto-accepted and which go to the human review queue.

| Setting | Auto-accepted | Flagged for review |
|---|---|---|
| HIGH | HIGH only | MEDIUM and LOW |
| MEDIUM | HIGH and MEDIUM | LOW only |
| LOW | everything | nothing (not recommended for production) |

---

## 7. Transformation Rules (plain English)

These are the deterministic rules the agent applies. They live in the product
schema file (src/schemas/government_bond.py) and are enforced in the prompt.

1. Coupon rate given as a percentage (value > 1.0) is divided by 100.
   Example: 4.25 becomes 0.0425.
2. Coupon frequency SEMI / S / SEMI-ANNUAL becomes period=M, periodMultiplier=6.
3. ANNUAL / A becomes period=Y, periodMultiplier=1.
4. QUARTERLY / Q becomes period=M, periodMultiplier=3.
5. Day count ACT/ACT or ACT/ACT ICMA becomes ACT/ACT.ICMA.
6. Side BUY / B / PURCHASE becomes payer=Party2, receiver=Party1.
7. Side SELL / SALE becomes payer=Party1, receiver=Party2.
8. Date in YYYYMMDD (no dashes) becomes YYYY-MM-DD.
9. Currency, if absent, is inferred from the ISIN country prefix
   (US=USD, GB=GBP, DE=EUR, FR=EUR, JP=JPY, AU=AUD, CA=CAD, CH=CHF).
10. Any security identifier (ISIN/CUSIP/SEDOL) produces TWO mapping entries -
    one for the value, one for the scheme.
11. If currency is missing, an explicit "currency (inferred)" entry is created
    with a reason.
12. If day count is missing, an explicit "day_count (inferred)" entry is
    created with a reason.

---

## 8. Product Types

Currently supported: GovernmentBond (fixed rate).

Planned (per spec): FX Forward, Interest Rate Swap, Corporate Bond,
Cross-Currency Swap, then credit derivatives and options.

Each product type has its own schema file in src/schemas/. Adding a product
means adding a schema file and ground truth files - the agent code does not
change. Government bonds and corporate bonds are treated as SEPARATE products
because corporate bonds carry extra fields (credit rating, seniority,
issuer credit risk).

---

## 9. Ground Truth (the answer key)

Ground truth files are hand-verified correct CDM mappings. They are what the
agent is graded against. They live in:

    data/ground_truth/<product_type>/

Each file contains:
- _source.raw   : the raw legacy input string
- _field_mapping: the correct source-to-CDM field mappings (the answer key)
- cdmTrade      : the correct CDM output

Naming convention encodes what makes each trade different, so coverage gaps
are visible at a glance:

    gb_004_bund_eur_annual_30360_buy.json
    |   |    |    |    |      |    |
    |   |    |    |    |      |    side
    |   |    |    |    |      day count
    |   |    |    |    coupon frequency
    |   |    |    currency
    |   |    issuer / instrument
    |   sequence number
    product prefix (gb = government bond)

Two kinds of diversity are needed:
- Format diversity: the SAME trade in different file formats (tests the parser).
- Trade diversity: DIFFERENT trades (currencies, frequencies, day counts,
  buy/sell, edge cases) - tests the agent's actual understanding.

Target: 15-30 diverse ground truth files per product before trusting the agent
on that product in production.

---

## 10. Provenance / Audit Fields

Every mapping result records:
- _agentModel   : which model produced it (for audit - "Opus mapped this")
- _sourceFormat : the detected input format
- confidence + reason per field
- (later, in the Observation Store) timestamp, agent version, CDM version,
  and any human corrections.

This is required for regulatory traceability (EU AI Act, model risk
management). The model info is not needed to RUN - it is needed to TRACE what
happened afterward.

---

## 11. Project Structure

    src/
      config.py                 all settings (reads .env)
      ingestion/
        format_detector.py      detects and parses input format (product-agnostic)
      schemas/
        government_bond.py       bond schema + transformation rules + metadata
        registry.py              maps product type -> schema
      agent/
        mapping_agent.py         product-agnostic; loads schema from registry
        agent_loop.py            end-to-end pipeline with retry
        eval.py                  runs agent across all ground truth, scores it
      validation/
        validator.py             validates CDM output against finos-cdm
    data/
      ground_truth/
        government_bond/         diverse verified bond mappings
      sample_trades/             raw sample inputs
    docs/
      CONFIGURATION_REFERENCE.md  this file
      T002_CDM_Schema_GovernmentBond.md

Core principle: adding a new product adds files (a schema + ground truth).
It never requires editing the agent code.
