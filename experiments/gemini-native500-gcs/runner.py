#!/usr/bin/env python3
"""Protected single-pass Gemini research runner using private GCS objects.
No GitHub Issue handshake, no custom envelope crypto, no plaintext GitHub artifacts.
This runner is inert without the explicit activation file and enabled config.
"""
import datetime
import hashlib
import http.client
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUCKET = "lao-translator-src-460077888071"
PREFIX = "research/gemini-model-native500-20261107"
MODELS = {"35": "gemini-3.5-flash-lite", "36": "gemini-3.6-flash"}
CAMPAIGNS = {
    "35": "GEMINI35_MODEL_NATIVE_OPT500_20261107",
    "36": "GEMINI36_MODEL_NATIVE_OPT500_20261107",
}
PATHS = ("KF", "KB", "LF", "LB")
VARIANTS = {"35": {"Q35", "BASE", "N35", "S35", "S35_LOW"},
            "36": {"Q36", "BASE", "R36", "S36", "S36_MINIMAL"}}


def check(assertion, reason):
    if not assertion:
        raise RuntimeError(reason)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(model):
    check(model in MODELS, "INVALID_MODEL")
    directory = ROOT / "experiments" / f"gemini{model}-native500"
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    activation_path = directory / "activation-gcs.json"
    check(activation_path.is_file(), "ACTIVATION_MISSING")
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    check(config.get("campaign") == CAMPAIGNS[model], "CAMPAIGN_MISMATCH")
    check(config.get("model") == MODELS[model], "MODEL_MISMATCH")
    check(config.get("enabled") is True, "PAID_GATE_DISABLED")
    check(type(config.get("prior_actual")) is int, "BAD_PRIOR")
    check(type(config.get("max_new")) is int, "BAD_MAX_NEW")
    check(0 <= config["prior_actual"] < 500, "PRIOR_OUT_OF_BOUNDS")
    check(0 < config["max_new"] <= 500 - config["prior_actual"], "CAP_EXCEEDED")
    check(activation.get("model") == MODELS[model], "ACTIVATION_MODEL_MISMATCH")
    check(activation.get("campaign") == CAMPAIGNS[model], "ACTIVATION_CAMPAIGN_MISMATCH")
    check(activation.get("phase") == config.get("phase"), "PHASE_MISMATCH")
    check(activation.get("max_new") == config["max_new"], "PHASE_CAP_MISMATCH")
    check(activation.get("plan_sha256") == config.get("plan_sha256"), "PLAN_DIGEST_MISMATCH")
    check(activation.get("run_nonce") == config.get("run_nonce"), "RUN_NONCE_MISMATCH")
    check(isinstance(activation.get("run_nonce"), str)
          and 20 <= len(activation["run_nonce"]) <= 100
          and activation["run_nonce"].isascii()
          and all(x.isalnum() or x in "-_" for x in activation["run_nonce"]),
          "BAD_RUN_NONCE")
    check(isinstance(config.get("deadline_epoch"), int)
          and config["deadline_epoch"] > time.time(), "EXPIRED")
    check(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "NO_RERUN")
    check(os.environ.get("GITHUB_REF") == "refs/heads/research/gemini-model-native500-20261107",
          "WRONG_BRANCH")
    check(os.environ.get("GITHUB_ACTOR") == "martin830000-spec", "UNAUTHORIZED_ACTOR")
    check(os.environ.get("GITHUB_EVENT_NAME") == "push", "WRONG_TRIGGER")
    # Plan and result objects are fixed to the campaign/model namespace.
    name = f"{PREFIX}/{model}/plans/{activation['plan_sha256']}.json"
    check(activation.get("plan_object") == name, "UNEXPECTED_GCS_OBJECT_PATH")
    check(len(activation["plan_sha256"]) == 64
          and all(c in "0123456789abcdef" for c in activation["plan_sha256"]),
          "BAD_SHA")
    return directory, config, activation, name


