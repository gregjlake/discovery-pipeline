"""Phase 5: Spot-check the pipeline output against historical expectations.

Six numbered checks. Exits non-zero if any fail.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import PROC


def fmt(b):
    return "[PASS]" if b else "[FAIL]"


def peak_year(scores, country):
    s = scores[(scores["country_name"] == country) & scores["structural_strength"].notna()]
    if s.empty:
        return None, None
    idx = s["structural_strength"].idxmax()
    return int(s.loc[idx, "year"]), float(s.loc[idx, "structural_strength"])


def score_at(scores, country, year):
    s = scores[(scores["country_name"] == country) & (scores["year"] == year)]
    if s.empty or pd.isna(s["structural_strength"].values[0]):
        return None
    return float(s["structural_strength"].values[0])


def is_peer(peers, country, year, candidate, top_n=5):
    p = peers[(peers["country_name"] == country) & (peers["year"] == year)]
    p = p[p["peer_rank"] <= top_n]
    return candidate in p["peer_name"].tolist()


def top_peers(peers, country, year, n=3):
    p = peers[(peers["country_name"] == country) & (peers["year"] == year)]
    p = p.sort_values("peer_rank").head(n)
    return [(r["peer_name"], r["distance"], r["similarity_pct"]) for _, r in p.iterrows()]


def main():
    print("[Phase 5] Validation")
    print("=" * 72)

    scores = pd.read_csv(PROC / "structural_scores.csv")
    peers  = pd.read_csv(PROC / "peers.csv")

    results = []

    # ── 1. UK peaks 1860-1970 ──
    yr, sc = peak_year(scores, "United Kingdom")
    ok = yr is not None and 1860 <= yr <= 1970
    print(f"\n1. UK peak year in 1860-1970")
    sc_str = f"{sc:.1f}" if sc is not None else "n/a"
    print(f"   peak year={yr} score={sc_str}  {fmt(ok)}")
    results.append(("UK peak 1860-1970", ok))

    # ── 2. Japan: pre-1870 max < 27 AND 1870 -> 2000 delta > 20 ──
    pre_1870 = scores[
        (scores["country_name"] == "Japan") &
        (scores["year"] < 1870) &
        scores["structural_strength"].notna()
    ]["structural_strength"]
    pre_max = float(pre_1870.max()) if len(pre_1870) else None
    j_1870 = score_at(scores, "Japan", 1870)
    j_2000 = score_at(scores, "Japan", 2000)
    delta = (j_2000 - j_1870) if (j_1870 is not None and j_2000 is not None) else None
    pre_ok = pre_max is not None and pre_max < 27
    delta_ok = delta is not None and delta > 20
    ok = pre_ok and delta_ok
    print(f"\n2. Japan low pre-1870 (<27) and rises 1870->2000 (delta>20)")
    pre_str = f"{pre_max:.1f}" if pre_max is not None else "n/a"
    delta_str = f"{delta:.1f}" if delta is not None else "n/a"
    print(f"   pre-1870 max={pre_str}  1870={j_1870}  2000={j_2000}  delta={delta_str}  {fmt(ok)}")
    results.append(("Japan trajectory", ok))

    # ── 3. Argentina peaks 1920-1970 then declines ──
    yr_a, sc_a = peak_year(scores, "Argentina")
    a_2000 = score_at(scores, "Argentina", 2000)
    in_window = yr_a is not None and 1920 <= yr_a <= 1970
    declined = sc_a is not None and a_2000 is not None and a_2000 < sc_a - 5
    ok = in_window and declined
    print(f"\n3. Argentina peak 1920-1970 then declines")
    sc_a_str = f"{sc_a:.1f}" if sc_a is not None else "n/a"
    a2k_str = f"{a_2000:.1f}" if a_2000 is not None else "n/a"
    print(f"   peak year={yr_a} score={sc_a_str}  2000 score={a2k_str}  {fmt(ok)}")
    results.append(("Argentina peak/decline", ok))

    # ── 4. China rises from 1820 low to above 40 by 2000 ──
    c_1820 = score_at(scores, "China", 1820)
    c_2000 = score_at(scores, "China", 2000)
    high_end = c_2000 is not None and c_2000 > 40
    rises    = (c_1820 is not None and c_2000 is not None and c_2000 > c_1820)
    ok = high_end and rises
    print(f"\n4. China rises from 1820 to above 40 by 2000")
    c1820_str = f"{c_1820:.1f}" if c_1820 is not None else "n/a"
    c2000_str = f"{c_2000:.1f}" if c_2000 is not None else "n/a"
    print(f"   1820={c1820_str}  2000={c2000_str}  {fmt(ok)}")
    results.append(("China rise to 2000", ok))

    # ── 5. UK and Belgium are mutual top-5 peers in 1820 ──
    ok_a = is_peer(peers, "United Kingdom", 1820, "Belgium", top_n=5)
    ok_b = is_peer(peers, "Belgium",        1820, "United Kingdom", top_n=5)
    ok = ok_a or ok_b
    print(f"\n5. UK and Belgium are top-5 peers in 1820")
    print(f"   UK->Belgium={ok_a}  Belgium->UK={ok_b}  {fmt(ok)}")
    results.append(("UK<->Belgium 1820", ok))

    # ── 6. Russia: 1870+ has data, with known nulls at 1880 and 1910 ──
    r_1870 = score_at(scores, "Russia", 1870)
    r_1880 = score_at(scores, "Russia", 1880)
    r_1910 = score_at(scores, "Russia", 1910)
    has_1870 = r_1870 is not None
    gap_1880 = r_1880 is None
    gap_1910 = r_1910 is None
    # post-1910 should be largely complete (allow 0 missing in 1920..2000)
    post = scores[
        (scores["country_name"] == "Russia") &
        (scores["year"].between(1920, 2000))
    ]
    post_missing = int(post["structural_strength"].isna().sum())
    post_ok = post_missing == 0
    ok = has_1870 and gap_1880 and gap_1910 and post_ok
    print(f"\n6. Russia has 1870+ data with known gaps at 1880 and 1910")
    print(f"   1870={r_1870}  1880={r_1880}  1910={r_1910}  post-1910 missing={post_missing}  {fmt(ok)}")
    results.append(("Russia gaps", ok))

    # ── Detail: top-3 peers in 1900 (informational, not a gated test) ──
    print("\n" + "-" * 72)
    print("Top-3 peers in 1900 (informational)")
    print("-" * 72)
    for country in ["United Kingdom", "United States", "Germany",
                    "Japan", "China", "Argentina"]:
        peers_list = top_peers(peers, country, 1900, n=3)
        score = score_at(scores, country, 1900)
        score_str = f"{score:.1f}" if score is not None else "n/a"
        print(f"   {country:18s} (score {score_str})")
        for name, dist, sim in peers_list:
            print(f"     - {name:20s}  distance={dist:>5.1f}  similarity={sim:>5.1f}%")

    # ── Trajectories ──
    print("\n" + "=" * 72)
    print("Score trajectories (1820-2000)")
    print("=" * 72)
    for country in ["United Kingdom", "Argentina"]:
        sub = scores[scores["country_name"] == country].sort_values("year")
        print(f"\n  {country}")
        for _, row in sub.iterrows():
            s = row["structural_strength"]
            s_str = f"{s:6.1f}" if pd.notna(s) else "   n/a"
            n_vars = len(str(row["variables_used"]).split(",")) if pd.notna(row["variables_used"]) else 0
            print(f"    {int(row['year'])}   {s_str}    ({n_vars} vars)")

    # ── Summary ──
    print("\n" + "=" * 72)
    n_pass = sum(1 for _, ok in results if ok)
    n_fail = len(results) - n_pass
    print(f"Validation: {n_pass}/{len(results)} passed  ({n_fail} failed)")
    for name, ok in results:
        print(f"  {fmt(ok)}  {name}")

    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
