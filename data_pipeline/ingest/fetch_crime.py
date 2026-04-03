"""Crime data ingest -- deferred due to FBI UCR API constraints."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    print("\n=== CRIME DATA ===")
    print("  Crime data deferred -- FBI UCR API requires registration and has")
    print("  significant county coverage gaps (~15-20% missing).")
    print("  Will add in Wave 3.1 with proper API key and coverage analysis.")
    print("  Status: DEFERRED")


if __name__ == "__main__":
    main()
