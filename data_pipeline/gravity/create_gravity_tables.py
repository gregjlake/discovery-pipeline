"""Create the 5 gravity model tables in Supabase via the PostgREST SQL endpoint."""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY not set in .env")
    sys.exit(1)

# Supabase exposes a SQL endpoint at /rest/v1/rpc for custom functions,
# but for DDL we use the pg-meta or direct SQL via the management API.
# The simplest reliable approach: use the supabase-py client to call
# a one-off RPC, or use the REST SQL endpoint.
# Supabase projects expose: {url}/rest/v1/rpc/{function_name}
# For DDL, we'll create a temporary function via the SQL editor approach
# using the postgrest "query" endpoint available on service_role.

SQL = """
-- 1. county_population
CREATE TABLE IF NOT EXISTS county_population (
    fips            TEXT PRIMARY KEY,
    county_name     TEXT NOT NULL,
    population      INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. county_migration_flows
CREATE TABLE IF NOT EXISTS county_migration_flows (
    origin_fips     TEXT NOT NULL,
    dest_fips       TEXT NOT NULL,
    flow            INTEGER NOT NULL,
    PRIMARY KEY (origin_fips, dest_fips)
);
CREATE INDEX IF NOT EXISTS idx_cmf_origin ON county_migration_flows (origin_fips);
CREATE INDEX IF NOT EXISTS idx_cmf_dest ON county_migration_flows (dest_fips);

-- 3. gravity_model_metadata
CREATE TABLE IF NOT EXISTS gravity_model_metadata (
    id                  TEXT PRIMARY KEY DEFAULT 'default',
    beta                FLOAT NOT NULL,
    alpha_origin        FLOAT,
    alpha_dest          FLOAT,
    pseudo_r2           FLOAT NOT NULL,
    aic                 FLOAT,
    n_pairs             INTEGER,
    calibration_year    TEXT,
    calibration_source  TEXT,
    model_type          TEXT,
    distance_type       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 4. gravity_nodes
CREATE TABLE IF NOT EXISTS gravity_nodes (
    fips            TEXT PRIMARY KEY,
    population      INTEGER NOT NULL,
    initial_lat     FLOAT NOT NULL,
    initial_lon     FLOAT NOT NULL
);

-- 5. gravity_links
CREATE TABLE IF NOT EXISTS gravity_links (
    source_fips                 TEXT NOT NULL,
    target_fips                 TEXT NOT NULL,
    force_strength_normalized   FLOAT NOT NULL,
    combined_dist               FLOAT NOT NULL,
    PRIMARY KEY (source_fips, target_fips)
);
CREATE INDEX IF NOT EXISTS idx_gl_source ON gravity_links (source_fips);
"""


