"""
setup_ground_truth.py
Generates a diverse set of government bond ground truth files.
Run ONCE from the project root:  python setup_ground_truth.py

Creates data/ground_truth/government_bond/ with diverse trades covering
multiple currencies, coupon frequencies, day counts, buy/sell, and formats.
Each file stores the raw input, the correct field mapping, and the CDM output.
"""

import os
import json

OUT_DIR = os.path.join("data", "ground_truth", "government_bond")
os.makedirs(OUT_DIR, exist_ok=True)

# CDM path constants
P_TRADEID = "tradeIdentifier[0].assignedIdentifier[0].identifier"
P_TRADEDATE = "tradeDate.date"
P_CPTY = "party[1].partyId[0].identifier"
P_ISIN = "product.productIdentifier[0].identifier"
P_ISIN_SCHEME = "product.productIdentifier[0].source"
P_EFF = "product.economicTerms.effectiveDate.adjustableDate.unadjustedDate"
P_TERM = "product.economicTerms.terminationDate.adjustableDate.unadjustedDate"
P_AMT = "product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.amount"
P_CCY = "product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.unit.currency"
P_RATE = "product.economicTerms.payout[0].interestRatePayout.rateSpecification.fixedRate.rateSchedule.initialValue"
P_FREQ = "product.economicTerms.payout[0].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency"
P_DCF = "product.economicTerms.payout[0].interestRatePayout.dayCountFraction"
P_PR = "product.economicTerms.payout[0].interestRatePayout.payerReceiver"


def freq_to_cdm(freq):
    f = freq.upper()
    if f in ["SEMI", "S", "SEMI-ANNUAL", "SEMIANNUAL"]:
        return {"period": "M", "periodMultiplier": 6}
    if f in ["ANNUAL", "A", "Y"]:
        return {"period": "Y", "periodMultiplier": 1}
    if f in ["QUARTERLY", "Q"]:
        return {"period": "M", "periodMultiplier": 3}
    return {"period": "M", "periodMultiplier": 6}


def side_to_pr(side):
    s = side.upper()
    if s in ["BUY", "B", "PURCHASE"]:
        return {"payer": "Party2", "receiver": "Party1"}
    return {"payer": "Party1", "receiver": "Party2"}


def build(spec):
    """Build a full ground truth dict from a compact spec."""
    pr = side_to_pr(spec["side"])
    freq = freq_to_cdm(spec["freq"])

    cdm = {
        "tradeIdentifier": [{"assignedIdentifier": [{"identifier": spec["trade_id"]}]}],
        "tradeDate": {"date": spec.get("trade_date")},
        "party": [
            {"partyId": [{"identifier": "OUR-BANK", "identifierType": "INTERNAL"}], "name": "OUR BANK PLC", "role": "OUR_BANK"},
            {"partyId": [{"identifier": spec["cpty"], "identifierType": spec.get("cpty_type", "INTERNAL")}], "name": spec.get("cpty_name", spec["cpty"]), "role": "COUNTERPARTY"}
        ],
        "product": {
            "productType": "Rates.GovernmentBond",
            "productIdentifier": [{"identifier": spec["isin"], "source": "ISIN"}],
            "economicTerms": {
                "effectiveDate": {"adjustableDate": {"unadjustedDate": spec.get("settle_date")}},
                "terminationDate": {"adjustableDate": {"unadjustedDate": spec["maturity"]}},
                "payout": [{
                    "interestRatePayout": {
                        "payerReceiver": pr,
                        "rateSpecification": {"fixedRate": {"rateSchedule": {"initialValue": spec["rate"]}}},
                        "dayCountFraction": spec["day_count"],
                        "calculationPeriodDates": {
                            "terminationDate": {"adjustableDate": {"unadjustedDate": spec["maturity"]}},
                            "calculationPeriodFrequency": freq
                        },
                        "principalPayment": {"principalAmount": {"amount": spec["amount"], "unit": {"currency": spec["currency"]}}}
                    }
                }]
            }
        },
        "dates": {"tradeDate": spec.get("trade_date"), "settlementDate": spec.get("settle_date"), "maturityDate": spec["maturity"]}
    }

    return {
        "_metadata": {
            "ground_truth_id": spec["id"],
            "product_type": "GovernmentBond.FixedRate",
            "source_format": spec["format"],
            "description": spec["desc"]
        },
        "_source": {"raw": spec["raw"]},
        "_field_mapping": spec["field_mapping"],
        "cdmTrade": cdm
    }


