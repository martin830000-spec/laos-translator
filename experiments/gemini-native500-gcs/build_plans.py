#!/usr/bin/env python3
"""Build private GCS task plans from the verified R2 samples; never calls Gemini."""
import argparse
import hashlib
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "experiments" / "gemini-native500-gcs" / "runner.py"
BUCKET = "lao-translator-src-460077888071"
PREFIX = "research/gemini-model-native500-20261107"
SAMPLE_DIR = "GEMINI_NATIVE500_SAMPLES_20261107_R2"
EXPECTED_MANIFEST_SHA = "221f446226e7d79a69f1f3aad65aabcfddf965e6f62e53818eeeb3dcbe57b533"
EXPECTED_SAMPLE_SHA = {
    "development_baseline.json": "70add842393768eabeb2695ffbbd37507923ddf1ee77d3725e98344fc38b8169",
    "ab_candidates.json": "0159f00217fded127bd3a656cf2fca1e9219b352487aa0a994fcdb4a33f3a109",
    "final_holdout.json": "ad1ae9a6c530bd4c5458e028b6056315c12f306b96e5c037371376e599ce15bb",
}
MODELS = {
    "35": ("gemini-3.5-flash-lite", "GEMINI35_MODEL_NATIVE_OPT500_20261107"),
    "36": ("gemini-3.6-flash", "GEMINI36_MODEL_NATIVE_OPT500_20261107"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_sample(directory: Path, name: str, manifest: dict) -> list:
    raw = (directory / name).read_bytes()
    if sha(raw) != EXPECTED_SAMPLE_SHA[name]:
        raise RuntimeError(f"SAMPLE_SHA_MISMATCH:{name}")
    rows = json.loads(raw)
    info = manifest["sets"][name]
    if len(rows) != info["records"]:
        raise RuntimeError(f"SAMPLE_COUNT_MISMATCH:{name}")
    return rows


def stable_key(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def choose_development(rows: list) -> list:
    clusters = {}
    for row in rows:
        clusters.setdefault(str(row["cluster"]), {})[row["side"]] = row
    common = [
        cluster for cluster, sides in clusters.items()
        if "K" in sides and "L" in sides
    ]
    common.sort(key=lambda c: stable_key("dev20:" + c))
    if len(common) < 20:
        raise RuntimeError("NOT_ENOUGH_DEVELOPMENT_CLUSTERS")
    selected = []
    for cluster in common[:20]:
        selected.extend([clusters[cluster]["K"], clusters[cluster]["L"]])
    if len(selected) != 40:
        raise RuntimeError("DEVELOPMENT_SELECTION_COUNT")
    return selected


def choose_ab(rows: list) -> list:
    selected = []
    for side in ("K", "L"):
        side_rows = [row for row in rows if row["side"] == side]
        side_rows.sort(key=lambda row: stable_key("ab50:" + side + ":" + str(row["id"])))
        selected.extend(side_rows[:25])
    if len(selected) != 50:
        raise RuntimeError("AB_SELECTION_COUNT")
    counts = {}
    for row in selected:
        cluster = str(row["cluster"])
        counts[cluster] = counts.get(cluster, 0) + 1
    if max(counts.values()) > 3:
        raise RuntimeError("AB_CLUSTER_CAP")
    return selected


def make_slot(prefix: str, index: int, side: str, variant: str, suffix: str) -> str:
    slot = f"{prefix}-{index:03d}-{side.lower()}-{variant.lower()}-{suffix}"
    if len(slot) > 64:
        raise RuntimeError("SLOT_TOO_LONG")
    return slot


def add_pair(tasks: list, row: dict, index: int, variant: str, prefix: str) -> str:
    side = row["side"]
    first_path = "KF" if side == "K" else "LF"
    back_path = "KB" if side == "K" else "LB"
    first_slot = make_slot(prefix, index, side, variant, "f")
    back_slot = make_slot(prefix, index, side, variant, "b")
    tasks.append({
        "slot": first_slot,
        "case_id": str(row["id"]),
        "path": first_path,
        "variant": variant,
        "input": row["source"],
        "sample_cluster": str(row["cluster"]),
    })
    tasks.append({
        "slot": back_slot,
        "case_id": str(row["id"]),
        "path": back_path,
        "variant": variant,
        "from_slot": first_slot,
        "sample_cluster": str(row["cluster"]),
    })
    return first_slot


def build_development(model: str, rows: list, manifest_sha: str) -> dict:
    tasks = []
    for i, row in enumerate(rows, 1):
        add_pair(tasks, row, i, "BASE", "dev")
    return make_plan(model, "DEVELOPMENT_BASELINE", 0, tasks, rows, manifest_sha)


def build_ab_35(rows: list, manifest_sha: str, prior_actual: int = 80) -> dict:
    tasks = []
    for i, row in enumerate(rows, 1):
        for variant in ("BASE", "N35", "S35"):
            add_pair(tasks, row, i, variant, "ab")
    return make_plan("35", "AB_COMPARE", prior_actual, tasks, rows, manifest_sha)


def build_ab_36(rows: list, manifest_sha: str, prior_actual: int = 80) -> dict:
    tasks = []
    for i, row in enumerate(rows, 1):
        base_first = add_pair(tasks, row, i, "BASE", "ab")
        side = row["side"]
        back_path = "KB" if side == "K" else "LB"
        r36_slot = make_slot("ab", i, side, "R36", "b")
        tasks.append({
            "slot": r36_slot,
            "case_id": str(row["id"]),
            "path": back_path,
            "variant": "R36",
            "first_variant": "BASE",
            "from_slot": base_first,
            "sample_cluster": str(row["cluster"]),
        })
        add_pair(tasks, row, i, "S36", "ab")
    return make_plan("36", "AB_COMPARE", prior_actual, tasks, rows, manifest_sha)


def make_plan(model: str, phase: str, prior_actual: int, tasks: list,
              rows: list, manifest_sha: str) -> dict:
    model_id, campaign = MODELS[model]
    if len(tasks) + prior_actual > 500:
        raise RuntimeError(f"MODEL_CAP_EXCEEDED:{model}")
    # Ensure every BACK is dependent and no original source is embedded in BACK tasks.
    for task in tasks:
        if task["path"].endswith("B"):
            if "input" in task or "from_slot" not in task:
                raise RuntimeError("BACK_ORIGINAL_SOURCE_LEAK")
    return {
        "schema": "GEMINI_NATIVE500_GCS_PLAN_V1",
        "campaign": campaign,
        "model": model_id,
        "phase": phase,
        "prior_actual": prior_actual,
        "planned_calls": len(tasks),
        "approval_cap": 500,
        "sample_manifest_sha256": manifest_sha,
        "sample_ids": [str(row["id"]) for row in rows],
        "tasks": tasks,
    }


def validate_plan(plan: dict, model: str) -> None:
    import runpy
    module = runpy.run_path(str(RUNNER), run_name=f"_runner_plan_validation_{model}")
    module["validate_tasks"](plan["tasks"], model, {"max_new": len(plan["tasks"])})
    if len(plan["tasks"]) != plan["planned_calls"]:
        raise RuntimeError("PLAN_CALL_COUNT_MISMATCH")
    if plan["prior_actual"] + len(plan["tasks"]) > 500:
        raise RuntimeError("PLAN_EXCEEDS_500_CAP")
    # Every FIRST must precede all its BACK dependencies.
    slots = {}
    for task in plan["tasks"]:
        if task["path"].endswith("F"):
            slots[task["slot"]] = task
        else:
            first = slots[task["from_slot"]]
            if first["case_id"] != task["case_id"]:
                raise RuntimeError("BACK_CASE_LINK_MISMATCH")


def write_private(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--ab-prior-actual", type=int, default=80)
    args = parser.parse_args()
    sample_dir = Path(args.samples).expanduser()
    output = Path(args.output).expanduser()
    if output.exists():
        raise RuntimeError("PLAN_OUTPUT_ALREADY_EXISTS")

    manifest_raw = (sample_dir / "MANIFEST.json").read_bytes()
    manifest_sha = sha(manifest_raw)
    if manifest_sha != EXPECTED_MANIFEST_SHA:
        raise RuntimeError("SAMPLE_MANIFEST_SHA_MISMATCH")
    manifest = json.loads(manifest_raw)

    dev_all = load_sample(sample_dir, "development_baseline.json", manifest)
    ab_all = load_sample(sample_dir, "ab_candidates.json", manifest)
    final_rows = load_sample(sample_dir, "final_holdout.json", manifest)

    dev = choose_development(dev_all)
    ab = choose_ab(ab_all)
    if len(final_rows) != 50:
        raise RuntimeError("FINAL_HOLDOUT_COUNT")
    final_k = sum(row["side"] == "K" for row in final_rows)
    final_l = sum(row["side"] == "L" for row in final_rows)
    final_cluster_counts = {}
    for row in final_rows:
        cluster = str(row["cluster"])
        final_cluster_counts[cluster] = final_cluster_counts.get(cluster, 0) + 1
    if final_k != 25 or final_l != 25 or len(final_cluster_counts) != 30 or max(final_cluster_counts.values()) > 2:
        raise RuntimeError("FINAL_HOLDOUT_BALANCE_OR_CLUSTER_CAP")
    if not 0 <= args.ab_prior_actual < 500:
        raise RuntimeError("AB_PRIOR_OUT_OF_RANGE")
    if len({str(x["id"]) for x in dev + ab + final_rows}) != 140:
        raise RuntimeError("CROSS_STAGE_DUPLICATE")

    plans = {}
    for model in ("35", "36"):
        plans[f"{model}-development-baseline.json"] = build_development(model, dev, manifest_sha)
    plans["35-ab-compare.json"] = build_ab_35(ab, manifest_sha, args.ab_prior_actual)
    plans["36-ab-compare.json"] = build_ab_36(ab, manifest_sha, args.ab_prior_actual)

    expected_calls = {
        "35-development-baseline.json": 80,
        "36-development-baseline.json": 80,
        "35-ab-compare.json": 300,
        "36-ab-compare.json": 250,
    }
    result_manifest = {
        "campaign": "GEMINI35_36_MODEL_NATIVE_OPT500_20261107",
        "sample_manifest_sha256": manifest_sha,
        "development_selected_records": 40,
        "ab_selected_records": 50,
        "final_holdout_reserved_records": 50,
        "same_source_samples_for_both_models": True,
        "plans": {},
        "budgets": {
            "model35": {
                "development_planned": 80, "development_prior_actual": 0,
                "ab_prior_actual": args.ab_prior_actual, "ab": 300,
                "final_reserved": 100,
                "planned_before_reserve": args.ab_prior_actual + 300 + 100,
                "reserve": 500 - args.ab_prior_actual - 300 - 100,
            },
            "model36": {
                "development_planned": 80, "development_prior_actual": 0,
                "ab_prior_actual": args.ab_prior_actual, "ab": 250,
                "final_reserved": 100,
                "planned_before_reserve": args.ab_prior_actual + 250 + 100,
                "reserve": 500 - args.ab_prior_actual - 250 - 100,
            },
        },
        "paid_api_calls": 0,
    }

    for filename, plan in plans.items():
        model = "35" if filename.startswith("35-") else "36"
        validate_plan(plan, model)
        if len(plan["tasks"]) != expected_calls[filename]:
            raise RuntimeError(f"UNEXPECTED_TASK_COUNT:{filename}")
        payload = (json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        plan_sha = sha(payload)
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(output, 0o700)
        write_private(output / filename, payload)
        object_name = f"{PREFIX}/{model}/plans/{plan_sha}.json"
        result_manifest["plans"][filename] = {
            "model": plan["model"],
            "phase": plan["phase"],
            "prior_actual": plan["prior_actual"],
            "planned_calls": len(plan["tasks"]),
            "plan_sha256": plan_sha,
            "gcs_object": f"gs://{BUCKET}/{object_name}",
            "sample_ids": plan["sample_ids"],
        }

    manifest_payload = (
        json.dumps(result_manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    write_private(output / "PLAN_MANIFEST.json", manifest_payload)

    print("PLAN_BUILD: PASS")
    print("SAMPLE_MANIFEST_SHA256:", manifest_sha)
    print("DEVELOPMENT_RECORDS:", len(dev), "K=", sum(x["side"] == "K" for x in dev),
          "L=", sum(x["side"] == "L" for x in dev))
    print("AB_RECORDS:", len(ab), "K=", sum(x["side"] == "K" for x in ab),
          "L=", sum(x["side"] == "L" for x in ab))
    print("FINAL_RESERVED_RECORDS:", len(final_rows))
    for name, info in result_manifest["plans"].items():
        print(name, "CALLS=", info["planned_calls"], "SHA256=", info["plan_sha256"])
        print("GCS_OBJECT:", info["gcs_object"])
    print("MODEL35_PLANNED_WITH_FINAL:", args.ab_prior_actual + 400,
          "RESERVE:", 500 - args.ab_prior_actual - 400)
    print("MODEL36_PLANNED_WITH_FINAL:", args.ab_prior_actual + 350,
          "RESERVE:", 500 - args.ab_prior_actual - 350)
    print("OUTPUT_DIRECTORY:", output)
    print("PAID_API_CALLS: 0")


if __name__ == "__main__":
    main()
