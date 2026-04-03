#!/usr/bin/env python3
"""
DiscoSights Full Pipeline Orchestrator
Runs pipeline steps in phases. Each phase runs as a separate worker job
to avoid Railway CPU/memory timeouts on the full 10-step pipeline.
"""
import subprocess
import sys
import os
import time
from datetime import datetime


PIPELINE_PHASES = {
    1: [
        ("Beta Calibration", "data_pipeline/gravity/calibrate_beta.py"),
        ("Gravity Pipeline", "data_pipeline/gravity/run_gravity_pipeline.py"),
        ("IRS Validation", "data_pipeline/gravity/validate_against_migration.py"),
    ],
    2: [
        ("Force Variants", "data_pipeline/gravity/compute_force_variants.py"),
        ("PCA Analysis", "data_pipeline/gravity/pca_analysis.py"),
        ("County Clusters", "data_pipeline/gravity/compute_county_clusters.py"),
        ("Correlation Insights", "data_pipeline/gravity/compute_correlation_insights.py"),
    ],
    3: [
        ("Terrain", "data_pipeline/gravity/compute_terrain.py"),
        ("KNN Baseline", "data_pipeline/gravity/compute_knn_baseline.py"),
    ],
    4: [
        ("Layout", "data_pipeline/gravity/compute_layout.py"),
        ("Margins of Error", "data_pipeline/gravity/fetch_margins_of_error.py"),
        ("Methodology", "data_pipeline/gravity/generate_methodology.py"),
    ],
}


def run_step(name: str, script: str):
    """Run a pipeline step and return success/failure."""
    print(f"\n{'='*60}")
    print(f"STEP: {name}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    elapsed = time.time() - start

    if result.stdout:
        print(result.stdout[-2000:])
    if result.stderr:
        print("STDERR:", result.stderr[-2000:])

    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\n{status} -- {name} ({elapsed:.1f}s)")

    return result.returncode == 0


def run_pipeline(steps: list = None, phase: int = None):
    """Run the full pipeline, a single phase, or specific steps. Returns True if all succeeded."""
    if phase is not None:
        all_steps = PIPELINE_PHASES.get(phase, [])
        label = f"Phase {phase}/{len(PIPELINE_PHASES)}"
    elif steps:
        flat = [item for p in sorted(PIPELINE_PHASES.keys()) for item in PIPELINE_PHASES[p]]
        all_steps = [(n, s) for n, s in flat if any(step in s for step in steps)]
        label = f"Custom steps ({len(all_steps)})"
    else:
        all_steps = [item for p in sorted(PIPELINE_PHASES.keys()) for item in PIPELINE_PHASES[p]]
        label = f"Full pipeline ({len(all_steps)} steps)"

    print(f"\nDiscoSights Pipeline Orchestrator")
    print(f"Running: {label}")
    print(f"Start: {datetime.now().isoformat()}")

    results = []
    for name, script in all_steps:
        if not os.path.exists(script):
            print(f"SKIP: {script} not found")
            continue
        success = run_step(name, script)
        results.append((name, success))
        if not success:
            print(f"\nPipeline FAILED at: {name}")
            print("Stopping here -- fix the error and rerun")
            break

    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {status} {name}")

    all_passed = all(s for _, s in results)
    print(f"\nResult: {'ALL PASSED' if all_passed else 'FAILED'}")
    print(f"End: {datetime.now().isoformat()}")

    return all_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", nargs="+", help="Run specific steps (by script name fragment)")
    parser.add_argument("--phase", type=int, help="Run a specific phase (1-4)")
    args = parser.parse_args()

    success = run_pipeline(args.steps, phase=args.phase)
    sys.exit(0 if success else 1)
