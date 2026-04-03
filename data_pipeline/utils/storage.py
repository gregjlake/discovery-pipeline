"""Upload pipeline output files to Supabase Storage with retry."""
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
    """Upload a local file to the pipeline-cache bucket with exponential backoff retry."""
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

    try:
        client.storage.from_('pipeline-cache').remove([storage_filename])
    except Exception:
        pass

    # Upload with exponential backoff (handles transient Supabase 502s)
    last_error = None
    for attempt in range(5):
        try:
            client.storage.from_('pipeline-cache').upload(
                storage_filename, data,
                file_options={'content-type': content_type}
            )
            url = client.storage.from_('pipeline-cache').get_public_url(storage_filename)
            size_kb = len(data) / 1024
            print(f"Uploaded to Storage: {storage_filename} ({size_kb:.1f} KB)")
            return url
        except Exception as e:
            last_error = e
            if attempt < 4:
                wait = 30 * (2 ** attempt)
                print(f"Upload failed attempt {attempt+1}/5, retrying in {wait}s: {e}")
                time.sleep(wait)

    raise Exception(f"Upload failed after 5 attempts: {last_error}")
