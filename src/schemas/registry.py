"""
schemas/registry.py
Maps a product type to its schema and metadata.
Adding a product = add one import + one line in _REGISTRY. No agent code changes.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from schemas import government_bond
from schemas import fx_forward
from schemas import interest_rate_swap

_REGISTRY = {
    "GovernmentBond": government_bond,
    "FXForward": fx_forward,
    "InterestRateSwap": interest_rate_swap,
}


def get_schema(product_type):
    module = _REGISTRY.get(product_type)
    if module is None:
        raise ValueError(
            "No schema registered for product type '" + str(product_type) + "'. "
            "Registered types: " + ", ".join(_REGISTRY.keys())
        )
    return module.SCHEMA


def get_metadata(product_type):
    module = _REGISTRY.get(product_type)
    if module is None:
        return None
    return module.PRODUCT_METADATA


def list_products():
    return list(_REGISTRY.keys())


def detect_product_type(normalized_fields):
    """Score each registered product by hint matches, return the best match."""
    field_names_lower = [k.lower() for k in normalized_fields.keys()]

    best_product = "UNKNOWN"
    best_score = 0

    for product_type, module in _REGISTRY.items():
        hints = module.PRODUCT_METADATA.get("detection_hints", {})
        must_have_any = [h.lower() for h in hints.get("must_have_any", [])]
        strong_signals = [h.lower() for h in hints.get("strong_signals", [])]
        excludes = [h.lower() for h in hints.get("excludes", [])]

        has_required = any(h in field_names_lower for h in must_have_any) if must_have_any else False
        has_excluded = any(h in field_names_lower for h in excludes)

        if not has_required or has_excluded:
            continue

        score = sum(1 for h in must_have_any if h in field_names_lower)
        score += sum(1 for h in strong_signals if h in field_names_lower)

        if score > best_score:
            best_score = score
            best_product = product_type

    return best_product


if __name__ == "__main__":
    print("Registered products: " + ", ".join(list_products()))
    bond_fields = {"ISIN": "US91282CJL54", "COUPON": "4.25", "MATURE_DT": "2034-08-15"}
    print("Bond fields detected as: " + detect_product_type(bond_fields))
    fx_fields = {"BUY_CCY": "EUR", "SELL_CCY": "USD", "BUY_NOTIONAL": "1000000"}
    print("FX fields detected as: " + detect_product_type(fx_fields))
    irs_fields = {"FIX_RATE": "3.85", "FLT_INDEX": "SOFR", "NOTIONAL": "25000000"}
    print("IRS fields detected as: " + detect_product_type(irs_fields))
