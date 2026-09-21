"""
mapping_agent.py
T-005: The CDM mapping agent (product-agnostic).
Loads the schema for the detected product type from the registry.
Supports optional previous_errors for validation-retry reuse by agent_loop.py -
single source of truth for the actual API call and parsing logic.
"""

import json
import os
from dotenv import load_dotenv
import anthropic
import sys

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ingestion.format_detector import normalize
from schemas.registry import get_schema, detect_product_type
from config import (
    AGENT_MODEL, AGENT_MODEL_COMPLEX, AGENT_MAX_TOKENS,
    DEFAULT_PRODUCT_TYPE, GROUND_TRUTH_DIR
)

OUTPUT_CONTRACT = """

STRICT OUTPUT CONTRACT - your response MUST be a single JSON object whose
TOP-LEVEL keys are EXACTLY these, spelled exactly this way:
  "cdmTrade"          (object)
  "fieldMapping"      (array)   <- singular, not "fieldMappings"
  "mappingNotes"      (array)
  "missingFields"     (array)
Do NOT wrap these in any other key such as "cdmMappingOutput", "result",
"output", or "data". Start your response with { and the first key must be
"cdmTrade".
"""


def _find_key_recursive(obj, target_keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in target_keys:
                return v
        for v in obj.values():
            found = _find_key_recursive(v, target_keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key_recursive(item, target_keys)
            if found is not None:
                return found
    return None


def _normalize_result(parsed):
    """Extract cdmTrade + fieldMapping regardless of what wrapper key the model used."""
    if isinstance(parsed, dict) and ("cdmTrade" in parsed or "fieldMapping" in parsed or "fieldMappings" in parsed):
        result = dict(parsed)
    else:
        result = {}
        ct = _find_key_recursive(parsed, {"cdmTrade", "cdm_trade", "CDMTrade", "trade"})
        fm = _find_key_recursive(parsed, {"fieldMapping", "fieldMappings", "field_mapping", "field_mappings"})
        notes = _find_key_recursive(parsed, {"mappingNotes", "mapping_notes", "notes"})
        missing = _find_key_recursive(parsed, {"missingFields", "missing_fields"})
        if ct is not None:
            result["cdmTrade"] = ct
        if fm is not None:
            result["fieldMapping"] = fm
        if notes is not None:
            result["mappingNotes"] = notes
        if missing is not None:
            result["missingFields"] = missing

    if "fieldMappings" in result and "fieldMapping" not in result:
        result["fieldMapping"] = result.pop("fieldMappings")

    if "cdmTrade" not in result and isinstance(parsed, dict) and "tradeIdentifier" in parsed:
        result["cdmTrade"] = parsed

    if "fieldMapping" not in result:
        result["fieldMapping"] = []

    return result


def map_trade(normalized_fields, product_type=None, use_complex_model=False, previous_errors=None):
    """
    Map a normalized trade dict to CDM.

    Args:
        normalized_fields: output from format_detector.normalize()
        product_type: force a product type, or None to auto-detect
        use_complex_model: use the complex/escalation model instead of standard
        previous_errors: list of validation error strings from a prior attempt -
            when given, the agent is asked to correct these specific issues.
            This is what makes agent_loop.py's retry loop work through this
            same function instead of duplicating the API call logic.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = AGENT_MODEL_COMPLEX if use_complex_model else AGENT_MODEL

    if product_type is None:
        product_type = detect_product_type(normalized_fields)
        if product_type == "UNKNOWN":
            product_type = DEFAULT_PRODUCT_TYPE
    if product_type == "UNKNOWN":
        return {"error": "Could not detect product type. Flag for human review.", "productTypeDetected": "UNKNOWN"}

    try:
        schema = get_schema(product_type) + OUTPUT_CONTRACT
    except ValueError as e:
        return {"error": str(e), "productTypeDetected": product_type}

    fields_text = json.dumps(normalized_fields, indent=2)

    has_currency = any(k.lower() in ["currency", "ccy", "bond_ccy", "settle_ccy"] for k in normalized_fields.keys())
    has_day_count = any(k.lower() in ["day_count", "dcf", "day_cnt", "basis", "day_count_basis", "fix_dcf", "float_dcf"] for k in normalized_fields.keys())
    reminders = []
    if not has_currency:
        reminders.append("No currency field in source - apply the currency inference rule with a reason")
    if not has_day_count:
        reminders.append("No day count field in source - apply the day count inference rule with a reason")
    reminder_text = ("\n\nREMINDERS:\n" + "\n".join(["- " + r for r in reminders])) if reminders else ""

    error_text = ""
    if previous_errors:
        error_text = "\n\nVALIDATION ERRORS FROM PREVIOUS ATTEMPT - fix these specifically:\n" + \
                     "\n".join(["- " + e for e in previous_errors])

    user_message = (
        "Map this legacy trade data to CDM format.\n\n"
        "SOURCE DATA:\n" + fields_text + reminder_text + error_text +
        "\n\nReturn a single JSON object with top-level keys cdmTrade, fieldMapping, "
        "mappingNotes, missingFields. Start with { and first key cdmTrade. No markdown."
    )

    response = client.messages.create(
        model=model,
        max_tokens=AGENT_MAX_TOKENS,
        system=schema,
        messages=[{"role": "user", "content": user_message}]
    )

    raw_text = response.content[0].text.strip()
    if "```" in raw_text:
        for part in raw_text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw_text = part
                break
    raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return {"error": str(e), "rawResponse": raw_text[:500]}

    result = _normalize_result(parsed)
    result["_agentModel"] = model
    result["_sourceFormat"] = normalized_fields.get("_format", "UNKNOWN")
    result["_productType"] = product_type
    return result


def score_against_ground_truth(agent_output, ground_truth_path):
    """Compare agent output against ground truth using best-match scoring."""
    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)

    gt_mappings = {
        m["source_field"]: m["cdm_path"]
        for m in ground_truth.get("_field_mapping", [])
        if "NOT MAPPED" not in m["cdm_path"]
    }

    agent_mappings = {}
    for m in agent_output.get("fieldMapping", []):
        src = m.get("sourceField", "")
        cdm = m.get("cdmPath", "")
        if "UNMAPPED" not in cdm and "NOT MAPPED" not in cdm:
            agent_mappings.setdefault(src, []).append(cdm)

    correct = 0
    total = len(gt_mappings)
    comparison = []
    for source_field, gt_cdm_path in gt_mappings.items():
        agent_paths = agent_mappings.get(source_field, ["MISSING"])
        best_match = "MISSING"
        is_correct = False
        for path in agent_paths:
            if path == gt_cdm_path or path.startswith(gt_cdm_path) or gt_cdm_path.startswith(path):
                best_match = path
                is_correct = True
                break
        if not is_correct and agent_paths:
            best_match = agent_paths[0]
        if is_correct:
            correct += 1
        comparison.append({
            "sourceField": source_field, "groundTruth": gt_cdm_path,
            "agentOutput": best_match, "correct": is_correct
        })

    accuracy = round((correct / total * 100), 1) if total > 0 else 0
    return {"accuracy": str(accuracy) + "%", "correct": correct, "total": total, "comparison": comparison}


if __name__ == "__main__":
    from config import print_config
    print_config()
    gt = json.load(open(os.path.join(GROUND_TRUTH_DIR, "government_bond", "gb_001_pipedelimited.json")))
    normalized = normalize(gt["_source"]["raw"])
    result = map_trade(normalized, product_type="GovernmentBond")
    print("\nKeys: " + str(list(result.keys())))
    print("fieldMapping count: " + str(len(result.get("fieldMapping", []))))
