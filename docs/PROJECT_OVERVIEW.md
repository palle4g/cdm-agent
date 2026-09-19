# CDM Mapping Agent — Project Overview

**Last updated:** September 17, 2026
**Status:** 3 products live, Observation Store operational, Critique UI functional

This is the master reference for the whole project. Read this first, then
dive into the per-product docs (T002_CDM_Schema_*.md) or
CONFIGURATION_REFERENCE.md for settings detail.

---

## 1. What This Project Is

An AI agent that reads legacy bank trade data — in any format (CSV, JSON,
XML, fixed-width) — and maps it into the ISDA Common Domain Model (CDM), the
open-source industry standard maintained by FINOS. It is Phase 0 of the
larger TP-GPT (Trade & Position GPT) vision: the data-normalization
foundation that every downstream trading, pricing, and risk agent depends on.

---

## 2. Current Status

| Product | Ground Truth Files | Accuracy | Doc |
|---|---|---|---|
| Government Bond | 6 (4 currencies, 3 frequencies, 4 day counts) | 100% | docs/T002_CDM_Schema_GovernmentBond.md |
| FX Forward | 3 (2 source styles, 1 missing-field edge case) | 100% | docs/T002_CDM_Schema_FXForward.md |
| Interest Rate Swap | 3 (XML/JSON/pipe, 1 missing-spread edge case) | 100% | docs/T002_CDM_Schema_InterestRateSwap.md |

**14 ground truth trades total, 3 completely different products, one shared
codebase.** No agent code was changed to add products #2 or #3 — only schema
files and ground truth were added, proving the registry architecture.

---

## 3. Architecture

```
src/
├── config.py                    All settings (reads .env) - see CONFIGURATION_REFERENCE.md
├── ingestion/
│   └── format_detector.py       Detects CSV/JSON/XML/fixed-width, normalizes to key-value.
│                                  Product-agnostic. Extracts XML attributes as <tag>_<attr>.
├── schemas/
│   ├── government_bond.py       Bond schema, rules, detection hints
│   ├── fx_forward.py            FX schema, rules, detection hints
│   ├── interest_rate_swap.py    Swap schema, rules, detection hints
│   └── registry.py              Maps product_type -> schema. Scoring-based auto-detection.
├── agent/
│   ├── mapping_agent.py         Core map_trade() function. Loads schema from registry.
│   │                              Bulletproof output parser (see Section 5).
│   │                              Supports previous_errors for retry reuse.
│   ├── agent_loop.py            Plan-Act-Reflect loop with validation retry (product-agnostic).
│   └── eval.py                  Evaluation harness. Scans ground truth folders, scores,
│                                  stores every result in the Observation Store.
├── validation/
│   └── validator.py             Product-aware validation dispatch (bond/FX/swap each
│                                  get correct rules). Constructs real finos-cdm objects.
├── registry/
│   └── observation_store.py     T-009. SQLite database. Product-agnostic - product_type
│                                  is just a data column, same tables serve every product.
└── api/
    └── app.py                   FastAPI backend for the Critique UI.

critique_ui.html                 Standalone HTML review interface (talks to api/app.py)
view_store.py                    CLI utility to inspect the Observation Store
setup_ground_truth.py            Generates Government Bond ground truth
setup_ground_truth_fx.py         Generates FX Forward ground truth
setup_ground_truth_irs.py        Generates Interest Rate Swap ground truth
```

---

## 4. The Core Design Principle

**Adding a product means adding files, never changing agent code.** To add
product #4:
1. Write `src/schemas/<product>.py` with `SCHEMA` and `PRODUCT_METADATA`
   (including `detection_hints`).
2. Add one import + one line to `src/schemas/registry.py`.
3. Write `src/validation/validator.py`'s product-specific check function and
   register it in `_PRODUCT_VALIDATORS`.
4. Write a `setup_ground_truth_<product>.py` generator with 3-15 diverse
   trades.
5. Run `python src/agent/eval.py <ProductName>` — everything else (format
   detection, the agent loop, the Observation Store, the Critique UI) works
   immediately with zero changes.

---

## 5. The Recurring Bug Pattern (read this before adding product #4)

**Every product schema hit some version of the same bug: a derived value
computed correctly inside `cdmTrade`, but not given its own `fieldMapping`
entry, or given a different name than expected.**

Occurrences, in order discovered:
1. Government Bond — ISIN scheme not a separate entry from the ISIN value
2. FX Forward — direction folded into the currency entry
3. FX Forward — ccy_pair currency values missing separate entries entirely
4. Interest Rate Swap — payer/receiver entry missing a naming convention

**The fix pattern, every time:** add an explicit rule to the schema stating
(a) this MUST be a separate fieldMapping entry, (b) the exact naming
convention to use, and (c) a worked example with DIFFERENT numbers than any
ground truth file (so the model generalizes the mechanism rather than
memorizing an answer).

**For product #4 and beyond:** proactively include a "Compound Field Rule"
in the schema from the start (copy the wording from `fx_forward.py` or
`interest_rate_swap.py`), rather than discovering this bug again through
trial and error.

---

## 6. Known Limitations (be aware, not urgent)

- **The scorer does exact string matching on fieldMapping names.** A
  functionally correct mapping can score as "wrong" purely from a label
  difference. A more robust future scorer would compare actual `cdmTrade`
  values, not just field mapping labels.
- **XML attribute extraction was fixed once (Section on IRS doc) but only
  tested against the specific sources we had.** Deeply nested or repeated
  attributes on the same tag name are untested.
- **LLM non-determinism.** The same input can occasionally produce a
  slightly different fieldMapping label between runs (observed once on the
  IRS payer/receiver entry). If a single run fails, rerun before assuming a
  real bug — use `python src/agent/eval.py <Product> <file>` for a fast
  single-file retry.
- **No product-type collision testing yet.** With 3 products the detection
  hints don't overlap, but this hasn't been stress-tested with genuinely
  ambiguous trades (e.g. a cross-currency swap, which shares fields with
  both FX and IRS).

---

## 7. What's Built vs What's Next

**Built and working:**
- T-001 through T-009 (see CONFIGURATION_REFERENCE.md for full task list)
- 3 products, 14 ground truth trades, all at 100%
- Observation Store (product-agnostic SQLite)
- Critique UI (FastAPI + HTML), tested end-to-end with live data
- Validation retry loop, product-agnostic
- Fast debug workflow: `eval.py <Product> <file>`

**Natural next steps (not started):**
- A 4th product to further stress-test the registry (Corporate Bond or
  Cross-Currency Swap are next in the original spec's Phase 2)
- Human corrections submitted via the Critique UI aren't yet fed back into
  the agent's prompt as few-shot learning (the Observation Store's
  `learned_mappings` table exists and is populated, but `mapping_agent.py`
  doesn't query it yet)
- PostgreSQL migration (SQLite is fine for one developer; the spec calls for
  PostgreSQL in production)
- Autonomy-level progression (Section 8.3 of the original PRS spec) — every
  conversion is currently Level 0/1 (always available for review); no format
  has been promoted to auto-accept based on proven accuracy yet

---

*For environment setup, git workflow, and terminal command reference, see
your own working notes — this doc covers architecture and product knowledge
only. For every `.env` setting and what HIGH/MEDIUM/LOW confidence means,
see docs/CONFIGURATION_REFERENCE.md.*
