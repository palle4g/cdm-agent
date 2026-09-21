"""
v2/src/builders/cdm_format.py

Converts CDM JSON written in the FLAT @type style (as used by the
FINXIS/FpML reference files) into the NESTED choice-wrapper style the
finos-cdm python models require.

Flat (reference files):
    "rateSpecification": {"@type": "cdm.product.asset.FixedRateSpecification", ...}
Nested (python library):
    "rateSpecification": {"FixedRateSpecification": {...}}

Rule applied recursively:
  - dict has '@type' naming class AC, expected model class is EC:
      * AC is EC or a subclass of EC  -> real polymorphism, leave @type,
        recurse into fields using AC's model_fields
      * otherwise, BFS through EC's choice-wrapper fields (capitalised
        field names) for a path to a field named AC -> nest dict under
        that path (handles Observable -> Index -> InterestRateIndex)
  - all other dicts / lists: recurse using field annotations

Import AFTER rune_patches and finos._bundle.
"""
import copy
import typing
import finos._bundle as _b
from rune.runtime.base_data_class import BaseDataClass


# ── annotation helpers ────────────────────────────────────────────────────────

def _unwrap(annotation):
    """Return the BaseDataClass classes reachable in an annotation."""
    out = []
    origin = typing.get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseDataClass):
            out.append(annotation)
        return out
    for arg in typing.get_args(annotation):
        out.extend(_unwrap(arg))
    return out


def _field_model_class(cls, field_name):
    f = cls.model_fields.get(field_name)
    if f is None:
        return None
    classes = _unwrap(f.annotation)
    return classes[0] if classes else None


def _resolve_type(fq_type: str):
    """'cdm.product.asset.FixedRateSpecification' -> class."""
    simple = fq_type.split('.')[-1]
    mangled = 'finos_' + fq_type.replace('.', '_')
    cls = getattr(_b, simple, None) or getattr(_b, mangled, None)
    if cls is None:
        import importlib
        try:
            mod = importlib.import_module('finos.' + fq_type)
            cls = getattr(mod, simple, None)
        except ImportError:
            cls = None
    return cls


def _choice_path(wrapper_cls, target_name, max_depth=3):
    """BFS: path of capitalised field names from wrapper_cls to target_name."""
    queue = [(wrapper_cls, [])]
    seen = set()
    while queue:
        cls, path = queue.pop(0)
        if cls in seen or len(path) >= max_depth:
            continue
        seen.add(cls)
        for fname in cls.model_fields:
            if not fname[0].isupper():
                continue
            if fname == target_name:
                return path + [fname]
            child = _field_model_class(cls, fname)
            if child is not None:
                queue.append((child, path + [fname]))
    return None


# ── main transform ────────────────────────────────────────────────────────────

def to_nested(data, expected_cls):
    """Transform flat-@type JSON (dict) into nested form for expected_cls."""
    if isinstance(data, list):
        return [to_nested(item, expected_cls) for item in data]
    if not isinstance(data, dict):
        return data

    meta = {k: v for k, v in data.items() if k.startswith('@')}
    body = {k: v for k, v in data.items() if not k.startswith('@')}

    # '@data'-wrapped values carry the real content (and their own @type);
    # transform the wrapped value against the same expected class.
    if isinstance(meta.get('@data'), (dict, list)):
        meta = meta | {'@data': to_nested(meta['@data'], expected_cls)}

    actual_cls = None
    fq = meta.get('@type')
    if fq:
        actual_cls = _resolve_type(fq)

    if actual_cls is not None and expected_cls is not None:
        if actual_cls is expected_cls or issubclass(actual_cls, expected_cls):
            # real polymorphism — keep @type, recurse with the actual class
            inner = {k: to_nested(v, _field_model_class(actual_cls, k)) for k, v in body.items()}
            return meta | inner
        path = _choice_path(expected_cls, actual_cls.__name__.split('_')[-1]) \
            or _choice_path(expected_cls, fq.split('.')[-1])
        if path:
            # nest under choice path; drop @type, keep other meta at inner level
            inner_meta = {k: v for k, v in meta.items() if k != '@type'}
            inner = inner_meta | {k: to_nested(v, _field_model_class(actual_cls, k)) for k, v in body.items()}
            nested = inner
            for fname in reversed(path):
                nested = {fname: nested}
            return nested

    # no @type routing — plain recursion using expected_cls's fields
    cls = actual_cls or expected_cls
    inner = {k: to_nested(v, _field_model_class(cls, k) if cls else None) for k, v in body.items()}
    return meta | inner


def load_reference_file(path):
    """Load a FINXIS-style flat CDM JSON file into the nested dict form."""
    import json
    with open(path) as f:
        raw = json.load(f)
    TradeState = _b.finos_cdm_event_common_TradeState
    out = copy.deepcopy(raw)
    trade_meta = {k: v for k, v in out.items() if k.startswith('@')}
    body = {k: to_nested(v, _field_model_class(TradeState, k)) for k, v in out.items() if not k.startswith('@')}
    return trade_meta | body
