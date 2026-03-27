"""Download all four datasets and save as parquet files in data/."""
import os
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

DATASETS = [
    ('library',   'ingest.imls'),
    ('mobility',  'ingest.opportunity'),
    ('air',       'ingest.epa'),
    ('broadband', 'ingest.fcc'),
]


def main():
    DATA_DIR.mkdir(exist_ok=True)

    for dataset_id, module_path in DATASETS:
        print(f"Ingesting {dataset_id}...")
        module = __import__(module_path, fromlist=['ingest'])
        df, provenance = module.ingest()

        parquet_path = DATA_DIR / f'{dataset_id}.parquet'
        df.to_parquet(parquet_path, index=False)
        print(f"  Saved {parquet_path} ({len(df)} rows, {df['fips'].nunique()} counties)")

        prov_path = DATA_DIR / f'{dataset_id}_provenance.json'
        with open(prov_path, 'w') as f:
            json.dump(provenance, f, indent=2)
        print(f"  Saved {prov_path}")

    print("\nDone.")


if __name__ == '__main__':
    main()
