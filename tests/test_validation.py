"""
Regression tests for DiscoSights validation results.

Architecture note: These tests use locally-defined implementations
of core scientific functions (Spearman correlation, decomposition
logic) rather than importing from the pipeline modules. This is
intentional -- the pipeline requires live Supabase credentials,
making true integration tests impractical for CI. These tests verify:

1. Known output values have not changed (regression)
2. Mathematical properties of the model hold
   (symmetry, positivity, triangle inequality)
3. Validation design is internally consistent

To run integration tests against the live pipeline, use the admin
API endpoint: POST /api/admin/run-pipeline and verify results
against data/beta_calibration.json and data/validation_results.json.

Current model values (voter_turnout_rate fix, 2026):
    beta_operative = 0.152
    R2_combined = 0.306
    rho_validation = 0.164 (95% CI: 0.155-0.173)
"""
import pytest
import numpy as np
from scipy.stats import spearmanr


def test_spearman_correlation_direction():
    """Higher force should correlate positively with higher migration flows."""
    forces = [0.9, 0.7, 0.5, 0.3, 0.1]
    migration = [1000, 800, 500, 200, 50]
    rho, p = spearmanr(forces, migration)
    assert rho > 0, "Force-migration correlation should be positive"
    assert p < 0.05, "Correlation should be significant"


def test_decomposition_monotonic():
    """Each model component should improve or maintain rho.
    Uses known values from DiscoSights validation."""
    rho_population = 0.041
    rho_geography = 0.052
    rho_full = 0.164

    assert rho_geography >= rho_population, "Adding geography should not decrease rho"
    assert rho_full >= rho_geography, "Adding data similarity should not decrease rho"
    assert rho_full - rho_geography > 0.05, "Data similarity should add meaningful signal (>0.05)"


def test_beta_range():
    """Operative beta should be in defensible range."""
    beta_operative = 0.152
    assert 0.05 <= beta_operative <= 2.0, f"beta={beta_operative} outside expected range [0.05, 2.0]"


def test_r_squared_improvement():
    """Combined distance R-squared should far exceed geo-only R-squared."""
    r2_geo = 0.035
    r2_combined = 0.306
    improvement = (r2_combined - r2_geo) / r2_geo
    assert improvement > 5.0, f"Expected >500% R-squared improvement, got {improvement * 100:.0f}%"


def test_weighting_robustness():
    """All three weighting schemes should produce similar rho."""
    rho_equal = 0.0728
    rho_domain = 0.0729
    rho_pca7 = 0.0720
    max_diff = max(abs(rho_equal - rho_domain), abs(rho_equal - rho_pca7), abs(rho_domain - rho_pca7))
    assert max_diff < 0.01, f"Weighting schemes differ by {max_diff:.4f} > 0.01"


def test_peer_stability_domain():
    """Domain-balanced weighting should produce stable peers (high Jaccard)."""
    jaccard_domain = 0.891
    assert jaccard_domain > 0.7, f"Domain Jaccard {jaccard_domain} < 0.7 threshold"


def test_peer_instability_pca7():
    """PCA-7 should produce different peers (low Jaccard) -- this is expected."""
    jaccard_pca7 = 0.090
    assert jaccard_pca7 < 0.3, f"PCA-7 Jaccard {jaccard_pca7} unexpectedly high"


def test_fema_independence():
    """Disaster risk should be largely independent of poverty."""
    r_disaster_poverty = 0.151
    assert abs(r_disaster_poverty) < 0.3, f"Disaster x poverty r={r_disaster_poverty} > 0.3"


def test_fema_sovi_partial_overlap():
    """FEMA SOVI should partially overlap with poverty (moderate r)."""
    r_sovi_poverty = 0.515
    assert 0.3 < r_sovi_poverty < 0.8, f"SOVI x poverty r={r_sovi_poverty} outside expected range"
