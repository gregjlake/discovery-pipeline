#!/usr/bin/env python3
"""
DiscoSights Pipeline Worker
Polls Supabase pipeline_jobs table for pending jobs and executes them.
Supports phased execution: each phase runs as a separate job to avoid
Railway CPU/memory timeouts. After each phase completes, the next phase
is auto-queued.
"""
import os
import sys
import time
from datetime import datetime, timezone

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
            {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", job["id"]).eq("status", "pending").execute()

        return job
    except Exception as e:
        print(f"Error claiming job: {e}")
        return None


def complete_job(client, job_id: int, success: bool, error: str = None):
    """Mark job complete and auto-queue next phase if applicable."""
    # Get current job details for phase info
    try:
        result = client.table("pipeline_jobs").select("phase,total_phases,triggered_by").eq("id", job_id).execute()
        job_data = result.data[0] if result.data else {}
    except Exception:
        job_data = {}

    current_phase = job_data.get("phase") or 1
    total_phases = job_data.get("total_phases") or 1

    client.table("pipeline_jobs").update(
        {
            "status": "completed" if success else "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": "success" if success else "failed",
            "error": error,
        }
    ).eq("id", job_id).execute()

    if not success:
        print(f"Phase {current_phase} failed -- stopping pipeline")
        return

    # Auto-queue next phase
    if current_phase < total_phases:
        next_phase = current_phase + 1
        client.table("pipeline_jobs").insert({
            "status": "pending",
            "phase": next_phase,
            "total_phases": total_phases,
            "triggered_by": f"auto-phase-{next_phase}",
        }).execute()
        print(f"Auto-queued Phase {next_phase}/{total_phases}")
    else:
        print(f"All {total_phases} phases complete")
        invalidate_api_cache()


def invalidate_api_cache():
    """Tell the API service to drop its in-memory cache."""
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


def run_worker():
    print(f"DiscoSights Pipeline Worker starting...")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    client = get_client()

    while True:
        job = claim_next_job(client)

        if job:
            phase = job.get("phase") or None
            total = job.get("total_phases") or 1
            print(f"\nProcessing job {job['id']} (phase {phase or 'all'}/{total})")
            print(f"Triggered by: {job.get('triggered_by')}")

            try:
                from data_pipeline.run_full_pipeline import run_pipeline
                import io, sys as _sys

                old_stdout, old_stderr = _sys.stdout, _sys.stderr
                buf = io.StringIO()
                _sys.stdout = buf
                _sys.stderr = buf
                try:
                    success = run_pipeline(
                        steps=job.get("steps"),
                        phase=phase,
                    )
                finally:
                    _sys.stdout, _sys.stderr = old_stdout, old_stderr

                output = buf.getvalue()
                error_msg = output[-2000:] if not success else None
                complete_job(client, job["id"], success, error_msg)
                old_stdout.write(f"Job {job['id']}: {'SUCCESS' if success else 'FAILED'}\n")
                if not success:
                    old_stdout.write(f"Output:\n{output[-1000:]}\n")

            except Exception as e:
                complete_job(client, job["id"], False, str(e))
                print(f"Job {job['id']} error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_worker()
