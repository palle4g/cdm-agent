# CDM Mapping Agent

**An AI agent that automatically converts legacy bank trade data into the ISDA Common Domain Model (CDM) — no manual mapping, no per-format integration work.**

Status: 3 financial products live · 14 diverse test trades · 100% mapping accuracy · Human review UI operational

---

## The Problem

Banks store trade data in decades-old, incompatible formats. Citi runs 17 separate systems just for interest rate swaps. Another's core trading data flows through systems 30–40 years old. Every format has different field names for the same concept — `CPTY_CODE`, `COUNTERPARTY_ID`, `CTR_PTY` might all mean "who's on the other side of this trade."

This fragmentation is why banks struggle to calculate firm-wide risk in real time, why regulatory reporting is slow and error-prone, and why AI initiatives stall — you cannot build intelligent systems on top of data you cannot even read consistently.

**Mapping one legacy format to a common standard, by hand, has historically taken two experienced data modelers two months for a single product type.**

## The Solution

This project uses an AI agent to do that mapping automatically — in seconds, for any source format, for multiple financial products — and validates every result against the real ISDA CDM schema before accepting it.

```
Legacy Trade (any format)  →  AI Agent  →  Validated CDM Output  →  Human Review (optional)
     CSV / JSON / XML          reads &          checked against         via web UI
     fixed-width / etc.        maps fields      real CDM schema
```

---

## Current Results

| Financial Product | Test Trades | Formats Covered | Accuracy |
|---|---|---|---|
| Government Bond | 6 | CSV, JSON, fixed-width | **100%** |
| FX Forward | 3 | CSV, JSON, fixed-width | **100%** |
| Interest Rate Swap | 3 | XML, JSON, CSV | **100%** |

Each product was tested across multiple currencies, conventions, and edge cases (missing fields, different day-count standards, buy/sell sides) — not just one trade repeated in different formats.

**Three completely different financial products, one shared codebase.** Adding each new product required zero changes to the core agent logic — only a new schema file and a set of test cases. This proves the architecture scales.

---

## How It Works

1. **Format Detection** — the system reads any input (CSV, JSON, XML, pipe-delimited, fixed-width) and automatically identifies its structure, with no configuration needed per source.
2. **AI Mapping** — Claude (Anthropic's AI model) reads the raw fields and maps each one to the correct location in the CDM standard, applying real financial domain rules (e.g., converting a coupon rate from a percentage to a decimal, correctly identifying which side of a trade is the payer vs. receiver).
3. **Validation** — every mapped result is checked against the actual, official CDM schema library. If something is wrong, the specific error is fed back to the AI, which corrects itself and retries — up to 3 times — before flagging the trade for human review.
4. **Observation Store** — every conversion, every field-level decision, and every confidence rating is permanently recorded in a database. This becomes the audit trail and the foundation for the system getting smarter over time.
5. **Human Review (Critique UI)** — a reviewer can browse every conversion in a web interface, see exactly what the AI mapped and why (including its reasoning for anything inferred or uncertain), and correct anything wrong.

---

## Why This Matters

- **Speed**: seconds per trade vs. months of manual mapping work
- **Scalability**: the same system handles bonds, FX, and swaps today — adding the next product type is a matter of days, not months
- **Transparency**: every mapping decision includes a confidence level (High/Medium/Low) and, where the AI had to infer or guess, a plain-English explanation of why
- **Auditability**: nothing is a black box — every conversion is permanently logged with full traceability (which AI model made the decision, what the source data was, what was inferred vs. directly mapped)
- **Human oversight where it matters**: low-confidence or unusual mappings are automatically flagged for review rather than silently accepted

This is Phase 0 of a larger vision (internally referred to as TP-GPT) for AI-driven trading operations — this data-standardization layer is the foundation every downstream trading, risk, and pricing agent will depend on.

---

## Screenshots

**The Critique UI** — reviewers see the original trade data, the AI's field-by-field mapping decisions with confidence levels, and the final standardized output, side by side:

*(see critique_ui.html — run locally to view live data)*

---

## Technology

- **Python** — core application logic
- **Claude (Anthropic API)** — the AI mapping agent
- **FINOS Common Domain Model** — the official, open-source industry standard this project maps into
- **SQLite** — the Observation Store (production would use PostgreSQL)
- **FastAPI** — backend serving the review interface
- **Git / GitHub** — version control

---

## Project Structure

```
src/
├── ingestion/          Detects and parses any input format
├── schemas/            One file per financial product (bond, FX, swap...)
├── agent/              The AI mapping engine and evaluation harness
├── validation/         Checks output against the real CDM standard
├── registry/           The permanent record of every conversion
└── api/                Backend for the review interface

data/
└── ground_truth/       Hand-verified correct answers, used to measure accuracy

docs/
├── PROJECT_OVERVIEW.md          Full technical architecture and design decisions
└── CONFIGURATION_REFERENCE.md   Every setting explained in plain language

critique_ui.html        The human review interface
```

---

## Running This Project

Requires Python 3.12+ and an Anthropic API key.

```bash
# Set up environment
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

# Add your API key to .env
echo "ANTHROPIC_API_KEY=your_key_here" > .env

# Run the full evaluation across all products
python src/agent/eval.py

# Launch the review interface
uvicorn src.api.app:app --reload --port 8000
# then open critique_ui.html in a browser
```

See `docs/PROJECT_OVERVIEW.md` for full architecture detail and `docs/CONFIGURATION_REFERENCE.md` for every configurable setting.

---

## Roadmap

- [x] Government Bond mapping (Phase 1)
- [x] FX Forward mapping (Phase 1)
- [x] Interest Rate Swap mapping (Phase 2)
- [x] Human review interface
- [ ] Corporate Bond / Cross-Currency Swap (next products)
- [ ] Feed human corrections back into the AI's learning process
- [ ] Production database (PostgreSQL)
- [ ] Autonomous processing for proven, high-confidence formats

---

*This project is an internal proof of concept demonstrating AI-driven data standardization for capital markets infrastructure.*