# core mapping entries shared shape helper
def fm(src, path, conf="HIGH", missing=False, reason=None, transform=None):
    e = {"source_field": src, "cdm_path": path, "confidence": conf}
    if transform:
        e["transformation"] = transform
    if missing:
        e["missingSourceField"] = True
    if reason:
        e["reason"] = reason
    return e


TRADES = [

    # gb_001 - US Treasury, USD, semi-annual, ACT/ACT, BUY, pipe-delimited
    {
        "id": "gb_001", "format": "pipe-delimited",
        "desc": "US Treasury, USD, semi-annual, ACT/ACT, BUY",
        "raw": "TRADE_NUM|ISIN|SIDE|QTY|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT\nGB001|US91282CJL54|BUY|10000000|JPMORGAN|2026-09-14|2026-09-16|2034-08-15|4.25|SEMI|ACT/ACT",
        "trade_id": "GB001", "isin": "US91282CJL54", "side": "BUY", "amount": 10000000,
        "cpty": "JPMORGAN", "cpty_name": "JPMORGAN", "trade_date": "2026-09-14",
        "settle_date": "2026-09-16", "maturity": "2034-08-15", "rate": 0.0425,
        "freq": "SEMI", "day_count": "ACT/ACT.ICMA", "currency": "USD",
        "field_mapping": [
            fm("TRADE_NUM", P_TRADEID), fm("TRADE_DT", P_TRADEDATE),
            fm("ISIN", P_ISIN), fm("ISIN (scheme)", P_ISIN_SCHEME, reason="Scheme inferred from field name and 12-char format"),
            fm("CPTY_CODE", P_CPTY), fm("SETTLE_DT", P_EFF), fm("MATURE_DT", P_TERM),
            fm("QTY", P_AMT), fm("COUPON", P_RATE, transform="4.25/100=0.0425"),
            fm("FREQ", P_FREQ, transform="SEMI->M,6"), fm("DAY_COUNT", P_DCF, transform="ACT/ACT->ACT/ACT.ICMA"),
            fm("SIDE", P_PR, transform="BUY->payer=Party2,receiver=Party1")
        ]
    },

    # gb_002 - German Bund, EUR, annual, 30/360, BUY, pipe-delimited
    {
        "id": "gb_002", "format": "pipe-delimited",
        "desc": "German Bund, EUR, annual, 30/360, BUY",
        "raw": "TRADE_NUM|ISIN|SIDE|QTY|CCY|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT\nGB002|DE0001102580|BUY|5000000|EUR|DEUTSCHE|2026-09-14|2026-09-16|2033-05-15|2.30|ANNUAL|30/360",
        "trade_id": "GB002", "isin": "DE0001102580", "side": "BUY", "amount": 5000000,
        "cpty": "DEUTSCHE", "cpty_name": "DEUTSCHE BANK", "trade_date": "2026-09-14",
        "settle_date": "2026-09-16", "maturity": "2033-05-15", "rate": 0.023,
        "freq": "ANNUAL", "day_count": "30/360", "currency": "EUR",
        "field_mapping": [
            fm("TRADE_NUM", P_TRADEID), fm("TRADE_DT", P_TRADEDATE),
            fm("ISIN", P_ISIN), fm("ISIN (scheme)", P_ISIN_SCHEME, reason="Scheme inferred from field name and 12-char format"),
            fm("CPTY_CODE", P_CPTY), fm("SETTLE_DT", P_EFF), fm("MATURE_DT", P_TERM),
            fm("QTY", P_AMT), fm("CCY", P_CCY),
            fm("COUPON", P_RATE, transform="2.30/100=0.023"),
            fm("FREQ", P_FREQ, transform="ANNUAL->Y,1"), fm("DAY_COUNT", P_DCF, transform="30/360->30/360"),
            fm("SIDE", P_PR, transform="BUY->payer=Party2,receiver=Party1")
        ]
    },

    # gb_003 - UK Gilt, GBP, semi-annual, ACT/365, SELL, JSON
    {
        "id": "gb_003", "format": "JSON",
        "desc": "UK Gilt, GBP, semi-annual, ACT/365, SELL",
        "raw": '{"deal_id":"GB003","security":"GB00BLPK7110","transaction_type":"SELL","face_value":8000000,"currency":"GBP","coupon_rate":3.75,"payment_frequency":"SEMI-ANNUAL","day_count_basis":"ACT/365","trade_date":"2026-09-14","settlement_date":"2026-09-16","maturity_date":"2035-01-31","counterparty":"BARCLAYS","counterparty_lei":"K7GEUW7YXOX6DZBLZC10"}',
        "trade_id": "GB003", "isin": "GB00BLPK7110", "side": "SELL", "amount": 8000000,
        "cpty": "K7GEUW7YXOX6DZBLZC10", "cpty_type": "LEI", "cpty_name": "BARCLAYS",
        "trade_date": "2026-09-14", "settle_date": "2026-09-16", "maturity": "2035-01-31",
        "rate": 0.0375, "freq": "SEMI-ANNUAL", "day_count": "ACT/365.FIXED", "currency": "GBP",
        "field_mapping": [
            fm("deal_id", P_TRADEID), fm("trade_date", P_TRADEDATE),
            fm("security", P_ISIN), fm("security (scheme)", P_ISIN_SCHEME, reason="Scheme inferred from GB-prefix 12-char format"),
            fm("counterparty_lei", P_CPTY), fm("settlement_date", P_EFF), fm("maturity_date", P_TERM),
            fm("face_value", P_AMT), fm("currency", P_CCY),
            fm("coupon_rate", P_RATE, transform="3.75/100=0.0375"),
            fm("payment_frequency", P_FREQ, transform="SEMI-ANNUAL->M,6"),
            fm("day_count_basis", P_DCF, transform="ACT/365->ACT/365.FIXED"),
            fm("transaction_type", P_PR, transform="SELL->payer=Party1,receiver=Party2")
        ]
    },

    # gb_004 - Japan Govt Bond, JPY, semi-annual, ACT/ACT, BUY, pipe-delimited
    {
        "id": "gb_004", "format": "pipe-delimited",
        "desc": "Japan Government Bond, JPY, semi-annual, ACT/ACT, BUY",
        "raw": "TRADE_NUM|ISIN|SIDE|QTY|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT\nGB004|JP1103271G95|BUY|500000000|NOMURA|2026-09-14|2026-09-17|2036-06-20|0.80|SEMI|ACT/ACT",
        "trade_id": "GB004", "isin": "JP1103271G95", "side": "BUY", "amount": 500000000,
        "cpty": "NOMURA", "cpty_name": "NOMURA", "trade_date": "2026-09-14",
        "settle_date": "2026-09-17", "maturity": "2036-06-20", "rate": 0.008,
        "freq": "SEMI", "day_count": "ACT/ACT.ICMA", "currency": "JPY",
        "field_mapping": [
            fm("TRADE_NUM", P_TRADEID), fm("TRADE_DT", P_TRADEDATE),
            fm("ISIN", P_ISIN), fm("ISIN (scheme)", P_ISIN_SCHEME, reason="Scheme inferred from JP-prefix 12-char format"),
            fm("CPTY_CODE", P_CPTY), fm("SETTLE_DT", P_EFF), fm("MATURE_DT", P_TERM),
            fm("QTY", P_AMT), fm("COUPON", P_RATE, transform="0.80/100=0.008"),
            fm("FREQ", P_FREQ, transform="SEMI->M,6"), fm("DAY_COUNT", P_DCF, transform="ACT/ACT->ACT/ACT.ICMA"),
            fm("SIDE", P_PR, transform="BUY->payer=Party2,receiver=Party1")
        ]
    },

    # gb_005 - US Treasury, fixed-width, missing currency AND day count (inference test), BUY
    {
        "id": "gb_005", "format": "fixed-width",
        "desc": "US Treasury, fixed-width, currency and day count inferred",
        "raw": "TRADE_ID  ISIN          SIDE QTY        COUPON FREQ MAT_DATE   CPTY\nGB005     US91282CKQ98  B    20000000   3.8750 S    20300215   CITI",
        "trade_id": "GB005", "isin": "US91282CKQ98", "side": "B", "amount": 20000000,
        "cpty": "CITI", "cpty_name": "CITI", "trade_date": None,
        "settle_date": None, "maturity": "2030-02-15", "rate": 0.03875,
        "freq": "S", "day_count": "ACT/ACT.ICMA", "currency": "USD",
        "field_mapping": [
            fm("TRADE_ID", P_TRADEID),
            fm("ISIN", P_ISIN), fm("ISIN (scheme)", P_ISIN_SCHEME, reason="Scheme inferred from US-prefix 12-char format"),
            fm("CPTY", P_CPTY, conf="MEDIUM", reason="Short code only, no LEI available"),
            fm("MAT_DATE", P_TERM, transform="20300215->2030-02-15"),
            fm("QTY", P_AMT),
            fm("currency (inferred)", P_CCY, conf="MEDIUM", missing=True, transform="ISIN US->USD",
               reason="No currency field in source. Inferred from ISIN prefix US=USD. Review recommended."),
            fm("COUPON", P_RATE, transform="3.875/100=0.03875"),
            fm("FREQ", P_FREQ, transform="S->M,6"),
            fm("day_count (inferred)", P_DCF, conf="MEDIUM", missing=True, transform="defaulted",
               reason="No day count in source. Defaulted to ACT/ACT.ICMA standard for government bonds. Review recommended."),
            fm("SIDE", P_PR, transform="B->payer=Party2,receiver=Party1")
        ]
    },

    # gb_006 - US Treasury, USD, quarterly, ACT/360, SELL, JSON
    {
        "id": "gb_006", "format": "JSON",
        "desc": "US Treasury, USD, quarterly, ACT/360, SELL",
        "raw": '{"deal_id":"GB006","security":"US912810TM09","transaction_type":"SELL","face_value":15000000,"currency":"USD","coupon_rate":4.00,"payment_frequency":"QUARTERLY","day_count_basis":"ACT/360","trade_date":"2026-09-15","settlement_date":"2026-09-17","maturity_date":"2040-11-15","counterparty":"WELLS FARGO","counterparty_lei":"KB1H1DSPRFMYMCUFXT09"}',
        "trade_id": "GB006", "isin": "US912810TM09", "side": "SELL", "amount": 15000000,
        "cpty": "KB1H1DSPRFMYMCUFXT09", "cpty_type": "LEI", "cpty_name": "WELLS FARGO",
        "trade_date": "2026-09-15", "settle_date": "2026-09-17", "maturity": "2040-11-15",
        "rate": 0.04, "freq": "QUARTERLY", "day_count": "ACT/360", "currency": "USD",
        "field_mapping": [
            fm("deal_id", P_TRADEID), fm("trade_date", P_TRADEDATE),
            fm("security", P_ISIN), fm("security (scheme)", P_ISIN_SCHEME, reason="Scheme inferred from US-prefix 12-char format"),
            fm("counterparty_lei", P_CPTY), fm("settlement_date", P_EFF), fm("maturity_date", P_TERM),
            fm("face_value", P_AMT), fm("currency", P_CCY),
            fm("coupon_rate", P_RATE, transform="4.00/100=0.04"),
            fm("payment_frequency", P_FREQ, transform="QUARTERLY->M,3"),
            fm("day_count_basis", P_DCF, transform="ACT/360->ACT/360"),
            fm("transaction_type", P_PR, transform="SELL->payer=Party1,receiver=Party2")
        ]
    },
]


def main():
    count = 0
    for spec in TRADES:
        gt = build(spec)
        fname = spec["id"] + "_" + spec["format"].replace("-", "") + ".json"
        path = os.path.join(OUT_DIR, fname)
        with open(path, "w") as f:
            json.dump(gt, f, indent=2)
        print("Created: " + path + "  (" + spec["desc"] + ")")
        count += 1
    print("\nDone. " + str(count) + " ground truth files created in " + OUT_DIR)


if __name__ == "__main__":
    main()
