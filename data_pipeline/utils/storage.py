"""Upload pipeline output files to Supabase Storage."""
import os

from dotenv import load_dotenv

load_dotenv()


def get_storage_client():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )


def upload_to_storage(local_path: str, storage_filename: str = None):
    """Upload a local file to the pipeline-cache bucket in Supabase Storage."""
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

    client.storage.from_('pipeline-cache').upload(
        storage_filename, data,
        file_options={'content-type': content_type}
    )

    url = client.storage.from_('pipeline-cache').get_public_url(storage_filename)
    size_kb = len(data) / 1024
    print(f"Uploaded to Storage: {storage_filename} ({size_kb:.1f} KB)")
    return url
