#!/usr/bin/env python3
"""Download private baseline slots from GCS and produce a compact private review JSON."""
import argparse
import json
import math
import pathlib
import statistics
import subprocess
import tempfile
from collections import Counter, defaultdict

BUCKET = "lao-translator-src-460077888071"
PREFIX = "research/gemini-model-native500-20261107"
PLAN_SHA = {
    "35": "9cd55e8dceeda7b334bcad32dcb7c6d22768361e82b22c3c4b853141c7dba78b",
    "36": "f597d1317494470b42f5e7e4c45126e396e01b64555da057717d0a4d0ee07cbb",
}
MODEL_NAMES = {"35": "gemini-3.5-flash-lite", "36": "gemini-3.6-flash"}


def run(args):
    subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    index = max(0, min(len(values) - 1, math.ceil(pct * len(values)) - 1))
    return values[index]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = pathlib.Path(args.output).expanduser()
    if output.exists():
        raise RuntimeError("OUTPUT_ALREADY_EXISTS")

    records = []
    phase_summary = {}

    with tempfile.TemporaryDirectory(prefix="native500-review-") as temp:
        temp_root = pathlib.Path(temp)
        for engine in ("35", "36"):
            plan_sha = PLAN_SHA[engine]
            result_prefix = f"{PREFIX}/{engine}/results/{plan_sha}"
            local_dir = temp_root / engine
            local_dir.mkdir()

            # Download only the private result namespace for this exact baseline plan.
            run([
                "gcloud", "storage", "cp", "--recursive",
                f"gs://{BUCKET}/{result_prefix}/", str(local_dir)
            ])

            finish_files = list(local_dir.rglob("RUN_FINISHED.json"))
            if len(finish_files) != 1:
                raise RuntimeError(f"RUN_FINISHED_MISSING_OR_DUPLICATE:{engine}")
            finish = json.loads(finish_files[0].read_text(encoding="utf-8"))

            slot_files = [p for p in local_dir.rglob("*.json") if p.parent.name == "slots"]
            if len(slot_files) != 80:
                raise RuntimeError(f"EXPECTED_80_SLOT_FILES:{engine}:{len(slot_files)}")

            model_rows = []
            for path in slot_files:
                row = json.loads(path.read_text(encoding="utf-8"))
                if row.get("status") == "SKIPPED_DEPENDENCY":
                    model_rows.append({
                        "model": MODEL_NAMES[engine], "slot": row.get("slot"),
                        "status": row["status"]
                    })
                    continue
                response = row.get("response") or {}
                inspection = row.get("inspection") or {}
                request = row.get("request") or {}
                usage = response.get("usageMetadata") or {}
                model_rows.append({
                    "model": MODEL_NAMES[engine],
                    "case_id": row.get("case_id"),
                    "path": row.get("path"),
                    "stage": "FIRST" if str(row.get("path", "")).endswith("F") else "BACK",
                    "variant": row.get("variant"),
                    "slot": row.get("slot"),
                    "source_or_back_input": row.get("input"),
                    "displayed_translation": row.get("displayed"),
                    "raw_translation": inspection.get("raw_text"),
                    "status": row.get("status"),
                    "http_status": row.get("http_status"),
                    "finish_reason": inspection.get("reason"),
                    "warnings": inspection.get("warnings", []),
                    "elapsed_s": row.get("elapsed_s"),
                    "prompt_version": request.get("version"),
                    "prompt_sha256": request.get("prompt_sha256"),
                    "model_version": response.get("modelVersion"),
                    "usage": {
                        "prompt_tokens": usage.get("promptTokenCount"),
                        "candidate_tokens": usage.get("candidatesTokenCount"),
                        "total_tokens": usage.get("totalTokenCount"),
                        "thoughts_tokens": usage.get("thoughtsTokenCount"),
                    },
                })

            model_rows.sort(key=lambda x: (str(x.get("case_id", "")), str(x.get("path", ""))))
            records.extend(model_rows)
            latencies = [
                float(x["elapsed_s"]) for x in model_rows
                if isinstance(x.get("elapsed_s"), (int, float))
            ]
            token_totals = Counter()
            for x in model_rows:
                for key, value in (x.get("usage") or {}).items():
                    if isinstance(value, (int, float)):
                        token_totals[key] += value

            phase_summary[MODEL_NAMES[engine]] = {
                "run_finished": finish,
                "slot_files": len(slot_files),
                "status_counts": dict(Counter(x.get("status", "UNKNOWN") for x in model_rows)),
                "path_counts": dict(Counter(x.get("path", "UNKNOWN") for x in model_rows)),
                "latency_count": len(latencies),
                "latency_mean_s": statistics.mean(latencies) if latencies else None,
                "latency_median_s": statistics.median(latencies) if latencies else None,
                "latency_p95_s": percentile(latencies, 0.95),
                "token_totals": dict(token_totals),
            }

    if len(records) != 160:
        raise RuntimeError(f"EXPECTED_160_TOTAL_SLOT_RECORDS:{len(records)}")

    result = {
        "report": "GEMINI_NATIVE500_DEVELOPMENT_BASELINE_REVIEW",
        "private_source_data": True,
        "api_calls_in_exporter": 0,
        "models": phase_summary,
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(payload)
    output.chmod(0o600)

    print("BASELINE_EXPORT: PASS")
    print("MODELS:", len(phase_summary))
    print("SLOT_RECORDS:", len(records))
    for model, summary in phase_summary.items():
        print(model, json.dumps({
            "run_finished": summary["run_finished"],
            "status_counts": summary["status_counts"],
            "path_counts": summary["path_counts"],
            "latency_mean_s": summary["latency_mean_s"],
            "latency_median_s": summary["latency_median_s"],
            "latency_p95_s": summary["latency_p95_s"],
            "token_totals": summary["token_totals"],
        }, ensure_ascii=False))
    print("OUTPUT:", output)
    print("OUTPUT_BYTES:", len(payload))
    print("FILE_MODE: 600")
    print("API_CALLS: 0")


if __name__ == "__main__":
    main()
