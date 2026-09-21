"""
format_detector.py
T-004: Detects the format of legacy trade data and normalizes
it into a standard Python dictionary for the mapping agent.

Supported formats: JSON, CSV/pipe/tab-delimited, Fixed-width, XML/FpML

Fixed: parse_xml now also extracts XML attributes (e.g. currency="USD" on
a <notional> element), not just leaf text content. Attributes are exposed
as "<tag>_<attribute>" fields (e.g. "notional_currency": "USD") alongside
the element's own text value ("notional": "25000000"). Previously these
attributes were silently dropped, which meant data present in the source
never reached the agent at all.
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


def detect_format(raw_text):
    text = raw_text.strip()

    if text.startswith("{") or text.startswith("["):
        try:
            json.loads(text)
            return SourceFormat.JSON
        except json.JSONDecodeError:
            pass

    if text.startswith("<"):
        return SourceFormat.XML

    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) >= 2:
        for delimiter in ["|", ",", "\t"]:
            first_count = lines[0].count(delimiter)
            if first_count > 0:
                second_count = lines[1].count(delimiter)
                if first_count == second_count:
                    return SourceFormat.CSV

    if len(lines) >= 2:
        lengths = [len(l) for l in lines]
        avg_length = sum(lengths) / len(lengths)
        if all(abs(l - avg_length) < 10 for l in lengths):
            return SourceFormat.FIXED_WIDTH

    return SourceFormat.UNKNOWN


def parse_json(raw_text):
    data = json.loads(raw_text.strip())
    if isinstance(data, list):
        data = data[0]
    return {str(k): str(v) for k, v in data.items()}


def parse_csv(raw_text):
    text = raw_text.strip()
    lines = [l for l in text.splitlines() if l.strip()]
    delimiter = ","
    for d in ["|", "\t", ","]:
        if lines[0].count(d) > 0:
            delimiter = d
            break
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return {}
    return {k.strip(): v.strip() for k, v in rows[0].items()}


def parse_xml(raw_text):
    """
    Parse XML / FpML format into a flat key-value dictionary.
    Extracts BOTH leaf node text content AND element attributes.
    An element like <notional currency="USD">25000000</notional> produces:
        "notional": "25000000"
        "notional_currency": "USD"
    """
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(raw_text.strip())
        result = {}

        def extract(element):
            tag = element.tag.split("}")[-1]  # strip namespace
            children = list(element)

            # Attributes on this element become "<tag>_<attribute>" fields,
            # regardless of whether the element also has text or children.
            for attr_name, attr_value in element.attrib.items():
                clean_attr = attr_name.split("}")[-1]  # strip namespace on attr too
                result[tag + "_" + clean_attr] = attr_value

            if not children:
                if element.text and element.text.strip():
                    result[tag] = element.text.strip()
            else:
                for child in children:
                    extract(child)

        extract(root)
        return result
    except Exception as e:
        return {"_parse_error": str(e), "_raw": raw_text}


def parse_fixed_width(raw_text):
    lines = [l for l in raw_text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return {"_raw": raw_text}
    header_line = lines[0]
    data_line = lines[1]
    fields = {}
    for match in re.finditer(r"\S+", header_line):
        field_name = match.group()
        start = match.start()
        fields[field_name] = start
    result = {}
    field_names = list(fields.keys())
    for i, name in enumerate(field_names):
        start = fields[name]
        end = fields[field_names[i + 1]] if i + 1 < len(field_names) else len(data_line)
        value = data_line[start:end].strip()
        if value:
            result[name] = value
    return result


def normalize(raw_text):
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
        return {"_format": fmt.value, "_parse_error": str(e), "_raw": raw_text}


if __name__ == "__main__":
    xml_sample = '<swap><tradeId>IRS-001</tradeId><notional currency="USD">25000000</notional></swap>'
    result = normalize(xml_sample)
    print("XML attribute extraction test:")
    for k, v in result.items():
        print("  " + k + ": " + v)
    assert result.get("notional") == "25000000"
    assert result.get("notional_currency") == "USD"
    print("\nPASS - attribute correctly extracted as notional_currency")
