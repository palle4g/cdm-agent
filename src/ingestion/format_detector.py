"""
format_detector.py
T-004: Detects the format of legacy trade data and normalizes
it into a standard Python dictionary for the mapping agent.

Supported formats:
- JSON
- CSV / TSV / pipe-delimited
- Fixed-width (mainframe)
- XML / FpML
"""

import json
import csv
import io
import re
from enum import Enum


class SourceFormat(Enum):
    JSON = "JSON"
    CSV = "CSV"
    XML = "XML"
    FIXED_WIDTH = "FIXED_WIDTH"
    UNKNOWN = "UNKNOWN"


def detect_format(raw_text: str) -> SourceFormat:
    """
    Detect the format of raw legacy trade data.
    Returns a SourceFormat enum value.
    """
    text = raw_text.strip()

    # JSON — starts with { or [
    if text.startswith("{") or text.startswith("["):
        try:
            json.loads(text)
            return SourceFormat.JSON
        except json.JSONDecodeError:
            pass

    # XML / FpML — starts with < 
    if text.startswith("<"):
        return SourceFormat.XML

    # CSV / pipe-delimited / tab-delimited
    # Look for consistent delimiters across lines
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) >= 2:
        for delimiter in ["|", ",", "\t"]:
            first_count = lines[0].count(delimiter)
            if first_count > 0:
                # Check second line has same number of delimiters
                second_count = lines[1].count(delimiter)
                if first_count == second_count:
                    return SourceFormat.CSV

    # Fixed-width — lines of consistent length with no clear delimiter
    if len(lines) >= 2:
        lengths = [len(l) for l in lines]
        avg_length = sum(lengths) / len(lengths)
        # If lines are all within 10 chars of each other, likely fixed-width
        if all(abs(l - avg_length) < 10 for l in lengths):
            return SourceFormat.FIXED_WIDTH

    return SourceFormat.UNKNOWN


def parse_json(raw_text: str) -> dict:
    """Parse JSON format into a flat key-value dictionary."""
    data = json.loads(raw_text.strip())
    # Flatten one level if nested
    if isinstance(data, list):
        data = data[0]
    return {str(k): str(v) for k, v in data.items()}


def parse_csv(raw_text: str) -> dict:
    """
    Parse CSV / pipe-delimited / tab-delimited format.
    Assumes first row is headers, second row is values.
    """
    text = raw_text.strip()
    lines = [l for l in text.splitlines() if l.strip()]

    # Detect delimiter
    delimiter = ","
    for d in ["|", "\t", ","]:
        if lines[0].count(d) > 0:
            delimiter = d
            break

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return {}

    # Return first data row as flat dict, strip whitespace from keys/values
    return {k.strip(): v.strip() for k, v in rows[0].items()}


def parse_xml(raw_text: str) -> dict:
    """
    Parse XML / FpML format into a flat key-value dictionary.
    Extracts leaf node values (nodes with no children).
    """
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(raw_text.strip())
        result = {}

        def extract_leaves(element, prefix=""):
            tag = element.tag.split("}")[-1]  # strip namespace
            path = f"{prefix}.{tag}" if prefix else tag
            children = list(element)
            if not children:
                # Leaf node — has a value
                if element.text and element.text.strip():
                    result[tag] = element.text.strip()
            else:
                for child in children:
                    extract_leaves(child, path)

        extract_leaves(root)
        return result
    except Exception as e:
        return {"_parse_error": str(e), "_raw": raw_text}


def parse_fixed_width(raw_text: str) -> dict:
    """
    Parse fixed-width mainframe format.
    Uses header row to identify field names and their column positions.
    """
    lines = [l for l in raw_text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return {"_raw": raw_text}

    header_line = lines[0]
    data_line = lines[1]

    # Find column positions from header
    fields = {}
    for match in re.finditer(r"\S+", header_line):
        field_name = match.group()
        start = match.start()
        fields[field_name] = start

    # Extract values by column position
    result = {}
    field_names = list(fields.keys())
    for i, name in enumerate(field_names):
        start = fields[name]
        # End is the start of the next field, or end of line
        end = fields[field_names[i + 1]] if i + 1 < len(field_names) else len(data_line)
        value = data_line[start:end].strip()
        if value:
            result[name] = value

    return result


def normalize(raw_text: str) -> dict:
    """
    Main entry point. Takes any raw legacy trade text,
    detects its format, parses it, and returns a clean
    key-value dictionary ready for the mapping agent.

    Returns a dict with:
    - All trade fields as key-value strings
    - '_format': the detected source format
    - '_parse_error': if something went wrong
    """
    fmt = detect_format(raw_text)

    try:
        if fmt == SourceFormat.JSON:
            fields = parse_json(raw_text)
        elif fmt == SourceFormat.CSV:
            fields = parse_csv(raw_text)
        elif fmt == SourceFormat.XML:
            fields = parse_xml(raw_text)
        elif fmt == SourceFormat.FIXED_WIDTH:
            fields = parse_fixed_width(raw_text)
        else:
            fields = {"_raw": raw_text}

        fields["_format"] = fmt.value
        return fields

    except Exception as e:
        return {
            "_format": fmt.value,
            "_parse_error": str(e),
            "_raw": raw_text
        }


# -------------------------------------------------------
# Quick test — run this file directly to verify it works
# -------------------------------------------------------
if __name__ == "__main__":

    # Sample A — pipe-delimited
    sample_a = """TRADE_NUM|SEC_ID|ISIN|SEC_DESC|SIDE|QTY|PRICE|YIELD|ACCRUED_INT|SETTLE_AMT|CPTY_CODE|TRADE_DT|SETTLE_DT|MATURE_DT|COUPON|FREQ|DAY_COUNT
TB-20260914-001|UST-10Y|US91282CJL54|US TREASURY 4.25% 08/2034|BUY|10000000|98.750|4.42|21250.00|9896250.00|JPMORGAN|2026-09-14|2026-09-16|2034-08-15|4.25|SEMI|ACT/ACT"""

    # Sample B — JSON
    sample_b = """{
  "deal_id": "BOND-2026-8821",
  "security": "US91282CJL54",
  "transaction_type": "PURCHASE",
  "face_value": 5000000,
  "currency": "USD",
  "coupon_rate": 4.25,
  "payment_frequency": "SEMI-ANNUAL",
  "day_count_basis": "ACT/ACT ICMA",
  "trade_date": "2026-09-14",
  "settlement_date": "2026-09-16",
  "maturity_date": "2034-08-15",
  "counterparty": "GOLDMAN SACHS",
  "counterparty_lei": "784F5XWPLTWKTBV3E584"
}"""

    # Sample C — fixed-width
    sample_c = """TRADE_ID  ISIN          SIDE QTY        PRICE    COUPON FREQ MAT_DATE   CPTY
TB0091234 US91282CJL54  B    10000000   98.7500  4.2500 S    20340815   BARC"""

    print("=" * 60)
    print("FORMAT DETECTOR — T-004 Test")
    print("=" * 60)

    for label, sample in [("A (pipe-delimited)", sample_a),
                           ("B (JSON)", sample_b),
                           ("C (fixed-width)", sample_c)]:
        print(f"\nSample {label}")
        print("-" * 40)
        result = normalize(sample)
        for k, v in result.items():
            print(f"  {k}: {v}")