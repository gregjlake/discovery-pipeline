"""Upload pipeline output files to Supabase Storage with upsert and retry."""
import os
import time

from dotenv import load_dotenv

load_dotenv()


def get_storage_client():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )


def upload_to_storage(local_path: str, storage_filename: str = None):
    """Upload a local file to the pipeline-cache bucket with upsert and exponential backoff."""
    if storage_filename is None:
        storage_filename = os.path.basename(local_path)

    client = get_storage_client()

    with open(local_path, 'rb') as f:
        data = f.read()

    if local_path.endswith('.json'):
        content_type = 'application/json'
    elif local_path.endswith('.md'):
        content_type = 'text/markdown'
    elif local_path.endswith('.csv'):
        content_type = 'text/csv'
    else:
        content_type = 'application/octet-stream'

    size_kb = len(data) / 1024

    # Upload with upsert and exponential backoff
    last_error = None
    for attempt in range(5):
        try:
            client.storage.from_('pipeline-cache').upload(
                storage_filename, data,
                file_options={'content-type': content_type, 'upsert': 'true'}
            )
            print(f"  Uploaded to Storage: {storage_filename} ({size_kb:.1f} KB)")
            return
        except Exception as e:
            last_error = e
            if attempt < 4:
                wait = 10 * (2 ** attempt)
                print(f"  Upload attempt {attempt+1}/5 failed for {storage_filename}, retrying in {wait}s: {e}")
                time.sleep(wait)

    raise Exception(f"Storage upload FAILED for {storage_filename} after 5 attempts: {last_error}")
