# Ground Truth — Forward Rate Agreement (FRA)

Parallel to the IRS ground-truth set (v2/data/ground_truth/interest_rate_swap/)
but for the FRA product, which uses its own schema (FRAInput) and builder
(build_fra_trade_state) since FRA's single-period, net-settlement structure
doesn't fit the IRS leg/schedule shape.

## Layout

```
v2/data/ground_truth/fra/
  fra/   input.txt   expected_cdm.json
```

| case | input format style | reference file |
|---|---|---|
| fra | deal ticket free text | swaps/irs-fra.json |

`expected_cdm.json` is a byte-identical copy of the FINXIS reference file.

## Eval design

Same pattern as the IRS eval: extraction is the tested step, the build step
is separately proven (v2/tests/compare_reference.py, "fra" case, exact
match). Run:

```
python v2/eval/run_eval_fra.py --oracle      # harness self-test
python v2/eval/run_eval_fra.py                # real agent, sonnet (default)
python v2/eval/run_eval_fra.py --extractor opus
```

## Mapping conventions specific to FRA (agent configuration, not in raw input)

| concept | raw vocabulary → CDM value |
|---|---|
| isda_taxonomy | always `InterestRate_Fra` for any FRA |
| reset_date / termination_date | given as already-adjusted single-period boundary dates; stored directly, no separate BDC needed for these two |
| fixed_leg_payment_freq_multiplier/period | ONLY set when the record separately states a "Fixed Interest Period" / "contract period" for the fixed leg — a FRA-specific artifact, not the general index tenor |
| trade identifier scheme | if the record states a scheme URL literally, use it verbatim (add `http://` if missing) rather than mapping to a different known convention |
| fixing offset sign | negative when fixing is before the reset date (the normal FRA case) |

## Extractor

FRA has its own extractor module (parallels the IRS split):
```
v2/src/agent/fra_extractor_core.py    - shared schema builder, FRA prompt, tool
v2/src/agent/fra_extractor_sonnet.py  - thin wrapper, claude-sonnet-4-6 (default)
v2/src/agent/fra_extractor_opus.py    - thin wrapper, claude-opus-4-6
```
