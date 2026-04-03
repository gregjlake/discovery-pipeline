"""Environment/EJ data ingest -- deferred due to EPA data complexity."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    print("\n=== ENVIRONMENTAL JUSTICE DATA ===")
    print("  EPA EJScreen requires block-group-to-county aggregation from bulk CSV (~4GB).")
    print("  EPA TRI county-level aggregates require FTP parsing with custom year filters.")
    print("  CDC PLACES does not include environmental health measures at county level.")
    print("  Status: DEFERRED -- will add in Wave 3.1 with bulk EPA download pipeline.")
    print()
    print("  Candidates for future ingestion:")
    print("    - EJScreen cancer risk (air toxics)")
    print("    - TRI total releases per capita")
    print("    - Superfund sites per county")


if __name__ == "__main__":
    main()
