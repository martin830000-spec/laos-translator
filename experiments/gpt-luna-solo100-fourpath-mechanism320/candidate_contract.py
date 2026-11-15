"""Offline TEST request builder. This module never sends a generation request.

Use only with independently verified, finalized private evidence. No API client,
credentials, retry, fallback, chain executor, or campaign-unlock function exists.
"""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re


CAMPAIGN = "GPT_LUNA_SOLO100_FOURPATH_MECHANISM320_20261115"
MODEL = "gpt-6-luna"
PATHS = ("KF", "KB", "LF", "LB")
DIRECTIONS = {"K2L": ("KF", "KB"), "L2K": ("LF", "LB")}
PROMPT_PATHS = {
    "BASE": {"KF", "KB", "LF", "LB"},
    "HLEX": {"KF", "LF"},
    "HPROP": {"KF", "LF"},
    "HBACK": {"KB", "LB"},
}


class ContractError(ValueError):
    """Invalid or incomplete evidence; messages contain no conversation text."""


def _require(condition, code):
    if not condition:
        raise ContractError(code)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value, code):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), code)
    return value


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def _read_json(path):
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("INVALID_JSON_FILE") from error
    _require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return raw, value


@dataclass(frozen=True, repr=False, slots=True, init=False)
class CandidateContract:
    """Verified immutable prompt snapshot; inputs are never saved in the object.

    Construct through ``load``. Directions describe the original FIRST direction:
    K2L means Korean FIRST to Lao and Lao BACK to Korean; L2K is the reverse.
    """

    _selected_prompts: tuple = field(repr=False)
    _configuration: tuple = field(repr=False)
    _evidence_hashes: tuple = field(repr=False)

    def __init__(self):
        raise ContractError("USE_VERIFIED_LOAD")

    def __repr__(self):
        return "CandidateContract(TEST_ONLY, offline=True, enabled=False, max_new=0)"

    @classmethod
    def load(cls, prompts_path, selection_path, controller_path, *, expected_selection_sha256):
        """Validate private files against an externally verified selection hash.

        File hashes refer to exact bytes, while prompt hashes refer to the exact
        decoded string encoded as UTF-8. Missing/pending selection is rejected.
        The close controller is evidence of no remaining execution authorization.
        """
        expected = _digest(expected_selection_sha256, "EXPECTED_SELECTION_SHA_REQUIRED")
        selection_raw, selection = _read_json(selection_path)
        _require(_sha(selection_raw) == expected, "SELECTION_FILE_SHA_MISMATCH")
        _require(selection.get("schema_version") == 1 and type(selection.get("schema_version")) is int,
                 "SELECTION_SCHEMA_VERSION")
        _require(selection.get("campaign") == CAMPAIGN, "SELECTION_CAMPAIGN")
        _require(selection.get("artifact_status") == "FINALIZED_TEST_CONTRACT", "SELECTION_NOT_FINALIZED")
        _require(selection.get("purpose") == "TEST_ONLY_OFFLINE_REQUEST_BUILDING", "SELECTION_PURPOSE")
        config = selection.get("selected_configuration")
        hashes = selection.get("prompt_sha256")
        _require(isinstance(config, dict) and set(config) == set(PATHS), "CONFIG_FOUR_PATHS_REQUIRED")
        _require(isinstance(hashes, dict) and set(hashes) == set(PATHS), "PROMPT_SHA_FOUR_PATHS_REQUIRED")
        prompt_file_sha = _digest(selection.get("prompt_file_sha256"), "PROMPT_FILE_SHA_REQUIRED")
        controller_file_sha = _digest(selection.get("controller_file_sha256"), "CONTROLLER_FILE_SHA_REQUIRED")

        prompts_raw, prompts = _read_json(prompts_path)
        _require(_sha(prompts_raw) == prompt_file_sha, "PROMPT_FILE_SHA_MISMATCH")
        _require(set(prompts) == set(PROMPT_PATHS), "FROZEN_PROMPT_IDS_REQUIRED")
        for prompt_id, routes in PROMPT_PATHS.items():
            route_prompts = prompts[prompt_id]
            _require(isinstance(route_prompts, dict) and set(route_prompts) == routes,
                     "FROZEN_PROMPT_ROUTES_INVALID")
            _require(all(isinstance(item, str) and item.strip() for item in route_prompts.values()),
                     "FROZEN_PROMPT_TEXT_INVALID")

        selected = []
        for route in PATHS:
            prompt_id = config[route]
            _require(isinstance(prompt_id, str) and prompt_id in PROMPT_PATHS
                     and route in PROMPT_PATHS[prompt_id], "SELECTED_PROMPT_ROUTE_INVALID")
            text = prompts[prompt_id][route]
            _require(_sha(text.encode("utf-8")) == _digest(hashes[route], "PROMPT_SHA_REQUIRED"),
                     "SELECTED_PROMPT_SHA_MISMATCH")
            selected.append((route, text))

        controller_raw, controller = _read_json(controller_path)
        _require(_sha(controller_raw) == controller_file_sha, "CONTROLLER_FILE_SHA_MISMATCH")
        _require(controller.get("campaign") == CAMPAIGN, "CONTROLLER_CAMPAIGN")
        _require(controller.get("status") == "CLOSED_LOCKED", "CONTROLLER_NOT_CLOSED")
        _require(controller.get("enabled") is False, "CONTROLLER_ENABLED")
        _require(type(controller.get("max_new")) is int and controller["max_new"] == 0,
                 "CONTROLLER_NEW_BUDGET_NOT_ZERO")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_selected_prompts", tuple(selected))
        object.__setattr__(instance, "_configuration", tuple((route, config[route]) for route in PATHS))
        object.__setattr__(instance, "_evidence_hashes",
                           (("selection_sha256", expected), ("prompt_file_sha256", prompt_file_sha),
                            ("controller_file_sha256", controller_file_sha)))
        return instance

    @property
    def selected_configuration(self):
        return dict(self._configuration)

    @property
    def evidence_hashes(self):
        return dict(self._evidence_hashes)

    @property
    def execution_policy(self):
        """Local policy metadata; these fields are not sent as API parameters."""
        return {"test_only": True, "network_enabled": False, "enabled": False,
                "max_new": 0, "automatic_retries": 0, "fallback_models": [],
                "hidden_generation_calls": 0, "service_apply_authorized": False}

    def _build(self, text, direction, step):
        _require(isinstance(direction, str) and direction in DIRECTIONS, "DIRECTION_K2L_OR_L2K_REQUIRED")
        _require(isinstance(text, str) and text.strip(), "NONEMPTY_TEXT_REQUIRED")
        route = DIRECTIONS[direction][step]
        return {"model": MODEL, "reasoning": {"effort": "none"},
                "instructions": dict(self._selected_prompts)[route], "input": text,
                "stream": True, "store": False, "max_output_tokens": 4096,
                "service_tier": "fast"}

    def build_first(self, text: str, direction: str) -> dict:
        """Return one FIRST payload; no transmission, normalization, or chaining."""
        return self._build(text, direction, 0)

    def build_back(self, actual_first: str, direction: str) -> dict:
        """Return one BACK payload using only the exact actual FIRST string.

        No source, source summary, expected answer, or evaluation argument exists.
        The caller must use a successful, complete, verified actual FIRST output.
        This string-only builder cannot verify the external output provenance.
        """
        return self._build(actual_first, direction, 1)
