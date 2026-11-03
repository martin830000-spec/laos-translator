"""Private-data-in / aggregate-only-out length and holdout audit helpers.

Do not commit actual messages or generated private manifests. Length bands are annotated
per language, using corpus distributions plus manual clause/sentence review.
"""
from collections import Counter,defaultdict
from statistics import median
import hashlib

DIRECTIONS=("K","L")
BANDS=("short","medium","long")
KINDS=("actual_spouse","learning_notice","synthetic_stress")

def digest(text):
    if not isinstance(text,str) or not text.strip(): raise ValueError("EMPTY_SOURCE")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def length_features(text):
    # This is a screening proxy, not a Lao sentence parser.
    letters=sum(not ch.isspace() for ch in text)
    breaks=sum(ch in ".!?。！？\n" for ch in text)
    return {"nonspace_chars":letters,"punctuation_breaks":breaks,
            "manual_sentence_review_required":True}

def audit_records(rows, final_a=(),final_b=(),prior_exposures=()):
    """Returns counts only. Raises on flawed holdout split/exposure.
    rows have: side, source_type, length_band, text, cluster_id, protected.
    final_a/final_b contain private record indices; do not display raw data here.
    """
    seen_exact=set()
    stats=defaultdict(list)
    clusters={}
    private_hashes={}
    for i,row in enumerate(rows):
        side=row["side"];band=row["length_band"];kind=row["source_type"]
        if side not in DIRECTIONS or band not in BANDS or kind not in KINDS:
            raise ValueError("UNKNOWN_CATEGORY")
        if not isinstance(row.get("cluster_id"),str) or not row["cluster_id"]:
            raise ValueError("MISSING_CLUSTER")
        h=digest(row["text"])
        private_hashes[i]=h;clusters[i]=row["cluster_id"]
        feat=length_features(row["text"])
        stats[(side,band,kind)].append(feat["nonspace_chars"])
        seen_exact.add(h)
    fa=set(final_a);fb=set(final_b)
    if fa & fb:raise ValueError("FINAL_A_B_INDEX_COLLISION")
    if any(i not in private_hashes for i in fa|fb):raise ValueError("BAD_FINAL_INDEX")
    prior=set(prior_exposures)
    final_ids=fa|fb
    if any(rows[i].get("protected",False) for i in final_ids):
        raise ValueError("FINAL_PROTECTED_RECORD")
    if any(private_hashes[i] in prior or clusters[i] in prior for i in final_ids):
        raise ValueError("FINAL_PRIOR_EXPOSURE")
    if {clusters[i] for i in fa}&{clusters[i] for i in fb}:
        raise ValueError("FINAL_CLUSTER_COLLISION")
    if {private_hashes[i] for i in fa}&{private_hashes[i] for i in fb}:
        raise ValueError("FINAL_SOURCE_COLLISION")
    summary={}
    for side in DIRECTIONS:
        side_rows=[rows[i] for i in range(len(rows)) if rows[i]["side"]==side]
        dist={b:sum(r["length_band"]==b for r in side_rows) for b in BANDS}
        vals=[length_features(r["text"])["nonspace_chars"] for r in side_rows]
        summary[side]={"n":len(side_rows),"bands":dist,
                       "median_nonspace_chars":median(vals) if vals else None,
                       "native_sentence_count_not_automatically_verified":True}
    final_counts={batch:{side:{band:sum(rows[i]["side"]==side and rows[i]["length_band"]==band for i in ids)
                         for band in BANDS} for side in DIRECTIONS}
                  for batch,ids in [("FINAL_A",fa),("FINAL_B",fb)]}
    return {"total_records":len(rows),"exact_unique":len(seen_exact),
            "per_direction":summary,"final_counts":final_counts,
            "final_clusters_disjoint":True,"raw_source_text_emitted":False}
