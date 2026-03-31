"""Unit tests for gravity model core scientific functions.
Runs without live Supabase — uses synthetic data only."""
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── FIXTURES ────────────────────────────────────────────

@pytest.fixture
def sample_counties():
    """Five synthetic counties for testing."""
    return [
        {"fips": "01001", "population": 50000,
         "lat": 32.5, "lon": -86.6,
         "datasets": {"poverty": 0.8, "median_income": 0.2, "unemployment": 0.7, "broadband": 0.3}},
        {"fips": "01002", "population": 30000,
         "lat": 33.0, "lon": -87.0,
         "datasets": {"poverty": 0.75, "median_income": 0.25, "unemployment": 0.65, "broadband": 0.35}},
        {"fips": "06037", "population": 10000000,
         "lat": 34.0, "lon": -118.2,
         "datasets": {"poverty": 0.4, "median_income": 0.6, "unemployment": 0.4, "broadband": 0.8}},
        {"fips": "17031", "population": 5000000,
         "lat": 41.8, "lon": -87.6,
         "datasets": {"poverty": 0.45, "median_income": 0.55, "unemployment": 0.45, "broadband": 0.75}},
        {"fips": "54047", "population": 20000,
         "lat": 37.6, "lon": -81.7,
         "datasets": {"poverty": 0.9, "median_income": 0.1, "unemployment": 0.85, "broadband": 0.2}},
    ]


# ── HAVERSINE DISTANCE TESTS ───────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    """Same formula as calibrate_beta.py."""
    R = 3958.8
    rl = np.radians
    dlat = rl(lat2 - lat1)
    dlon = rl(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rl(lat1)) * np.cos(rl(lat2)) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def test_haversine_same_point():
    """Distance from a point to itself is zero."""
    assert haversine(40.0, -75.0, 40.0, -75.0) == 0.0


def test_haversine_known_distance():
    """NYC to LA is approximately 2,445 miles."""
    nyc_to_la = haversine(40.71, -74.01, 34.05, -118.24)
    assert 2400 < nyc_to_la < 2500, f"Expected ~2445 miles, got {nyc_to_la:.1f}"


def test_haversine_symmetry():
    """Distance A->B equals distance B->A."""
    d1 = haversine(32.5, -86.6, 34.0, -118.2)
    d2 = haversine(34.0, -118.2, 32.5, -86.6)
    assert abs(d1 - d2) < 0.001


def test_haversine_triangle_inequality():
    """Direct distance <= sum of two-leg distances."""
    d_direct = haversine(32.5, -86.6, 41.8, -87.6)
    d_via_la = haversine(32.5, -86.6, 34.0, -118.2) + haversine(34.0, -118.2, 41.8, -87.6)
    assert d_direct <= d_via_la


# ── DATA DISSIMILARITY TESTS ───────────────────────────

