"""
setup_ground_truth_irs.py
Generates diverse Interest Rate Swap ground truth files.
Run ONCE from the project root: python setup_ground_truth_irs.py
"""

import os
import json

OUT_DIR = os.path.join("data", "ground_truth", "interest_rate_swap")
os.makedirs(OUT_DIR, exist_ok=True)

P_TRADEID = "tradeIdentifier[0].assignedIdentifier[0].identifier"
P_TRADEDATE = "tradeDate.date"
P_CPTY = "party[1].partyId[0].identifier"
P_EFF = "product.economicTerms.effectiveDate.adjustableDate.unadjustedDate"
P_TERM = "product.economicTerms.terminationDate.adjustableDate.unadjustedDate"
P_NOTIONAL = "product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.amount"
P_CCY = "product.economicTerms.payout[0].interestRatePayout.principalPayment.principalAmount.unit.currency"
P_FIXRATE = "product.economicTerms.payout[0].interestRatePayout.rateSpecification.fixedRate.rateSchedule.initialValue"
P_FIXFREQ = "product.economicTerms.payout[0].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency"
P_FIXDCF = "product.economicTerms.payout[0].interestRatePayout.dayCountFraction"
P_PR = "product.economicTerms.payout[0].interestRatePayout.payerReceiver"
P_FLTINDEX = "product.economicTerms.payout[1].interestRatePayout.rateSpecification.floatingRate.index"
P_FLTSPREAD = "product.economicTerms.payout[1].interestRatePayout.rateSpecification.floatingRate.spread"
P_FLTFREQ = "product.economicTerms.payout[1].interestRatePayout.calculationPeriodDates.calculationPeriodFrequency"
P_FLTDCF = "product.economicTerms.payout[1].interestRatePayout.dayCountFraction"


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
            "productType": "InterestRate.Swap",
            "economicTerms": {
                "effectiveDate": {"adjustableDate": {"unadjustedDate": spec["effective_date"]}},
                "terminationDate": {"adjustableDate": {"unadjustedDate": spec["termination_date"]}},
                "payout": [
                    {
                        "interestRatePayout": {
                            "payerReceiver": spec["fixed_pr"],
                            "rateSpecification": {"fixedRate": {"rateSchedule": {"initialValue": spec["fixed_rate"]}}},
                            "dayCountFraction": spec["fixed_dcf"],
                            "calculationPeriodDates": {"calculationPeriodFrequency": spec["fixed_freq"]},
                            "principalPayment": {"principalAmount": {"amount": spec["notional"], "unit": {"currency": spec["currency"]}}}
                        }
                    },
                    {
                        "interestRatePayout": {
                            "rateSpecification": {"floatingRate": {"index": spec["float_index"], "spread": spec["spread"]}},
                            "dayCountFraction": spec["float_dcf"],
                            "calculationPeriodDates": {"calculationPeriodFrequency": spec["float_freq"]}
                        }
                    }
                ]
            }
        }
    }
    return {
        "_metadata": {"ground_truth_id": spec["id"], "product_type": "InterestRateSwap", "source_format": spec["format"], "description": spec["desc"]},
        "_source": {"raw": spec["raw"]},
        "_field_mapping": spec["field_mapping"],
        "cdmTrade": cdm
    }


