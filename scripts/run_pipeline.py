import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from validate.checks import validate_dataset

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

DATASETS = [
    ('library',   'ingest.imls',        'IMLS Public Libraries Survey'),
    ('mobility',  'ingest.opportunity',  'Opportunity Atlas'),
    ('air',       'ingest.epa',          'EPA Air Quality Index'),
    ('broadband', 'ingest.fcc',          'Census ACS Broadband'),
]

# Columns to upload per dataset (excluding fips and year)
VALUE_COLUMNS = {
    'library':   ['library_spend_per_capita', 'n_libraries'],
    'mobility':  ['mobility_rank_p25'],
    'air':       ['air_clean_score', 'air_quality_inv'],
    'broadband': ['broadband_rate'],
}


def _get_supabase():
    """Initialize Supabase client from env vars."""
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        print("  WARNING: SUPABASE_URL or SUPABASE_SERVICE_KEY not set — skipping Supabase upload")
        return None
    from supabase import create_client
    return create_client(url, key)


def _upload_to_supabase(sb, dataset_id, df, provenance):
    """Write dataset rows to raw_values and provenance to provenance table."""
    columns = VALUE_COLUMNS.get(dataset_id, [])

    # Build raw_values rows: one row per fips per column
    rows = []
    for _, row in df.iterrows():
        fips = row['fips']
        year = int(row.get('year', 2022))
        for col in columns:
            if col in row and row[col] is not None and str(row[col]) != 'nan':
                rows.append({
                    'fips': fips,
                    'dataset_id': dataset_id,
                    'year': year,
                    'value': float(row[col]),
                    'column_name': col,
                })

    if not rows:
        print("  WARNING: No rows to upload")
        return

    # Upsert in batches of 1000 (Supabase has payload limits)
    batch_size = 1000
    total_upserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sb.table('raw_values').upsert(
            batch,
            on_conflict='fips,dataset_id,column_name',
        ).execute()
        total_upserted += len(batch)

    print(f"  Supabase: upserted {total_upserted} raw_values rows")

    # Write provenance record
    prov_row = {
        'dataset_id': provenance['dataset_id'],
        'source_name': provenance['source_name'],
        'source_url': provenance['source_url'],
        'download_date': provenance['download_date'],
        'file_hash': provenance['file_hash'],
        'row_count': provenance['row_count'],
        'counties_matched': provenance['counties_matched'],
        'notes': provenance.get('notes', ''),
    }
    sb.table('provenance').insert(prov_row).execute()
    print(f"  Supabase: inserted provenance record")


def main():
    parser = argparse.ArgumentParser(description='Run the discovery data pipeline')
    parser.add_argument('--dry-run', action='store_true', help='Skip downloads, just print what would run')
    parser.add_argument('--no-supabase', action='store_true', help='Skip Supabase upload, only save parquet')
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN — no downloads will be performed ===\n")
        for dataset_id, module_path, name in DATASETS:
            print(f"  [{dataset_id}] {name}")
            print(f"    module: {module_path}.ingest()")
            print(f"    validate: validate_dataset(df, '{dataset_id}')")
            print()
        print(f"Total datasets: {len(DATASETS)}")
        return

    # Initialize Supabase client (if not skipped)
    sb = None
    if not args.no_supabase:
        sb = _get_supabase()

    # Ensure data/ dir exists for parquet fallback
    data_dir = Path(__file__).resolve().parent.parent / 'data'
    data_dir.mkdir(exist_ok=True)

    results = []

    for dataset_id, module_path, name in DATASETS:
        print(f"\n{'='*60}")
        print(f"Ingesting: {name} ({dataset_id})")
        print('='*60)
        try:
            module = __import__(module_path, fromlist=['ingest'])
            df, provenance = module.ingest()
            print(f"  Downloaded: {provenance['row_count']} rows, {provenance['counties_matched']} counties")
            print(f"  Hash: {provenance['file_hash'][:16]}...")

            issues = validate_dataset(df, dataset_id)
            if issues:
                print(f"  Validation issues:")
                for issue in issues:
                    print(f"    - {issue}")
            else:
                print(f"  Validation: PASSED")

            # Save parquet (always, as fallback)
            import json
            df.to_parquet(data_dir / f'{dataset_id}.parquet', index=False)
            with open(data_dir / f'{dataset_id}_provenance.json', 'w') as f:
                json.dump(provenance, f, indent=2)
            print(f"  Parquet: saved to data/{dataset_id}.parquet")

            # Upload to Supabase
            if sb:
                try:
                    _upload_to_supabase(sb, dataset_id, df, provenance)
                except Exception as e:
                    print(f"  Supabase ERROR: {e}")

            results.append((dataset_id, name, df['fips'].nunique(), issues))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((dataset_id, name, 0, [str(e)]))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"{'Dataset':<12} {'Counties':>8}  Issues")
    print('-'*45)
    for dataset_id, name, county_count, issues in results:
        issue_str = '; '.join(issues) if issues else 'OK'
        print(f"{dataset_id:<12} {county_count:>8}  {issue_str}")


if __name__ == '__main__':
    main()