def validate_tasks(tasks, model, config):
    check(isinstance(tasks, list) and len(tasks) == config["max_new"], "TASK_COUNT")
    seen = {}
    for i, item in enumerate(tasks):
        check(isinstance(item, dict), "INVALID_TASK")
        check(item.get("path") in PATHS, "INVALID_PATH")
        check(item.get("variant") in VARIANTS[model], "INVALID_VARIANT")
        slot = item.get("slot")
        check(type(slot) is str and 1 <= len(slot) <= 64
              and slot.isascii() and all(c.isalnum() or c in "-_" for c in slot),
              "INVALID_SLOT")
        check(slot not in seen, "DUPLICATE_SLOT")
        case_id = item.get("case_id")
        check(type(case_id) is str and 1 <= len(case_id) <= 128, "INVALID_CASE")
        if item["path"].endswith("F"):
            check(isinstance(item.get("input"), str) and item["input"].strip(),
                  "EMPTY_FIRST")
            check("from_slot" not in item, "FIRST_HAS_DEPENDENCY")
        else:
            check("input" not in item, "BACK_MUST_DEPEND_ON_FIRST")
            target = item.get("from_slot")
            check(target in seen, "BACK_SOURCE_NOT_READY")
            first = seen[target]
            check(first["path"] == item["path"][0] + "F", "BACK_DIRECTION_MISMATCH")
            check(first["case_id"] == case_id, "BACK_CASE_MISMATCH")
            first_variant = item.get("first_variant", item["variant"])
            check(first["variant"] == first_variant, "BACK_VARIANT_MISMATCH")
            if first_variant != item["variant"]:
                check(
                    model == "36"
                    and first_variant == "BASE"
                    and item["variant"] == "R36",
                    "UNAPPROVED_CROSS_VARIANT"
                )
        seen[slot] = item
    return True


def storage_client():
    # Imported only in paid execution. Auth is WIF short-lived credentials.
    # Bucket security controls (UBLA and Public Access Prevention) were
    # independently verified before provisioning this scoped research identity.
    # Do not request storage.buckets.get or bucket-wide list permissions here.
    from google.cloud import storage
    client = storage.Client(project="gen-lang-client-0422436907")
    return client.bucket(BUCKET)


def immutable_write(bucket, path, payload):
    from google.api_core.exceptions import PreconditionFailed, Conflict
    blob = bucket.blob(path)
    try:
        blob.upload_from_string(
            dump(payload), content_type="application/json",
            if_generation_match=0, timeout=30,
        )
    except (PreconditionFailed, Conflict):
        raise RuntimeError("OBJECT_ALREADY_EXISTS_ABORT") from None


def worker_call(proc, request):
    proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    check(bool(line), "WORKER_CLOSED")
    obj = json.loads(line)
    check(obj.get("ok") is True, "WORKER_ERROR")
    return obj["value"]


def gemini_request(model, payload, api_key):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com", timeout=45)
    start = time.perf_counter()
    try:
        conn.request("POST", f"/v1beta/models/{MODELS[model]}:generateContent",
                     body=body, headers={"x-goog-api-key": api_key,
                                         "content-type": "application/json"})
        response = conn.getresponse()
        raw = response.read()
        latency = time.perf_counter() - start
        check(len(raw) <= 4_000_000, "PROVIDER_RESPONSE_TOO_LARGE")
        parsed = json.loads(raw)
        return response.status, parsed, latency
    finally:
        conn.close()