TRADES = [
    # irs_001 - USD, fixed vs SOFR, XML style, we pay fixed
    {
        "id": "irs_001", "format": "XML",
        "desc": "USD 5y swap, fixed vs SOFR, we pay fixed, XML",
        "raw": '<swap><tradeId>IRS-2026-55210</tradeId><tradeDate>2026-09-14</tradeDate><effectiveDate>2026-10-01</effectiveDate><terminationDate>2031-10-01</terminationDate><notional currency="USD">25000000</notional><fixedRate>3.85</fixedRate><fixedFreq>SEMI</fixedFreq><fixedDayCount>30/360</fixedDayCount><floatIndex>SOFR</floatIndex><spread>0.00</spread><floatFreq>QUARTERLY</floatFreq><floatDayCount>ACT/360</floatDayCount><counterparty lei="549300EXAMPLE01">BARCLAYS CAPITAL</counterparty></swap>',
        "trade_id": "IRS-2026-55210", "trade_date": "2026-09-14", "effective_date": "2026-10-01", "termination_date": "2031-10-01",
        "cpty": "549300EXAMPLE01", "cpty_type": "LEI", "cpty_name": "BARCLAYS CAPITAL",
        "notional": 25000000, "currency": "USD", "fixed_rate": 0.0385, "fixed_freq": {"period": "M", "periodMultiplier": 6},
        "fixed_dcf": "30/360", "fixed_pr": {"payer": "Party1", "receiver": "Party2"},
        "float_index": "SOFR", "spread": 0.0, "float_freq": {"period": "M", "periodMultiplier": 3}, "float_dcf": "ACT/360",
        "field_mapping": [
            fm("tradeId", P_TRADEID), fm("tradeDate", P_TRADEDATE), fm("counterparty", P_CPTY),
            fm("effectiveDate", P_EFF), fm("terminationDate", P_TERM),
            fm("notional", P_NOTIONAL), fm("notional (currency)", P_CCY, reason="Currency given as XML attribute on notional element"),
            fm("fixedRate", P_FIXRATE, transform="3.85/100=0.0385"),
            fm("fixedFreq", P_FIXFREQ, transform="SEMI->M,6"),
            fm("fixedDayCount", P_FIXDCF, transform="30/360->30/360"),
            fm("counterparty (payer/receiver)", P_PR, conf="MEDIUM", reason="No explicit pay/receive flag in source - defaulted to we pay fixed per standard bank hedging convention"),
            fm("floatIndex", P_FLTINDEX), fm("spread", P_FLTSPREAD),
            fm("floatFreq", P_FLTFREQ, transform="QUARTERLY->M,3"),
            fm("floatDayCount", P_FLTDCF, transform="ACT/360->ACT/360")
        ]
    },

    # irs_002 - EUR, fixed vs EURIBOR with spread, JSON, we receive fixed (pay float)
    {
        "id": "irs_002", "format": "JSON",
        "desc": "EUR 7y swap, fixed vs EURIBOR+spread, we receive fixed, JSON",
        "raw": '{"deal_id":"IRS-2026-88120","trade_date":"2026-09-15","effective_date":"2026-09-17","termination_date":"2033-09-17","notional":40000000,"currency":"EUR","fixed_rate":2.95,"fixed_frequency":"ANNUAL","fixed_day_count":"30/360","float_index":"EURIBOR","float_spread":0.15,"float_frequency":"QUARTERLY","float_day_count":"ACT/360","pay_receive":"RECEIVE_FIXED","counterparty_lei":"7LTWFZYICNSX8D621K86","counterparty_name":"DEUTSCHE BANK"}',
        "trade_id": "IRS-2026-88120", "trade_date": "2026-09-15", "effective_date": "2026-09-17", "termination_date": "2033-09-17",
        "cpty": "7LTWFZYICNSX8D621K86", "cpty_type": "LEI", "cpty_name": "DEUTSCHE BANK",
        "notional": 40000000, "currency": "EUR", "fixed_rate": 0.0295, "fixed_freq": {"period": "Y", "periodMultiplier": 1},
        "fixed_dcf": "30/360", "fixed_pr": {"payer": "Party2", "receiver": "Party1"},
        "float_index": "EURIBOR", "spread": 0.0015, "float_freq": {"period": "M", "periodMultiplier": 3}, "float_dcf": "ACT/360",
        "field_mapping": [
            fm("deal_id", P_TRADEID), fm("trade_date", P_TRADEDATE), fm("counterparty_lei", P_CPTY),
            fm("effective_date", P_EFF), fm("termination_date", P_TERM),
            fm("notional", P_NOTIONAL), fm("currency", P_CCY),
            fm("fixed_rate", P_FIXRATE, transform="2.95/100=0.0295"),
            fm("fixed_frequency", P_FIXFREQ, transform="ANNUAL->Y,1"),
            fm("fixed_day_count", P_FIXDCF, transform="30/360->30/360"),
            fm("pay_receive", P_PR, transform="RECEIVE_FIXED -> payer=Party2,receiver=Party1"),
            fm("float_index", P_FLTINDEX), fm("float_spread", P_FLTSPREAD, transform="0.15/100=0.0015"),
            fm("float_frequency", P_FLTFREQ, transform="QUARTERLY->M,3"),
            fm("float_day_count", P_FLTDCF, transform="ACT/360->ACT/360")
        ]
    },

    # irs_003 - GBP, fixed vs SONIA, pipe-delimited, missing spread (inference test)
    {
        "id": "irs_003", "format": "pipedelimited",
        "desc": "GBP 3y swap, fixed vs SONIA, missing spread field, pipe-delimited",
        "raw": "TRD_ID|TRADE_DT|EFF_DT|TERM_DT|NOTIONAL|CCY|FIX_RATE|FIX_FREQ|FIX_DCF|FLT_INDEX|FLT_FREQ|FLT_DCF|CPTY\nIRS003|2026-09-16|2026-09-18|2029-09-18|15000000|GBP|4.10|SEMI|ACT/365|SONIA|QUARTERLY|ACT/365|HSBC",
        "trade_id": "IRS003", "trade_date": "2026-09-16", "effective_date": "2026-09-18", "termination_date": "2029-09-18",
        "cpty": "HSBC", "cpty_type": "INTERNAL", "cpty_name": "HSBC",
        "notional": 15000000, "currency": "GBP", "fixed_rate": 0.041, "fixed_freq": {"period": "M", "periodMultiplier": 6},
        "fixed_dcf": "ACT/365.FIXED", "fixed_pr": {"payer": "Party1", "receiver": "Party2"},
        "float_index": "SONIA", "spread": 0.0, "float_freq": {"period": "M", "periodMultiplier": 3}, "float_dcf": "ACT/365.FIXED",
        "field_mapping": [
            fm("TRD_ID", P_TRADEID), fm("TRADE_DT", P_TRADEDATE), fm("CPTY", P_CPTY, conf="MEDIUM", reason="Short code only, no LEI available"),
            fm("EFF_DT", P_EFF), fm("TERM_DT", P_TERM),
            fm("NOTIONAL", P_NOTIONAL), fm("CCY", P_CCY),
            fm("FIX_RATE", P_FIXRATE, transform="4.10/100=0.041"),
            fm("FIX_FREQ", P_FIXFREQ, transform="SEMI->M,6"),
            fm("FIX_DCF", P_FIXDCF, transform="ACT/365->ACT/365.FIXED"),
            fm("CPTY (payer/receiver)", P_PR, conf="MEDIUM", reason="No explicit pay/receive flag in source - defaulted to we pay fixed per standard convention"),
            fm("FLT_INDEX", P_FLTINDEX),
            fm("spread (inferred)", P_FLTSPREAD, conf="MEDIUM", missing=True, transform="defaulted to 0.0",
               reason="No spread field present in source data. Defaulted to 0.0 (flat to index). Human review recommended."),
            fm("FLT_FREQ", P_FLTFREQ, transform="QUARTERLY->M,3"),
            fm("FLT_DCF", P_FLTDCF, transform="ACT/365->ACT/365.FIXED")
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
    print("\nDone. " + str(len(TRADES)) + " IRS ground truth files created in " + OUT_DIR)


if __name__ == "__main__":
    main()
