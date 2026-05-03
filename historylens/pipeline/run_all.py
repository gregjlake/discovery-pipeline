"""Run all pipeline phases in sequence."""
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).parent
PHASES = [
    "01_ingest.py",
    "02_harmonize.py",
    "03_normalize.py",
    "04_peers.py",
    "05_validate.py",
    "06_export.py",
]


def main():
    py = sys.executable
    for phase in PHASES:
        path = PIPELINE / phase
        sys.stdout.write("\n" + "#" * 72 + "\n")
        sys.stdout.write(f"# Running {phase}\n")
        sys.stdout.write("#" * 72 + "\n")
        sys.stdout.flush()
        result = subprocess.run([py, str(path)], cwd=str(PIPELINE))
        if result.returncode != 0:
            print(f"\n[ERROR] {phase} exited with code {result.returncode}")
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
