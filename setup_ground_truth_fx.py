"""
setup_ground_truth_fx.py
Generates diverse FX Forward ground truth files.
Run ONCE from the project root: python setup_ground_truth_fx.py
"""

import os
import json

OUT_DIR = os.path.join("data", "ground_truth", "fx_forward")
os.makedirs(OUT_DIR, exist_ok=True)

P_TRADEID = "tradeIdentifier[0].assignedIdentifier[0].identifier"
P_TRADEDATE = "tradeDate.date"
P_CPTY = "party[1].partyId[0].identifier"
P_LEG1_DIR = "product.economicTerms.payoutLeg1.direction"
P_LEG1_VAL = "product.economicTerms.payoutLeg1.amount.value"
P_LEG1_CCY = "product.economicTerms.payoutLeg1.amount.currency"
P_LEG2_DIR = "product.economicTerms.payoutLeg2.direction"
P_LEG2_VAL = "product.economicTerms.payoutLeg2.amount.value"
P_LEG2_CCY = "product.economicTerms.payoutLeg2.amount.currency"
P_SETTLE = "product.economicTerms.settlementDate"


def fm(src, path, conf="HIGH", missing=False, reason=None, transform=None):
    e = {"source_field": src, "cdm_path": path, "confidence": conf}
    if transform:
        e["transformation"] = transform
    if missing:
        e["missingSourceField"] = True
    if reason:
        e["reason"] = reason
    return e


def build(spec):
    cdm = {
        "tradeIdentifier": [{"assignedIdentifier": [{"identifier": spec["trade_id"]}]}],
        "tradeDate": {"date": spec.get("trade_date")},
        "party": [
            {"partyId": [{"identifier": "OUR-BANK", "identifierType": "INTERNAL"}], "name": "OUR BANK PLC", "role": "OUR_BANK"},
            {"partyId": [{"identifier": spec["cpty"], "identifierType": spec.get("cpty_type", "INTERNAL")}], "name": spec.get("cpty_name", spec["cpty"]), "role": "COUNTERPARTY"}
        ],
        "product": {
            "productType": "ForeignExchange.Forward",
            "economicTerms": {
                "payoutLeg1": {"direction": "RECEIVE", "amount": {"value": spec["receive_amount"], "currency": spec["receive_ccy"]}},
                "payoutLeg2": {"direction": "PAY", "amount": {"value": spec["pay_amount"], "currency": spec["pay_ccy"]}},
                "settlementDate": spec["settlement_date"]
            }
        },
        "dates": {"tradeDate": spec.get("trade_date"), "settlementDate": spec["settlement_date"]}
    }
    return {
        "_metadata": {"ground_truth_id": spec["id"], "product_type": "FXForward", "source_format": spec["format"], "description": spec["desc"]},
        "_source": {"raw": spec["raw"]},
        "_field_mapping": spec["field_mapping"],
        "cdmTrade": cdm
    }


