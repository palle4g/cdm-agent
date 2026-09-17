"""
schemas/registry.py
Maps a product type to its schema and metadata.

This is the lookup the agent uses. Adding a product means adding one line
here plus a schema file - no changes to the agent code.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from schemas import government_bond

# Registry: product_type string -> schema module
# To add a product: import its module and add it here.
_REGISTRY = {
    "GovernmentBond": government_bond,
}


def get_schema(product_type):
    """
    Return the SCHEMA string for a product type.
    Raises a clear error if the product type is unknown.
    """
    module = _REGISTRY.get(product_type)
    if module is None:
        raise ValueError(
            "No schema registered for product type '" + str(product_type) + "'. "
            "Registered types: " + ", ".join(_REGISTRY.keys())
        )
    return module.SCHEMA


def get_metadata(product_type):
    """Return the PRODUCT_METADATA dict for a product type."""
    module = _REGISTRY.get(product_type)
    if module is None:
        return None
    return module.PRODUCT_METADATA


def list_products():
    """Return all registered product types."""
    return list(_REGISTRY.keys())


def detect_product_type(normalized_fields):
    """
    Minimal product-type detection.
    Currently returns GovernmentBond if bond-like fields are present,
    else UNKNOWN. Extend this as more products are added.
    """
    field_names_lower = [k.lower() for k in normalized_fields.keys()]

    for product_type, module in _REGISTRY.items():
        hints = module.PRODUCT_METADATA.get("detection_hints", {})
        must_have_any = [h.lower() for h in hints.get("must_have_any", [])]
        excludes = [h.lower() for h in hints.get("excludes", [])]

        has_required = any(h in field_names_lower for h in must_have_any) if must_have_any else True
        has_excluded = any(h in field_names_lower for h in excludes)

        if has_required and not has_excluded:
            return product_type

    return "UNKNOWN"


if __name__ == "__main__":
    print("Registered products: " + ", ".join(list_products()))
    # quick detection test
    test_fields = {"ISIN": "US91282CJL54", "COUPON": "4.25", "MATURE_DT": "2034-08-15"}
    print("Detection test (bond fields): " + detect_product_type(test_fields))
    test_fx = {"BUY_CCY": "EUR", "SELL_CCY": "USD"}
    print("Detection test (FX fields): " + detect_product_type(test_fx))