def euclidean_dissim(vec_a, vec_b):
    """Normalized Euclidean dissimilarity."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.linalg.norm(a - b) / np.sqrt(len(a)))


def test_dissimilarity_identical_counties():
    """Identical profiles have zero dissimilarity."""
    v = [0.5, 0.3, 0.7, 0.4]
    assert euclidean_dissim(v, v) == 0.0


def test_dissimilarity_opposite_counties():
    """All-0 vs all-1 profile has max dissimilarity=1."""
    zeros = [0.0, 0.0, 0.0, 0.0]
    ones = [1.0, 1.0, 1.0, 1.0]
    assert abs(euclidean_dissim(zeros, ones) - 1.0) < 0.001


def test_dissimilarity_symmetry():
    """Dissimilarity is symmetric."""
    a = [0.8, 0.2, 0.7, 0.3]
    b = [0.4, 0.6, 0.3, 0.7]
    assert abs(euclidean_dissim(a, b) - euclidean_dissim(b, a)) < 1e-10


def test_dissimilarity_triangle_inequality():
    """Triangle inequality holds."""
    a = [0.9, 0.1, 0.8]
    b = [0.5, 0.5, 0.5]
    c = [0.1, 0.9, 0.2]
    assert euclidean_dissim(a, c) <= euclidean_dissim(a, b) + euclidean_dissim(b, c) + 1e-10


# ── COMBINED DISTANCE TESTS ────────────────────────────

def combined_distance(geo_norm, data_dissim, floor=0.01):
    """Multiplicative combined distance with floor."""
    return max(geo_norm * data_dissim, floor)


def test_combined_distance_floor():
    """Combined distance never goes below floor."""
    assert combined_distance(0.0, 0.0) == 0.01
    assert combined_distance(0.001, 0.001) == 0.01


def test_combined_distance_multiplicative():
    """High geo OR high data dissim increases distance."""
    close = combined_distance(0.1, 0.5)
    far = combined_distance(0.9, 0.5)
    assert far > close

    similar = combined_distance(0.5, 0.1)
    diff = combined_distance(0.5, 0.9)
    assert diff > similar


def test_combined_distance_zero_similarity_limit():
    """Identical counties (dissim=0) hit the floor."""
    d = combined_distance(0.5, 0.0)
    assert d == 0.01


# ── GRAVITY FORCE TESTS ────────────────────────────────

def gravity_force(pop_i, pop_j, combined_dist, beta):
    """Core gravity formula."""
    return (pop_i * pop_j) / (combined_dist ** beta)


def test_force_increases_with_population():
    """Larger counties have stronger force."""
    f_small = gravity_force(10000, 10000, 0.1, 0.155)
    f_large = gravity_force(1000000, 1000000, 0.1, 0.155)
    assert f_large > f_small


def test_force_decreases_with_distance():
    """More distant counties have weaker force."""
    f_close = gravity_force(100000, 100000, 0.1, 0.155)
    f_far = gravity_force(100000, 100000, 0.9, 0.155)
    assert f_close > f_far


def test_force_symmetry():
    """Force(i,j) == Force(j,i)."""
    f1 = gravity_force(500000, 200000, 0.3, 0.155)
    f2 = gravity_force(200000, 500000, 0.3, 0.155)
    assert abs(f1 - f2) < 1e-6


def test_force_beta_effect():
    """Higher beta means distance matters more (for dist > 1)."""
    # With combined_dist > 1, higher beta penalizes distance more
    f_low_beta = gravity_force(100000, 100000, 2.0, 0.1)
    f_high_beta = gravity_force(100000, 100000, 2.0, 1.5)
    assert f_low_beta > f_high_beta


def test_force_positive():
    """Force is always positive."""
    f = gravity_force(50000, 75000, 0.3, 0.155)
    assert f > 0


# ── PEER FINDING LOGIC TESTS ───────────────────────────

def test_peer_ordering(sample_counties):
    """Most similar county should rank first."""
    target = sample_counties[0]  # poverty=0.8
    keys = ["poverty", "median_income", "unemployment", "broadband"]

    def sim(county):
        a = [target["datasets"][k] for k in keys]
        b = [county["datasets"][k] for k in keys]
        return -euclidean_dissim(a, b)

    peers = sorted([c for c in sample_counties if c["fips"] != target["fips"]], key=sim, reverse=True)
    # 01002 (all values differ by ~0.05) is closer than 54047 (differ by ~0.1)
    assert peers[0]["fips"] == "01002"
    # 54047 should be second (next most similar disadvantaged profile)
    assert peers[1]["fips"] == "54047"


def test_peer_self_exclusion(sample_counties):
    """A county should not appear in its own peer list."""
    target_fips = sample_counties[0]["fips"]
    peers = [c for c in sample_counties if c["fips"] != target_fips]
    assert target_fips not in [c["fips"] for c in peers]


# ── NORMALIZATION TESTS ─────────────────────────────────

def test_minmax_normalization():
    """Min-max normalization produces [0,1] range."""
    arr = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    normalized = (arr - arr.min()) / (arr.max() - arr.min())
    assert normalized.min() == 0.0
    assert normalized.max() == 1.0


def test_normalization_preserves_order():
    """Normalization preserves relative ordering."""
    values = np.array([5.0, 2.0, 8.0, 1.0, 9.0])
    normalized = (values - values.min()) / (values.max() - values.min())
    assert list(np.argsort(values)) == list(np.argsort(normalized))


# ── RELIABILITY SCORE TESTS ─────────────────────────────

def reliability_from_cv(cv, population):
    """Reliability score from coefficient of variation."""
    if population < 1000:
        pop_rel = 0.2
    elif population < 5000:
        pop_rel = 0.5
    elif population < 10000:
        pop_rel = 0.7
    elif population < 25000:
        pop_rel = 0.85
    else:
        pop_rel = 1.0

    if cv < 0.15:
        cv_rel = 1.0
    elif cv < 0.30:
        cv_rel = 1.0 - (cv - 0.15) / 0.15
    else:
        cv_rel = 0.0

    return min((cv_rel + pop_rel) / 2, pop_rel)


def test_reliability_high_pop_low_cv():
    """Large county with small MOE = high reliability."""
    r = reliability_from_cv(cv=0.05, population=500000)
    assert r >= 0.8


def test_reliability_tiny_county():
    """Tiny county always gets low reliability."""
    r = reliability_from_cv(cv=0.05, population=500)
    assert r <= 0.5


def test_reliability_high_cv():
    """High coefficient of variation = low reliability."""
    r = reliability_from_cv(cv=0.5, population=100000)
    assert r <= 0.5


def test_reliability_bounded():
    """Reliability always between 0 and 1."""
    for cv in [0.0, 0.1, 0.2, 0.5, 1.0]:
        for pop in [100, 1000, 10000, 100000]:
            r = reliability_from_cv(cv, pop)
            assert 0.0 <= r <= 1.0, f"Reliability {r} out of bounds for cv={cv}, pop={pop}"