def execute(model):
    directory, config, activation, name = load(model)
    check(os.environ.get("GEMINI_API_KEY"), "GEMINI_SECRET_MISSING")
    bucket = storage_client()
    plan_raw = bucket.blob(name).download_as_bytes(timeout=30)
    check(digest(plan_raw) == activation["plan_sha256"], "PLAN_SHA_MISMATCH")
    plan = json.loads(plan_raw)
    check(plan.get("campaign") == CAMPAIGNS[model], "PLAN_CAMPAIGN_MISMATCH")
    check(plan.get("model") == MODELS[model], "PLAN_MODEL_MISMATCH")
    check(plan.get("phase") == config["phase"], "PLAN_PHASE_MISMATCH")
    check(plan.get("prior_actual") == config["prior_actual"], "PLAN_PRIOR_MISMATCH")
    prior_actual=0
    for previous_sha in config.get("prior_plans", []):
        previous=json.loads(bucket.blob(f"{PREFIX}/{model}/results/{previous_sha}/RUN_FINISHED.json").download_as_bytes(timeout=30))
        check(previous["status"] in ("DONE", "DONE_WITH_FAILURES"), "PRIOR_NOT_FINISHED")
        prior_actual+=previous["attempted"]
    check(prior_actual==config["prior_actual"], "REMOTE_LEDGER_PRIOR_MISMATCH")
    tasks = plan.get("tasks")
    validate_tasks(tasks, model, config)

    result_base = f"{PREFIX}/{model}/results/{activation['plan_sha256']}"
    # If the run was started once, no rerun may ever send the same requests.
    immutable_write(bucket, f"{result_base}/RUN_STARTED.json", {
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_sha": os.environ.get("GITHUB_SHA"),
        "campaign": config["campaign"],
        "reserved_slots": len(tasks),
        "prior_actual": config["prior_actual"],
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })

    proc = subprocess.Popen(["node", str(directory / "worker.cjs")],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    attempted = 0
    succeeded = 0
    failed = 0
    skipped = 0
    prior = {}
    stopped_reason = None
    try:
        for t in tasks:
            slot = t["slot"]
            key = f"{result_base}/slots/{len(prior)+1:04d}-{slot}.json"
            if "from_slot" in t:
                forward = prior[t["from_slot"]]
                if forward.get("status") != "SUCCESS":
                    skipped += 1
                    immutable_write(bucket, key, {"slot": slot, "status": "SKIPPED_DEPENDENCY"})
                    prior[slot] = {"status": "SKIPPED_DEPENDENCY"}
                    continue
                actual_input = forward["displayed"]
            else:
                actual_input = t["input"]

            built = worker_call(proc, {
                "mode": "build", "path": t["path"],
                "variant": t["variant"], "input": actual_input,
            })
            check(built.get("model") == MODELS[model], "WRONG_REQUEST_MODEL")
            check(built["payload"]["contents"] ==
                  [{"role": "user", "parts": [{"text": actual_input}]}],
                  "BACK_INDEPENDENCE_OR_SOURCE_FAILURE")
            # Reserve a GCS journal entry BEFORE the request; even uncertain
            # network outcomes are counted conservatively as attempted.
            attempted += 1
            immutable_write(bucket, f"{result_base}/journal/{attempted:04d}.json", {
                "slot": slot,
                "request_sha256": digest(dump(built["payload"])),
                "ordinal": config["prior_actual"] + attempted,
            })
            row = {"slot": slot, "model": MODELS[model], "case_id": t["case_id"],
                   "path": t["path"], "variant": t["variant"], "input": actual_input,
                   "request": built, "status": "UNKNOWN_AFTER_SEND",
                   "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "input_sha256": digest(actual_input.encode("utf-8")), "run_id": os.environ.get("GITHUB_RUN_ID")}
            try:
                status, body, latency = gemini_request(
                    model, built["payload"], os.environ["GEMINI_API_KEY"]
                )
                row.update(http_status=status, response=body, elapsed_s=latency)
                if status == 200 and body.get("modelVersion", "").startswith(MODELS[model]):
                    info = worker_call(proc, {
                        "mode": "inspect", "path": t["path"], "variant": t["variant"],
                        "raw": body, "input": actual_input,
                    })
                    row["inspection"] = info
                    row["status"] = info.get("status", "FAILED")
                    row["displayed"] = info.get("displayed")
                else:
                    row["status"] = "PROVIDER_ERROR"
            except Exception as exc:
                row["status"] = "UNCONFIRMED_REQUEST_ERROR"
                row["error_type"] = type(exc).__name__
            row["completed_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
            # Private full output is stored in GCS only, never GitHub Actions artifacts.
            immutable_write(bucket, key, row)
            prior[slot] = {"status": row["status"], "displayed": row.get("displayed")}
            if row["status"] == "SUCCESS":
                succeeded += 1
            else:
                failed += 1
                # A translation/output failure is valid research evidence:
                # keep processing independent cases, while its own BACK is
                # skipped by the dependency check above. Never retry.
                # Transport/provider failures stop the campaign immediately.
                if row["status"] in ("PROVIDER_ERROR", "UNCONFIRMED_REQUEST_ERROR"):
                    stopped_reason = row["status"]
                    break
    finally:
        proc.terminate()
    immutable_write(bucket, f"{result_base}/RUN_FINISHED.json", {
        "campaign": CAMPAIGNS[model], "model": MODELS[model],
        "attempted": attempted, "success": succeeded, "failed": failed,
        "skipped": skipped, "remaining_in_reserved_plan": len(tasks)-len(prior),
        "status": "STOPPED" if stopped_reason else ("DONE_WITH_FAILURES" if failed else "DONE"),
        "reason": stopped_reason,
    })
    # Never reveal source or translations in standard Actions logs.
    print(json.dumps({"model": model, "attempted": attempted, "success": succeeded,
                      "failed": failed, "skipped": skipped,
                      "status": "STOPPED" if stopped_reason else "DONE"}))


if __name__ == "__main__":
    check(len(sys.argv) == 3 and sys.argv[1] == "execute", "ARGS")
    execute(sys.argv[2])

