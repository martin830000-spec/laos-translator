from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PATHS = ["KF", "KB", "LF", "LB"]
VARIANTS = {
    "35": ["BASE", "N35", "S35", "S35_LOW"],
    "36": ["BASE", "R36", "S36", "S36_MINIMAL"],
}
CONFIGS = {
    "35": {"model": "gemini-3.5-flash-lite", "smart_variant": {"S35", "S35_LOW"}},
    "36": {"model": "gemini-3.6-flash", "smart_variant": {"S36", "S36_MINIMAL"}},
}
INPUTS = {
    "KF": "나 잘 들어가. 내 동생도 함께 왔어.",
    "KB": "ຂ້ອຍຈະລໍຖ້າເຈົ້າ.",
    "LF": "ແມ່ຂອງຂ້ອຍມາແລ້ວ ແລະ ນ້ອງຊາຍກໍມານຳ.",
    "LB": "나 잘 들어가. 내 동생도 함께 왔어.",
}
EXPECTED_SMART = {
    "KF": {"SELF", "HOME", "REL"},
    "LF": {"ELDER", "REL"},
}
NO_SMART_INPUTS = {
    "KF": "오늘은 날씨가 좋아.",
    "LF": "ອາກາດດີມື້ນີ້.",
}


def fail(message):
    raise AssertionError(message)


def run_engine(engine):
    directory = ROOT / "experiments" / f"gemini{engine}-native500"
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    expected = CONFIGS[engine]
    assert config["enabled"] is False, f"{engine}: paid gate must remain disabled"
    assert config["max_new"] == 0, f"{engine}: paid gate must remain zero"
    assert config["prior_actual"] == 0, f"{engine}: native campaign must start at zero"
    assert config["model"] == expected["model"], f"{engine}: model mismatch"

    requests = []
    for path in PATHS:
        for variant in VARIANTS[engine]:
            requests.append({
                "mode": "build",
                "path": path,
                "variant": variant,
                "input": INPUTS[path],
            })

    # Explicitly prove that SMART selectors return no IDs for neutral inputs.
    for path in ("KF", "LF"):
        variant = "S35" if engine == "35" and path == "KF" else (
            "S35" if engine == "35" else "S36"
        )
        requests.append({
            "mode": "build",
            "path": path,
            "variant": variant,
            "input": NO_SMART_INPUTS[path],
        })

    wire = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests)
    proc = subprocess.run(
        ["node", str(directory / "worker.cjs")],
        input=wire,
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=directory,
        timeout=20,
    )
    assert proc.returncode == 0, f"{engine}: worker exit={proc.returncode}; stderr={proc.stderr}"
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == len(requests), (
        f"{engine}: expected {len(requests)} worker responses, got {len(lines)}; "
        f"stderr={proc.stderr}"
    )

    for index, (request, line) in enumerate(zip(requests, lines), 1):
        try:
            envelope = json.loads(line)
        except Exception as exc:
            fail(f"{engine}: response {index} is not JSON: {type(exc).__name__}")
        assert envelope.get("ok") is True, (
            f"{engine}: response {index} failed: {envelope.get('error')}"
        )
        result = envelope["value"]
        path = request["path"]
        variant = request["variant"]
        source = request["input"]
        assert result.get("model") == expected["model"], (
            f"{engine}/{path}/{variant}: wrong model {result.get('model')}"
        )
        payload = result.get("payload", {})
        assert payload.get("contents") == [{"role": "user", "parts": [{"text": source}]}], (
            f"{engine}/{path}/{variant}: source payload changed"
        )
        generation = payload.get("generationConfig", {})
        assert generation.get("maxOutputTokens") == 1024, (
            f"{engine}/{path}/{variant}: unexpected output limit"
        )
        assert result.get("version"), f"{engine}/{path}/{variant}: missing candidate version"

        if variant == "BASE":
            continue

        smart = result.get("smart", {})
        selected = set(smart.get("selected_ids", []))
        attached = set(smart.get("attached_ids", []))
        attachment = smart.get("attachment", "")

        if path.endswith("B"):
            assert not attached and not attachment, (
                f"{engine}/{path}/{variant}: BACK must not receive SMART"
            )
        elif variant in expected["smart_variant"]:
            expected_ids = (
                set() if source in NO_SMART_INPUTS.values()
                else EXPECTED_SMART[path]
            )
            assert selected == expected_ids, (
                f"{engine}/{path}/{variant}: selected {selected}, expected {expected_ids}"
            )
            assert attached == expected_ids, (
                f"{engine}/{path}/{variant}: attached {attached}, expected {expected_ids}"
            )
            assert bool(attachment) == bool(expected_ids), (
                f"{engine}/{path}/{variant}: attachment presence mismatch"
            )
        else:
            assert not attached and not attachment, (
                f"{engine}/{path}/{variant}: non-SMART variant attached context"
            )

    return len(requests)


