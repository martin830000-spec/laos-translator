#!/usr/bin/env python3
"""Select deterministic, cluster-separated real-dialogue samples for Gemini 3.5/3.6."""
import argparse
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

EXPECTED_SOURCE_SHA = "1db5838ab90d5a80edb199d959905944fbcfde74fadb5d26b51a3403dcaccfc7"
EXPECTED_TOTAL = 2000
SEED = 20261107
PARTS = ("DEVELOPMENT", "AB", "FINAL")
OUTPUT_FIELDS = (
    "id", "side", "partition", "cluster", "source", "first", "back",
    "source_sha256", "normalized_sha256", "prior_exposed", "version", "time",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_eligible(row: dict, partition: str) -> bool:
    return (
        row.get("partition") == partition
        and row.get("side") in ("K", "L")
        and row.get("cluster") is not None
        and not any(row.get(k) for k in (
            "protected", "first_empty", "back_empty", "direction_mismatch"
        ))
        and all(
            isinstance(row.get(k), str) and row[k].strip()
            for k in ("source", "first", "back")
        )
        and row.get("id") is not None
    )


def make_groups(rows: list, partition: str, rng: random.Random) -> dict:
    groups = defaultdict(lambda: {"K": [], "L": []})
    for row in rows:
        if is_eligible(row, partition):
            groups[str(row["cluster"])][row["side"]].append(row)
    for sides in groups.values():
        for side in ("K", "L"):
            rng.shuffle(sides[side])
    return dict(groups)


def choose_one(groups: dict, side: str, cluster: str, selected: dict) -> dict:
    used = {str(row["id"]) for row in selected[cluster]}
    available = [
        row for row in groups[cluster][side]
        if str(row["id"]) not in used
    ]
    if not available:
        raise RuntimeError(f"NO_AVAILABLE_RECORD:{side}:{cluster}")
    return available[0]


def add_extra_records(
    groups: dict, selected: dict, output: list, side: str, quota: int,
    max_per_cluster: int, rng: random.Random
) -> None:
    while sum(row["side"] == side for row in output) < quota:
        candidates = [
            cluster for cluster, sides in groups.items()
            if len(selected[cluster]) < max_per_cluster
            and any(
                str(row["id"]) not in {str(x["id"]) for x in selected[cluster]}
                for row in sides[side]
            )
        ]
        if not candidates:
            raise RuntimeError(f"QUOTA_UNAVAILABLE:{side}:{quota}")
        rng.shuffle(candidates)
        candidates.sort(key=lambda c: len(selected[c]))
        cluster = candidates[0]
        row = choose_one(groups, side, cluster, selected)
        selected[cluster].append(row)
        output.append(row)


def summarize(rows: list) -> dict:
    cluster_counts = Counter(str(row["cluster"]) for row in rows)
    lengths = Counter(
        "short" if len(row["source"]) <= 40
        else "medium" if len(row["source"]) <= 150
        else "long"
        for row in rows
    )
    return {
        "records": len(rows),
        "K": sum(row["side"] == "K" for row in rows),
        "L": sum(row["side"] == "L" for row in rows),
        "clusters": len(cluster_counts),
        "max_records_per_cluster": max(cluster_counts.values()),
        "length_buckets": dict(lengths),
        "prior_exposed": dict(Counter(str(row.get("prior_exposed")) for row in rows)),
    }


def select_development(rows: list, rng: random.Random) -> list:
    groups = make_groups(rows, "DEVELOPMENT", rng)
    common = [c for c, sides in groups.items() if sides["K"] and sides["L"]]
    rng.shuffle(common)
    if len(common) < 40:
        raise RuntimeError("INSUFFICIENT_DEVELOPMENT_COMMON_CLUSTERS")
    selected = defaultdict(list)
    result = []
    for cluster in common[:40]:
        for side in ("K", "L"):
            row = choose_one(groups, side, cluster, selected)
            selected[cluster].append(row)
            result.append(row)
    assert summarize(result)["K"] == 40
    assert summarize(result)["L"] == 40
    assert summarize(result)["clusters"] == 40
    assert summarize(result)["max_records_per_cluster"] == 2
    return result


def select_ab(rows: list, rng: random.Random) -> list:
    groups = make_groups(rows, "AB", rng)
    selected = defaultdict(list)
    result = []
    quotas = {"K": 28, "L": 27}

    # First pass spreads one record of each direction across distinct clusters.
    for side in ("K", "L"):
        clusters = [c for c, sides in groups.items() if sides[side]]
        rng.shuffle(clusters)
        for cluster in clusters:
            if sum(row["side"] == side for row in result) >= quotas[side]:
                break
            row = choose_one(groups, side, cluster, selected)
            selected[cluster].append(row)
            result.append(row)

    # Fill remaining quota using least-loaded eligible clusters, max 3 per cluster.
    for side in ("K", "L"):
        add_extra_records(groups, selected, result, side, quotas[side], 3, rng)

    stats = summarize(result)
    assert stats["records"] == 55
    assert stats["K"] == 28 and stats["L"] == 27
    assert stats["max_records_per_cluster"] <= 3
    return result


def select_final(rows: list, rng: random.Random) -> list:
    groups = make_groups(rows, "FINAL", rng)
    k_clusters = {c for c, sides in groups.items() if sides["K"]}
    l_clusters = {c for c, sides in groups.items() if sides["L"]}
    shared = k_clusters & l_clusters
    k_only = sorted(k_clusters - l_clusters)

    if len(k_clusters) != 29 or len(l_clusters) != 22 or len(shared) != 21 or len(k_only) != 8:
        raise RuntimeError("FINAL_CLUSTER_LAYOUT_CHANGED")

    # Select 8 K-only + 17 shared clusters for 25 K records.
    # Leave at least 3 other shared clusters with a second L record available.
    chosen_k_shared = None
    extra_l_shared = None
    for combo in combinations(sorted(shared), 17):
        remaining = [
            c for c in shared - set(combo)
            if len(groups[c]["L"]) >= 2
        ]
        if len(remaining) >= 3:
            chosen_k_shared = set(combo)
            rng.shuffle(remaining)
            extra_l_shared = remaining[:3]
            break

    if chosen_k_shared is None:
        raise RuntimeError("FINAL_MAX2_CLUSTER_LAYOUT_UNAVAILABLE")

    selected = defaultdict(list)
    result = []

    for cluster in k_only + sorted(chosen_k_shared):
        row = choose_one(groups, "K", cluster, selected)
        selected[cluster].append(row)
        result.append(row)

    # One L from each of 22 L clusters.
    for cluster in sorted(l_clusters):
        row = choose_one(groups, "L", cluster, selected)
        selected[cluster].append(row)
        result.append(row)

    # Add exactly one more L to three shared clusters not used for K.
    for cluster in extra_l_shared:
        row = choose_one(groups, "L", cluster, selected)
        selected[cluster].append(row)
        result.append(row)

    stats = summarize(result)
    assert stats["records"] == 50
    assert stats["K"] == 25 and stats["L"] == 25
    assert stats["max_records_per_cluster"] <= 2
    assert stats["clusters"] == 30
    return result


def write_private(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.source).expanduser()
    output = Path(args.output).expanduser()
    if output.exists():
        raise RuntimeError("OUTPUT_ALREADY_EXISTS")
    raw = source.read_bytes()
    source_sha = sha256(raw)
    if source_sha != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"SOURCE_SHA_MISMATCH:{source_sha}")
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != EXPECTED_TOTAL:
        raise RuntimeError("SOURCE_RECORD_COUNT_MISMATCH")

    # Verify eligible counts against the already inspected dataset statistics.
    expected = {
        "DEVELOPMENT": {"K": 526, "L": 518},
        "AB": {"K": 217, "L": 267},
        "FINAL": {"K": 193, "L": 153},
    }
    for partition in PARTS:
        eligible = [r for r in rows if is_eligible(r, partition)]
        counts = Counter(r["side"] for r in eligible)
        if dict(counts) != expected[partition]:
            raise RuntimeError(
                f"ELIGIBLE_COUNT_CHANGED:{partition}:{dict(counts)}"
            )

    # Existing partition labels are already cluster-disjoint; verify again.
    partition_clusters = {
        part: {
            str(r["cluster"]) for r in rows
            if r.get("partition") == part and r.get("cluster") is not None
        }
        for part in PARTS
    }
    for i, left in enumerate(PARTS):
        for right in PARTS[i + 1:]:
            if partition_clusters[left] & partition_clusters[right]:
                raise RuntimeError(f"CROSS_PARTITION_CLUSTER_OVERLAP:{left}:{right}")

    # Independent deterministic RNG streams prevent one stage from affecting another.
    baseline = select_development(rows, random.Random(SEED + 1))
    ab = select_ab(rows, random.Random(SEED + 2))
    final = select_final(rows, random.Random(SEED + 3))

    all_rows = baseline + ab + final
    ids = [str(r["id"]) for r in all_rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("DUPLICATE_SOURCE_RECORD_ACROSS_SETS")

    sets = {
        "development_baseline.json": baseline,
        "ab_candidates.json": ab,
        "final_holdout.json": final,
    }

    # All selection checks are complete before creating the output directory.
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(output, 0o700)

    manifest = {
        "campaign": "GEMINI35_36_MODEL_NATIVE_OPT500_20261107",
        "source_file": source.name,
        "source_sha256": source_sha,
        "seed": SEED,
        "same_samples_for_both_models": True,
        "partition_cluster_overlap": 0,
        "selection_policy": {
            "DEVELOPMENT": "40 clusters, one K and one L per cluster",
            "AB": "28 K, 27 L, maximum 3 records per cluster",
            "FINAL": "25 K, 25 L, maximum 3 records per cluster",
        },
        "sets": {},
    }

    for name, selected_rows in sets.items():
        clean = [
            {key: row[key] for key in OUTPUT_FIELDS if key in row}
            for row in selected_rows
        ]
        payload = (
            json.dumps(clean, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        write_private(output / name, payload)
        manifest["sets"][name] = {
            **summarize(selected_rows),
            "sha256": sha256(payload),
            "record_ids": [str(row["id"]) for row in selected_rows],
            "clusters": sorted({str(row["cluster"]) for row in selected_rows}),
        }

    manifest["total_records"] = len(all_rows)
    manifest["unique_source_records"] = len(set(ids))
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    write_private(output / "MANIFEST.json", manifest_payload)

    # Re-read every output and verify file hashes and counts.
    for name, info in manifest["sets"].items():
        saved = (output / name).read_bytes()
        if sha256(saved) != info["sha256"]:
            raise RuntimeError(f"OUTPUT_SHA_MISMATCH:{name}")
        if len(json.loads(saved)) != info["records"]:
            raise RuntimeError(f"OUTPUT_COUNT_MISMATCH:{name}")

    print("SAMPLE_SELECTION: PASS")
    print("SOURCE_SHA256: PASS")
    print("TOTAL_SELECTED:", len(all_rows))
    print("UNIQUE_SOURCE_RECORDS:", len(set(ids)))
    for name, selected_rows in sets.items():
        print(name, json.dumps(summarize(selected_rows), ensure_ascii=False))
        print("SHA256:", manifest["sets"][name]["sha256"])
    print("MANIFEST_SHA256:", sha256(manifest_payload))
    print("OUTPUT_DIRECTORY:", output)
    print("FILE_PERMISSIONS: 600")
    print("PAID_API_CALLS: 0")


if __name__ == "__main__":
    main()
