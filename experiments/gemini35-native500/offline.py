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


def main():
    total = run_engine("35") + run_engine("36")
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
        ],
    }
    (ROOT / "native500-free.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