def protected_readiness():
    blockers = {}
    for engine in ("35", "36"):
        directory = ROOT / "experiments" / f"gemini{engine}-native500"
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        workflow = (
            ROOT / ".github" / "workflows" / f"gemini-native500-{engine}.yml"
        ).read_text(encoding="utf-8")
        activation_path = directory / "activation-gcs.json"
        missing = [
            key for key in ("run_nonce", "plan_sha256")
            if key not in config
        ]
        if not activation_path.is_file():
            missing.append("activation-gcs.json")
        if "projects/460077888071/locations/global/workloadIdentityPools/lao-github-deploy/providers/gemini-research" not in workflow:
            missing.append("dedicated WIF provider binding")
        if "gemini-research-runner@gen-lang-client-0422436907.iam.gserviceaccount.com" not in workflow:
            missing.append("dedicated research service account binding")
        if f"runner.py execute {engine}" not in workflow:
            missing.append("GCS runner entrypoint")
        if "handshake.json" in workflow or "runner.py prepare" in workflow:
            missing.append("legacy encrypted Issue handshake still active")
        assert config["enabled"] is False and config["max_new"] == 0
        blockers[engine] = sorted(set(missing))
    return {
        "ready": not any(blockers.values()),
        "paid_calls": 0,
        "models": blockers,
        "external_wif_access": "VERIFIED_BY_GITHUB_ACTIONS_PREFLIGHT",
        "private_gcs_plan": "NOT_UPLOADED",
        "note": "Dedicated WIF authentication and scoped GCS object read/write were verified; only the frozen private plan and activation remain. Paid gates remain locked.",
    }