TRADES = [
    # fx_001 - EUR/USD, BUY notation, pipe-delimited
    {
        "id": "fx_001", "format": "pipedelimited",
        "desc": "EUR/USD forward, BUY notional style, pipe-delimited",
        "raw": "TRD_ID|CPTY_LEI|BUY_CCY|BUY_NOTIONAL|SELL_CCY|SELL_NOTIONAL|VALUE_DATE|TRADE_DATE\nFXF-001|5493001KJTIIGC8Y1R12|EUR|10000000.00|USD|10850000.00|2026-12-18|2026-09-05",
        "trade_id": "FXF-001", "cpty": "5493001KJTIIGC8Y1R12", "cpty_type": "LEI", "cpty_name": "ACME ASSET MGMT",
        "trade_date": "2026-09-05", "settlement_date": "2026-12-18",
        "receive_ccy": "EUR", "receive_amount": 10000000.00, "pay_ccy": "USD", "pay_amount": 10850000.00,
        "field_mapping": [
            fm("TRD_ID", P_TRADEID), fm("CPTY_LEI", P_CPTY), fm("TRADE_DATE", P_TRADEDATE),
            fm("BUY_CCY", P_LEG1_CCY, transform="BUY currency = receive leg"),
            fm("BUY_NOTIONAL", P_LEG1_VAL),
            fm("BUY_CCY (direction)", P_LEG1_DIR, transform="BUY -> RECEIVE"),
            fm("SELL_CCY", P_LEG2_CCY, transform="SELL currency = pay leg"),
            fm("SELL_NOTIONAL", P_LEG2_VAL),
            fm("SELL_CCY (direction)", P_LEG2_DIR, transform="SELL -> PAY"),
            fm("VALUE_DATE", P_SETTLE)
        ]
    },

    # fx_002 - GBP/JPY, SELL, JSON with ccy_pair + direction style
    {
        "id": "fx_002", "format": "JSON",
        "desc": "GBP/JPY forward, direction=SELL style, JSON",
        "raw": '{"deal_ref":"FXF-002","instrument":"FX_FWD","ccy_pair":"GBP/JPY","direction":"SELL","base_amount":3000000,"quote_amount":570000000,"settle":"2026-11-20","booking_date":"2026-09-10","client_name":"NOMURA SECURITIES","client_lei":"353800LQV0Y32DZS7009"}',
        "trade_id": "FXF-002", "cpty": "353800LQV0Y32DZS7009", "cpty_type": "LEI", "cpty_name": "NOMURA SECURITIES",
        "trade_date": "2026-09-10", "settlement_date": "2026-11-20",
        "receive_ccy": "JPY", "receive_amount": 570000000, "pay_ccy": "GBP", "pay_amount": 3000000,
        "field_mapping": [
            fm("deal_ref", P_TRADEID), fm("client_lei", P_CPTY), fm("booking_date", P_TRADEDATE),
            fm("base_amount", P_LEG2_VAL, transform="SELL base(GBP)=pay leg"),
            fm("ccy_pair (base)", P_LEG2_CCY, conf="MEDIUM", transform="GBP/JPY base=GBP", reason="Currency parsed from first 3 chars of ccy_pair"),
            fm("direction (leg2)", P_LEG2_DIR, transform="SELL -> PAY base"),
            fm("quote_amount", P_LEG1_VAL, transform="SELL quote(JPY)=receive leg"),
            fm("ccy_pair (quote)", P_LEG1_CCY, conf="MEDIUM", transform="GBP/JPY quote=JPY", reason="Currency parsed from last 3 chars of ccy_pair"),
            fm("direction (leg1)", P_LEG1_DIR, transform="SELL -> RECEIVE quote"),
            fm("settle", P_SETTLE)
        ]
    },

    # fx_003 - USD/CHF, BUY, fixed-width, missing settlement date (edge case)
    {
        "id": "fx_003", "format": "fixedwidth",
        "desc": "USD/CHF forward, BUY, fixed-width, missing settlement date",
        "raw": "TRD_ID   CPTY     BUY_CCY BUY_AMT     SELL_CCY SELL_AMT    TRADE_DT\nFXF003   UBS      USD     5000000.00  CHF      4425000.00  2026-09-12",
        "trade_id": "FXF003", "cpty": "UBS", "cpty_type": "INTERNAL", "cpty_name": "UBS",
        "trade_date": "2026-09-12", "settlement_date": None,
        "receive_ccy": "USD", "receive_amount": 5000000.00, "pay_ccy": "CHF", "pay_amount": 4425000.00,
        "field_mapping": [
            fm("TRD_ID", P_TRADEID), fm("CPTY", P_CPTY, conf="MEDIUM", reason="Short code only, no LEI in source"),
            fm("TRADE_DT", P_TRADEDATE),
            fm("BUY_CCY", P_LEG1_CCY), fm("BUY_AMT", P_LEG1_VAL), fm("BUY_CCY (direction)", P_LEG1_DIR, transform="BUY -> RECEIVE"),
            fm("SELL_CCY", P_LEG2_CCY), fm("SELL_AMT", P_LEG2_VAL), fm("SELL_CCY (direction)", P_LEG2_DIR, transform="SELL -> PAY"),
            fm("settlementDate (inferred)", P_SETTLE, conf="LOW", missing=True,
               reason="No settlement or value date present in source data. Required field for FX forwards - must be confirmed by human reviewer, no safe default exists.")
        ]
    },
]


def main():
    for spec in TRADES:
        gt = build(spec)
        fname = spec["id"] + "_" + spec["format"] + ".json"
        path = os.path.join(OUT_DIR, fname)
        with open(path, "w") as f:
            json.dump(gt, f, indent=2)
        print("Created: " + path + "  (" + spec["desc"] + ")")
    print("\nDone. " + str(len(TRADES)) + " FX forward ground truth files created in " + OUT_DIR)


if __name__ == "__main__":
    main()