def run_sql_via_rpc(sql: str) -> bool:
    """Execute SQL via Supabase by first creating a helper function, then calling it."""
    # Step 1: Create a temporary RPC function that executes arbitrary SQL
    create_fn = """
    CREATE OR REPLACE FUNCTION exec_sql(query text)
    RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    BEGIN
        EXECUTE query;
    END;
    $$;
    """
    # We need to bootstrap — call the SQL endpoint to create the function first.
    # Supabase service_role can call the pg-meta SQL endpoint.
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    # Try using the Supabase SQL API (available at /pg/sql for service_role)
    # This is the internal endpoint Supabase Studio uses.
    pg_url = SUPABASE_URL.replace(".supabase.co", ".supabase.co") + "/rest/v1/rpc/exec_sql"

    # First, try to create the exec_sql function via the rpc endpoint itself
    # If it doesn't exist yet, we need an alternative bootstrap method.

    # Alternative: use supabase-py's postgrest to test if exec_sql exists
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Try calling exec_sql — if it doesn't exist, create it via raw HTTP
    try:
        sb.rpc("exec_sql", {"query": "SELECT 1"}).execute()
        print("exec_sql function exists")
    except Exception:
        # Create it via the Supabase management API
        print("Creating exec_sql helper function...")
        # The Supabase REST API doesn't support DDL directly.
        # Use the database connection string approach instead.
        # But we can use the /pg endpoint available to service_role.
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=headers,
            json={"query": "SELECT 1"},
            timeout=10,
        )
        if resp.status_code == 404:
            # Function doesn't exist — we need to create it another way.
            # Try the Supabase pg-meta SQL endpoint
            print("Trying Supabase pg-meta endpoint...")
            pg_meta_url = SUPABASE_URL.replace("supabase.co", "supabase.co")
            resp2 = httpx.post(
                f"{pg_meta_url}/pg/query",
                headers={**headers, "Content-Type": "application/json"},
                json={"query": create_fn},
                timeout=15,
            )
            if resp2.status_code in (200, 201):
                print("exec_sql function created via pg-meta")
            else:
                print(f"pg-meta failed ({resp2.status_code}): {resp2.text[:200]}")
                return False

    # Now execute the DDL statements one by one
    statements = [s.strip() for s in SQL.split(";") if s.strip() and not s.strip().startswith("--")]
    success = 0
    for stmt in statements:
        try:
            sb.rpc("exec_sql", {"query": stmt}).execute()
            success += 1
        except Exception as e:
            print(f"  WARN: {str(e)[:100]}")
            # Try as individual statement
            try:
                resp = httpx.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    headers=headers,
                    json={"query": stmt},
                    timeout=10,
                )
                if resp.status_code in (200, 204):
                    success += 1
                else:
                    print(f"  Failed: {resp.status_code}")
            except Exception as e2:
                print(f"  Failed: {e2}")

    print(f"Executed {success}/{len(statements)} SQL statements")
    return success == len(statements)


def run_sql_direct() -> bool:
    """Execute SQL by connecting directly to the Supabase Postgres database."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not available, trying alternate method...")
        return False

    # Supabase direct connection: postgresql://postgres.[ref]:[password]@[host]:5432/postgres
    ref = SUPABASE_URL.split("//")[1].split(".")[0]
    conn_str = f"postgresql://postgres.{ref}:{SUPABASE_KEY}@db.{ref}.supabase.co:5432/postgres"
    try:
        conn = psycopg2.connect(conn_str, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SQL)
        cur.close()
        conn.close()
        print("All SQL executed via direct Postgres connection")
        return True
    except Exception as e:
        print(f"Direct connection failed: {e}")
        return False


def verify_tables():
    """Verify all 5 tables exist by querying them."""
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    tables = [
        "county_population",
        "county_migration_flows",
        "gravity_model_metadata",
        "gravity_nodes",
        "gravity_links",
    ]
    results = {}
    for t in tables:
        try:
            resp = sb.table(t).select("*", count="exact").limit(0).execute()
            results[t] = f"OK (count={resp.count})"
        except Exception as e:
            results[t] = f"FAIL: {str(e)[:80]}"

    print("\nTable verification:")
    all_ok = True
    for t, status in results.items():
        icon = "+" if "OK" in status else "X"
        print(f"  [{icon}] {t}: {status}")
        if "FAIL" in status:
            all_ok = False
    return all_ok


def main():
    print("Creating gravity tables in Supabase...\n")
    print(f"URL: {SUPABASE_URL[:40]}...")
    print(f"Key: {SUPABASE_KEY[:20]}...\n")

    # Try direct Postgres connection first (most reliable for DDL)
    if run_sql_direct():
        verify_tables()
        return

    # Fall back to RPC method
    print("\nTrying RPC method...")
    if run_sql_via_rpc(SQL):
        verify_tables()
        return

    # Last resort: print SQL for manual execution
    print("\n" + "=" * 60)
    print("AUTOMATIC CREATION FAILED")
    print("=" * 60)
    print("Please run this SQL manually in the Supabase SQL Editor:\n")
    print(SQL)
    print("\nThen re-run this script to verify.")

    # Still try to verify (tables may already exist)
    verify_tables()


if __name__ == "__main__":
    main()
