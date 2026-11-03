"""Pure Gemini request adapter for REAL128. No HTTP, credentials, filesystem writes, or private source records.

This adapter constructs at most one FIRST or independent BACK request. The already
verified GitHub Actions transport is owned by a separate audited component.
"""
from pathlib import Path
import importlib.util

_ROOT = Path(__file__).resolve().parent
CAMPAIGN_ID = "GEMINI_NEXTGEN_REAL128_20261103"
ID = CAMPAIGN_ID
BACK_PROFILE = "NX_BACK_38_FREEZE_V1"
FIRST_PROFILES = {
    "K": frozenset({"38SVC", "K_BOUND_31", "K_FEWSHOT_31"}),
    "L": frozenset({"38SVC", "L_BOUND_38", "L_FEWSHOT_38"}),
}


def _load_fixed_module(label, relative):
    path = (_ROOT.parent / relative).resolve()
    if not path.is_file():
        raise RuntimeError("VERIFIED_DEPENDENCY_MISSING")
    spec = importlib.util.spec_from_file_location(label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_nextgen = _load_fixed_module("nextgen_pure_builder", "gemini-nextgen/candidates.py")
_legacy = _load_fixed_module("legacy_service_builder", "gemini-followup/adapter.py")
_cost = _load_fixed_module("historical_usage_calculator", "gemini-real400/baseline.py")
_CONTEXT = ("The wife speaks Lao and the husband speaks Korean. "
            "This is only static role context, not new events or facts.")


def _wrap(request, profile):
    model = request["model"]
    route, body = _nextgen.as_rest_request_parts(request)
    if route != "models/" + model + ":generateContent":
        raise ValueError("INVALID_MODEL_ROUTE")
    return {"model": model, "payload": body, "profile": profile}


def build_first(source, side, profile):
    if side not in FIRST_PROFILES or profile not in FIRST_PROFILES[side]:
        raise ValueError("UNAPPROVED_FIRST_PROFILE")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("EMPTY_SOURCE")
    if profile == "38SVC":
        source_contract = _legacy.build_first(source, side, "38SVC")
        return {"model": source_contract["model"],
                "payload": source_contract["payload"], "profile": profile}
    return _wrap(_nextgen.build_first(profile, source, _CONTEXT), profile)


def build_back(displayed_first, side, profile=BACK_PROFILE):
    if profile != BACK_PROFILE or side not in FIRST_PROFILES:
        raise ValueError("UNAPPROVED_BACK_PROFILE")
    return _wrap(_nextgen.build_independent_back(displayed_first, side), profile)


def inspect(response, *unused):
    try:
        shown = _nextgen.extract_display_once(response)
        return {"status": "SUCCESS", "translation": shown["displayed_text"],
                "warnings": shown["warnings"], "retry_count": 0}
    except (ValueError, TypeError, KeyError, AttributeError) as err:
        return {"status": "FAILED", "translation": None,
                "failure_kind": "NONSTOP_OR_OUTPUT", "error_type": type(err).__name__,
                "retry_count": 0}


def usage_cost(raw, model, wire):
    return _cost.usage_cost(raw, model, wire)