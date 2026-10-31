"""SC1 research adapter: static decoding contract, no HTTP client or API keys.

The transport boundary is supplied by a caller. This module does not authorize
live calls. Its command-line interface can only prepare requests or read responses.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "candidate.json").read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def load_baseline():
    path = ROOT.parent / "haiku-50-steps" / "adapter.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != CONFIG["baseline_adapter_sha256"]:
        raise ValueError("Frozen S47 adapter mismatch")
    spec = importlib.util.spec_from_file_location("frozen_s47_for_sc1", path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    if hashlib.sha256(canonical(module.CANDIDATE)).hexdigest() != CONFIG["baseline_candidate_canonical_sha256"]:
        raise ValueError("Frozen S47 candidate mismatch")
    return module


BASELINE = load_baseline()


def target_language(side, stage):
    if side not in ("K", "L") or stage not in ("first", "back"):
        raise ValueError("side K/L; stage first/back")
    return "Lao" if (side == "K") == (stage == "first") else "Korean"


def build_request(visible_text, side, stage, variant="SC1"):
    """Build from CURRENT visible text only, including for independent BACK.

    Patterns are constants by target language, never derived from private source
    text, extracted facts, source names, translations, or conversation history.
    """
    target = target_language(side, stage)
    if not isinstance(visible_text, str) or not visible_text.strip():
        raise ValueError("Nonempty current visible text required")
    if variant not in ("S47", "SC1"):
        raise ValueError("variant S47/SC1")
    request = copy.deepcopy(BASELINE.build_request(visible_text, side, stage))
    if variant == "SC1":
        field = request["output_config"]["format"]["schema"]["properties"]["translation"]
        field["pattern"] = CONFIG["translation_patterns"][target]
    return request


def inspect_response(response, side, stage):
    """Keep completed visible text exactly. Script findings are advisory only.

    An unexpected pattern violation is observable, never auto-repaired, deleted,
    hidden, retried or converted into a replacement translation.
    """
    target = target_language(side, stage)
    text = BASELINE.extract_translation(response)
    warnings = []
    if re.fullmatch(CONFIG["translation_patterns"][target], text) is None:
        warnings.append("SOURCE_SCRIPT_REMAINS")
    if re.search("[\u0e00-\u0e7f]", text):
        warnings.append("THAI_SCRIPT_REVIEW")
    if re.search("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]", text):
        warnings.append("HAN_SCRIPT_REVIEW")
    return {"translation": text, "warnings": warnings}


class SinglePassSession:
    """One-use FIRST then BACK orchestrator, with an injected transport.

    No built-in live transport, environment-secret lookup, automatic retry,
    fallback, parallel verification, polling, logging, or persistent private data.
    A callback exception or incomplete FIRST ends the session with no BACK.
    A consumed session cannot be replayed, including after an uncertain failure.
    """
    def __init__(self, side, variant="SC1"):
        target_language(side, "first")
        if variant not in ("S47", "SC1"):
            raise ValueError("variant S47/SC1")
        self.side = side
        self.variant = variant
        self.used = False
        self.attempts = 0
        self.measurements = []

    def _call(self, visible, stage, transport):
        request = build_request(visible, self.side, stage, self.variant)
        if self.attempts >= 2:
            raise RuntimeError("Single-pass session consumed")
        self.attempts += 1  # count before transport; uncertain sends are consumed
        started = time.perf_counter()
        try:
            response = transport(request)
            result = inspect_response(response, self.side, stage)
            return result
        finally:
            self.measurements.append({"stage": stage,
                                      "request_elapsed_ms": (time.perf_counter()-started)*1000})

    def run(self, source, transport):
        if self.used:
            raise RuntimeError("Single-pass session cannot be reused")
        self.used = True
        first = self._call(source, "first", transport)
        # FIRST facts/raw response are out of scope here. Only visible text passes.
        back = self._call(first["translation"], "back", transport)
        return {"first": first, "back": back, "attempts": self.attempts,
                "measurements": copy.deepcopy(self.measurements),
                "measurement_scope": "transport callback; not app UI latency"}
