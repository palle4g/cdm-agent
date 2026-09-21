"""
v2/src/builders/rune_patches.py

Temporary in-memory fixes for two bugs in rune-runtime 2.2.1
(see https://github.com/finos/rune-python-runtime/issues/37 follow-ups):

  Bug A (deserialize): ComplexTypeMetaDataMixin.deserialize raises
    "Expected either X or dict but got NoneType" when an OPTIONAL
    reference-capable field is None. Fix: None passes through as None.

  Bug B (serialise): ComplexTypeMetaDataMixin.serialise calls
    obj.serialise_meta() without guarding against obj being None or a
    list (e.g. AncillaryParty.partyReference is list-typed). Fix:
    None -> None, list -> serialise each element.

IMPORTANT: this module MUST be imported BEFORE any `import finos...`.
The pydantic validators/serializers capture bound method objects at
model-class creation time (which happens on first finos import), so
patching after that has no effect.

Usage (first lines of any entry point):
    import v2.src.builders.rune_patches  # noqa: F401  (must be first)
    import finos._bundle as b

Delete this module once upstream rune-runtime ships fixes.
"""
import sys

if any(mod == 'finos' or mod.startswith('finos.') for mod in sys.modules):
    raise ImportError(
        "rune_patches must be imported BEFORE finos. "
        "Move `import rune_patches` above any finos import."
    )

import rune.runtime.metadata as _meta

_orig_serialise = _meta.ComplexTypeMetaDataMixin.serialise.__func__
_orig_deserialize = _meta.ComplexTypeMetaDataMixin.deserialize.__func__


def _patched_serialise(cls, obj):
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_patched_serialise(cls, item) for item in obj]
    return _orig_serialise(cls, obj)


def _patched_deserialize(cls, obj, allowed_meta):
    if obj is None:
        return None
    return _orig_deserialize(cls, obj, allowed_meta)


_meta.ComplexTypeMetaDataMixin.serialise = classmethod(_patched_serialise)
_meta.ComplexTypeMetaDataMixin.deserialize = classmethod(_patched_deserialize)

PATCHED = True
