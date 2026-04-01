#!/usr/bin/env python3
"""
DiscoSights Full Pipeline Orchestrator
Runs all pipeline steps in sequence.
Safe to run on Railway worker or locally.
"""
import subprocess
import sys
import os
import time
from datetime import datetime


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

    # Print captured output
    if result.stdout:
        print(result.stdout[-2000:])
    if result.stderr:
        print("STDERR:", result.stderr[-2000:])

    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\n{status} -- {name} ({elapsed:.1f}s)")

    return result.returncode == 0


def run_pipeline(steps: list = None):
    """Run the full pipeline or a subset of steps. Returns True if all succeeded."""
    ALL_STEPS = [
        ("Beta Calibration (geo-only)", "data_pipeline/gravity/calibrate_beta.py"),
        ("Gravity Pipeline (full model + cache)", "data_pipeline/gravity/run_gravity_pipeline.py"),
        ("IRS Migration Validation", "data_pipeline/gravity/validate_against_migration.py"),
        ("Force Variants", "data_pipeline/gravity/compute_force_variants.py"),
        ("PCA Analysis", "data_pipeline/gravity/pca_analysis.py"),
        ("Terrain Generation", "data_pipeline/gravity/compute_terrain.py"),
        ("Pre-computed Layout", "data_pipeline/gravity/compute_layout.py"),
        ("Margins of Error", "data_pipeline/gravity/fetch_margins_of_error.py"),
        ("Methodology Document", "data_pipeline/gravity/generate_methodology.py"),
    ]

    if steps:
        run_steps = [(n, s) for n, s in ALL_STEPS if any(step in s for step in steps)]
    else:
        run_steps = ALL_STEPS

    print(f"\nDiscoSights Pipeline Orchestrator")
    print(f"Running {len(run_steps)} steps")
    print(f"Start: {datetime.now().isoformat()}")

    results = []
    for name, script in run_steps:
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
    args = parser.parse_args()

    success = run_pipeline(args.steps)
    sys.exit(0 if success else 1)