def gcs_protocol_offline():
    import runpy
    import importlib.util
    import os
    runner = ROOT / "experiments" / "gemini-native500-gcs" / "runner.py"
    selector = ROOT / "experiments" / "gemini-native500-gcs" / "select_samples.py"
    assert selector.is_file()
    selector_source = selector.read_text(encoding="utf-8")
    compile(selector_source, str(selector), "exec")
    assert "from itertools import combinations" in selector_source
    selector_module = runpy.run_path(str(selector), run_name="_native500_selector_offline")
    import random
    synthetic_final = []
    for index in range(8):
        synthetic_final.append({"id": f"ko-{index}", "side": "K", "partition": "FINAL", "cluster": f"k-only-{index}", "source": "synthetic", "first": "synthetic", "back": "synthetic"})
    for index in range(21):
        cluster = f"shared-{index}"
        synthetic_final.append({"id": f"k-{index}", "side": "K", "partition": "FINAL", "cluster": cluster, "source": "synthetic", "first": "synthetic", "back": "synthetic"})
        synthetic_final.append({"id": f"l-{index}-a", "side": "L", "partition": "FINAL", "cluster": cluster, "source": "synthetic", "first": "synthetic", "back": "synthetic"})
        synthetic_final.append({"id": f"l-{index}-b", "side": "L", "partition": "FINAL", "cluster": cluster, "source": "synthetic", "first": "synthetic", "back": "synthetic"})
    synthetic_final.append({"id": "l-only", "side": "L", "partition": "FINAL", "cluster": "l-only", "source": "synthetic", "first": "synthetic", "back": "synthetic"})
    selected_final = selector_module["select_final"](synthetic_final, random.Random(20261110))
    final_stats = selector_module["summarize"](selected_final)
    assert final_stats["records"] == 50
    assert final_stats["K"] == 25 and final_stats["L"] == 25
    assert final_stats["clusters"] == 30
    assert final_stats["max_records_per_cluster"] == 2
    assert runner.is_file()
    compile(runner.read_text(encoding="utf-8"), str(runner), "exec")
    module = runpy.run_path(str(runner), run_name="_native500_offline")
    valid_tasks = [
        {"slot": "first-1", "case_id": "case-1", "path": "KF",
         "variant": "N35", "input": "잘 잤어?"},
        {"slot": "back-1", "case_id": "case-1", "path": "KB",
         "variant": "N35", "from_slot": "first-1"},
    ]
    assert module["validate_tasks"](valid_tasks, "35", {"max_new": 2})
    illegal = [dict(x) for x in valid_tasks]
    illegal[1]["input"] = "처음 한국어 원문을 역번역에 전달하면 안 됨"
    try:
        module["validate_tasks"](illegal, "35", {"max_new": 2})
        assert False, "Unexpected acceptance of original-source BACK"
    except RuntimeError as exc:
        assert "BACK_MUST_DEPEND" in str(exc)
    cross_variant_tasks = [
        {"slot": "base-first", "case_id": "cross-case", "path": "KF",
         "variant": "BASE", "input": "잘 잤어?"},
        {"slot": "r36-back", "case_id": "cross-case", "path": "KB",
         "variant": "R36", "first_variant": "BASE", "from_slot": "base-first"},
    ]
    assert module["validate_tasks"](cross_variant_tasks, "36", {"max_new": 2})
    unsafe_cross_variant = [dict(x) for x in cross_variant_tasks]
    unsafe_cross_variant[1]["variant"] = "S36"
    try:
        module["validate_tasks"](unsafe_cross_variant, "36", {"max_new": 2})
        assert False, "Unexpected acceptance of unapproved cross-variant pair"
    except RuntimeError as exc:
        assert "UNAPPROVED_CROSS_VARIANT" in str(exc)
    for model in ("35", "36"):
        wf = (ROOT / ".github" / "workflows" /
              f"gemini-native500-{model}.yml").read_text(encoding="utf-8")
        assert "id-token: write" in wf
        assert "projects/460077888071/locations/global/workloadIdentityPools/lao-github-deploy/providers/gemini-research" in wf
        assert "gemini-research-runner@gen-lang-client-0422436907.iam.gserviceaccount.com" in wf
        assert f"runner.py execute {model}" in wf
        assert "issues: write" not in wf
        assert "handshake.json" not in wf and "runner.py prepare" not in wf
        assert "activation-gcs.json" in wf
        assert "secrets.GEMINI_API_KEY" in wf
        assert "github.run_attempt == 1" in wf
        assert "github.actor == 'martin830000-spec'" in wf
    cfg = (ROOT / "experiments" / "gemini35-native500" /
           "config.json").read_text(encoding="utf-8")
    assert '"enabled": false' in cfg
    return {"protocol": "GCS_ONLY", "offline": "PASS", "paid_calls": 0}


def main():
    total = run_engine("35") + run_engine("36")
    gcs_check = gcs_protocol_offline()
    readiness = protected_readiness()
    result = {
        "status": "PASS",
        "checks": total,
        "paid_calls": 0,
        "models": ["gemini-3.5-flash-lite", "gemini-3.6-flash"],
        "checks_include": [
            "worker imports",
            "all four translation paths",
            "all model variants",
            "model ID and source payload integrity",
            "generation output limit",
            "SMART selector exports",
            "SMART active IDs and actual attachments",
            "BACK SMART isolation",
            "neutral-input no-SMART behavior",
            "paid campaign gates remain disabled",
            "runner Python syntax",
            "protected workflow/runner digest field parity",
            "explicit protected-runner readiness blockers",
        ],
        "protected_execution": readiness,
        "gcs_protocol": gcs_check,
    }
    (ROOT / "native500-free.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
