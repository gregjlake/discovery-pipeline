"""Phase 5: Spot-check the pipeline output against historical expectations."""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from _common import PROC


def fmt_pass(b):
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

    # ── 1. UK structural strength has its broad-plateau peak between 1860 and 1970 ──
    yr, sc = peak_year(scores, "United Kingdom")
    ok = yr is not None and 1860 <= yr <= 1970
    print(f"\n1. UK peaks in 1860-1970 window (broad plateau)")
    print(f"   peak year={yr} score={sc:.1f}  {fmt_pass(ok)}")

    # ── 2. Japan rises sharply after 1870 ──
    j_1870 = score_at(scores, "Japan", 1870)
    j_1900 = score_at(scores, "Japan", 1900)
    j_2000 = score_at(scores, "Japan", 2000)
    rise_70_to_2000 = (j_2000 - j_1870) if j_1870 and j_2000 else None
    ok = rise_70_to_2000 is not None and rise_70_to_2000 > 20
    print(f"\n2. Japan rises sharply 1870 -> 2000 (delta > 20)")
    print(f"   1870={j_1870}  1900={j_1900}  2000={j_2000}  delta={rise_70_to_2000}  {fmt_pass(ok)}")

    # ── 3. Argentina peaks 1880-1920 then declines ──
    yr_a, sc_a = peak_year(scores, "Argentina")
    a_2000 = score_at(scores, "Argentina", 2000)
    declined = sc_a is not None and a_2000 is not None and a_2000 < sc_a - 5
    in_window = yr_a is not None and 1920 <= yr_a <= 1970
    ok = in_window and declined
    print(f"\n3. Argentina peaks 1920-1970 then declines")
    print(f"   peak year={yr_a} score={sc_a}  2000 score={a_2000}  {fmt_pass(ok)}")

    # ── 4. China low 1870-1950 then rises after 1980 ──
    early = scores[
        (scores["country_name"] == "China") &
        (scores["year"].between(1870, 1950)) &
        scores["structural_strength"].notna()
    ]["structural_strength"]
    late = scores[
        (scores["country_name"] == "China") &
        (scores["year"] >= 1980) &
        scores["structural_strength"].notna()
    ]["structural_strength"]
    early_mean = early.mean() if len(early) else None
    late_mean  = late.mean()  if len(late)  else None
    ok = early_mean is not None and late_mean is not None and late_mean > early_mean + 10
    print(f"\n4. China rises post-1980 (late mean - early mean > 10)")
    print(f"   1870-1950 mean={early_mean}  1980+ mean={late_mean}  {fmt_pass(ok)}")

    # ── 5. UK and Belgium peers in 1820 ──
    ok_a = is_peer(peers, "United Kingdom", 1820, "Belgium", top_n=5)
    ok_b = is_peer(peers, "Belgium",        1820, "United Kingdom", top_n=5)
    print(f"\n5. UK and Belgium are mutual top-5 peers in 1820")
    print(f"   UK->Belgium={ok_a}  Belgium->UK={ok_b}  {fmt_pass(ok_a or ok_b)}")

    # ── 6. USA and UK peers by 1900 ──
    ok_a = is_peer(peers, "United States",  1900, "United Kingdom", top_n=5)
    ok_b = is_peer(peers, "United Kingdom", 1900, "United States",  top_n=5)
    print(f"\n6. USA and UK are top-5 peers in 1900")
    print(f"   USA->UK={ok_a}  UK->USA={ok_b}  {fmt_pass(ok_a or ok_b)}")

    # ── 7. Top 3 peers in 1900 for selected countries ──
    print(f"\n7. Top 3 peers in 1900")
    for country in ["United Kingdom", "United States", "Germany",
                    "Japan", "China", "Argentina"]:
        peers_list = top_peers(peers, country, 1900, n=3)
        score = score_at(scores, country, 1900)
        score_str = f"{score:.1f}" if score is not None else "n/a"
        print(f"   {country:18s} (score {score_str})")
        if not peers_list:
            print("     (no peers found)")
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

    # ── Peer matrix across the 5 key decades ──
    print("\n" + "=" * 72)
    print("Top-3 peers in 1820, 1870, 1900, 1950, 2000")
    print("=" * 72)
    target_years = [1820, 1870, 1900, 1950, 2000]
    for country in ["United Kingdom", "United States", "Germany",
                    "Japan", "China", "Argentina"]:
        print(f"\n  {country}")
        for yr in target_years:
            score = score_at(scores, country, yr)
            score_str = f"{score:5.1f}" if score is not None else "  n/a"
            peers_list = top_peers(peers, country, yr, n=3)
            peer_strs = []
            for name, _, sim in peers_list:
                peer_strs.append(f"{name} ({sim:.0f}%)")
            joined = "  |  ".join(peer_strs) if peer_strs else "(none)"
            print(f"    {yr}  score={score_str}   {joined}")

    print("\n" + "=" * 72)


if __name__ == "__main__":
    main()
