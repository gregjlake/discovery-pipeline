#!/usr/bin/env python3
"""
DiscoSights Pipeline Worker
Polls Supabase pipeline_jobs table for pending jobs and executes them.
Runs as a separate Railway service.
"""
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL = int(os.environ.get("WORKER_POLL_INTERVAL", "30"))


def get_client():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def claim_next_job(client):
    """Atomically claim the next pending job."""
    try:
        result = (
            client.table("pipeline_jobs")
            .select("*")
            .eq("status", "pending")
            .order("created_at")
            .limit(1)
            .execute()
        )
        if not result.data:
            return None

        job = result.data[0]
        client.table("pipeline_jobs").update(
            {"status": "running", "started_at": datetime.now().isoformat()}
        ).eq("id", job["id"]).eq("status", "pending").execute()

        return job
    except Exception as e:
        print(f"Error claiming job: {e}")
        return None


def complete_job(client, job_id: int, success: bool, error: str = None):
    client.table("pipeline_jobs").update(
        {
            "status": "completed" if success else "failed",
            "completed_at": datetime.now().isoformat(),
            "result": "success" if success else "failed",
            "error": error,
        }
    ).eq("id", job_id).execute()


def run_worker():
    print(f"DiscoSights Pipeline Worker starting...")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print(f"Time: {datetime.now().isoformat()}")

    client = get_client()

    while True:
        job = claim_next_job(client)

        if job:
            print(f"\nProcessing job {job['id']}")
            print(f"Triggered by: {job.get('triggered_by')}")
            print(f"Steps: {job.get('steps') or 'all'}")

            try:
                from data_pipeline.run_full_pipeline import run_pipeline
                import io, contextlib

                # Capture stdout/stderr for error reporting
                buf = io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                        success = run_pipeline(steps=job.get("steps"))
                except Exception as inner_e:
                    success = False
                    buf.write(f"\nException: {inner_e}")

                output = buf.getvalue()
                error_msg = output[-1000:] if not success else None  # last 1000 chars
                complete_job(client, job["id"], success, error_msg)
                print(f"Job {job['id']}: {'SUCCESS' if success else 'FAILED'}")
                if not success:
                    print(f"Output: {output[-500:]}")

                # Invalidate API memory cache after pipeline completes
                if success:
                    try:
                        import httpx
                        api_url = os.environ.get("API_URL", "http://localhost:8000")
                        admin_key = os.environ.get("ADMIN_KEY", "")
                        httpx.post(
                            f"{api_url}/api/admin/invalidate-cache",
                            headers={"X-Admin-Key": admin_key},
                            timeout=10,
                        )
                        print("API cache invalidated")
                    except Exception as e:
                        print(f"Cache invalidation skipped: {e}")

            except Exception as e:
                complete_job(client, job["id"], False, str(e))
                print(f"Job {job['id']} error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_worker()
