"""
Storage cleanup service — keeps Supabase storage within the 1.1 GB free-tier limit.

Folders in the 'generations' bucket and their retention policy:
  guest-cards/    — guest one-off cards   → delete files older than  1 day
  guest-audio/    — guest one-off audio   → delete files older than  1 day
  guest-video/    — guest one-off video   → delete files older than  1 day
  contemplation-cards/  — user cards      → delete if NOT in content_generations DB
  meditation-audio/     — user audio      → delete if NOT in content_generations DB
  meditation-videos/    — user video      → delete if NOT in content_generations DB
  ramana-library/       — source images   → NEVER delete (required for card generation)

The source-files bucket (original PDFs) is NEVER touched by this cleanup.

Safe to run multiple times — all operations are idempotent.
Errors in one folder never abort cleanup of other folders.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ── Retention config ───────────────────────────────────────────────────────────
GUEST_FOLDERS = ["guest-cards", "guest-audio", "guest-video"]
GUEST_MAX_AGE_DAYS = 1          # delete guest files after 1 day
USER_FOLDERS = [
    "contemplation-cards",
    "meditation-audio",
    "meditation-videos",
]
# User folders: also delete files older than MAX_AGE_DAYS even if they ARE in DB
# (keeps storage manageable; users can regenerate content)
USER_MAX_AGE_DAYS = 60          # delete user files older than 60 days


# ── Internal helpers ───────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    logger.info(f"[CLEANUP] {msg}")


def _warn(msg: str) -> None:
    logger.warning(f"[CLEANUP] {msg}")


async def _list_folder(session, bucket: str, folder: str) -> list[dict]:
    """
    Return all objects in storage.objects for a given bucket + folder prefix.
    Returns list of dicts: {name, created_at}.
    """
    from sqlalchemy import text as sql_text

    try:
        result = await session.execute(sql_text("""
            SELECT
                name,
                created_at
            FROM storage.objects
            WHERE bucket_id = :bucket
              AND name LIKE :prefix
            ORDER BY created_at ASC
        """), {"bucket": bucket, "prefix": f"{folder}/%"})
        rows = result.fetchall()
        return [{"name": row.name, "created_at": row.created_at} for row in rows]
    except Exception as e:
        _warn(f"Failed to list {bucket}/{folder}: {e}")
        return []


async def _delete_files(spb_client, bucket: str, paths: list[str]) -> int:
    """
    Delete a list of storage paths using the Supabase admin client.
    Returns the number of successfully queued deletes.
    Batches into chunks of 100 to avoid request-size limits.
    """
    if not paths:
        return 0

    deleted = 0
    BATCH = 100
    for i in range(0, len(paths), BATCH):
        batch = paths[i : i + BATCH]
        try:
            await asyncio.to_thread(
                spb_client.storage.from_(bucket).remove, batch
            )
            deleted += len(batch)
            _log(f"Deleted batch of {len(batch)} files from {bucket}")
        except Exception as e:
            _warn(f"Batch delete failed for {bucket} (offset {i}): {e}")
    return deleted


# ── Main cleanup functions ─────────────────────────────────────────────────────

async def _cleanup_guest_folders(session, spb_client) -> int:
    """Delete all guest-* files older than GUEST_MAX_AGE_DAYS."""
    total_deleted = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=GUEST_MAX_AGE_DAYS)

    for folder in GUEST_FOLDERS:
        files = await _list_folder(session, "generations", folder)
        to_delete = []
        for f in files:
            created = f["created_at"]
            # Supabase stores as timezone-aware datetime; normalise just in case
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created < cutoff:
                    to_delete.append(f["name"])

        _log(f"{folder}: {len(files)} files total, {len(to_delete)} older than {GUEST_MAX_AGE_DAYS}d → deleting")
        if to_delete:
            deleted = await _delete_files(spb_client, "generations", to_delete)
            total_deleted += deleted

    return total_deleted


async def _get_active_content_paths(session) -> set[str]:
    """
    Return the set of content_path values in content_generations that still
    have a valid (non-NULL) path. These are the files we must NOT delete.
    """
    from sqlalchemy import text as sql_text

    try:
        result = await session.execute(sql_text("""
            SELECT content_path
            FROM content_generations
            WHERE content_path IS NOT NULL
        """))
        return {row[0] for row in result.fetchall()}
    except Exception as e:
        _warn(f"Could not fetch active content paths: {e}")
        return set()


async def _cleanup_user_folders(session, spb_client) -> int:
    """
    Delete user-content files that are:
      (a) NOT referenced in content_generations.content_path  (orphaned), OR
      (b) Older than USER_MAX_AGE_DAYS (expired — user can regenerate).
    """
    total_deleted = 0
    active_paths = await _get_active_content_paths(session)
    cutoff = datetime.now(timezone.utc) - timedelta(days=USER_MAX_AGE_DAYS)

    for folder in USER_FOLDERS:
        files = await _list_folder(session, "generations", folder)
        to_delete = []
        for f in files:
            path = f["name"]
            created = f["created_at"]
            if created is not None and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            orphaned = path not in active_paths
            expired = (created is not None and created < cutoff)

            if orphaned or expired:
                reason = "orphaned" if orphaned else f"expired>{USER_MAX_AGE_DAYS}d"
                logger.debug(f"[CLEANUP] Marking {path} for deletion ({reason})")
                to_delete.append(path)

        _log(
            f"{folder}: {len(files)} files total, "
            f"{len(to_delete)} to delete "
            f"(orphaned or >{USER_MAX_AGE_DAYS} days old)"
        )
        if to_delete:
            deleted = await _delete_files(spb_client, "generations", to_delete)
            total_deleted += deleted

    return total_deleted


async def run_storage_cleanup(session_factory) -> dict:
    """
    Entry point: run all cleanup passes.
    Returns a summary dict for logging.

    Call from server startup (after migrations) and from the daily background task.
    """
    from src.settings import get_supabase_admin_client, get_settings

    _log("============================================================")
    _log("  Storage cleanup starting")
    _log("============================================================")

    summary = {
        "guest_deleted": 0,
        "user_deleted": 0,
        "errors": [],
    }

    try:
        settings = get_settings()
        spb_client = get_supabase_admin_client(settings)
    except Exception as e:
        _warn(f"Could not create Supabase admin client: {e}")
        summary["errors"].append(f"supabase_client: {e}")
        return summary

    async with session_factory() as session:
        # 1. Guest folders (aggressive — 1 day TTL)
        try:
            n = await _cleanup_guest_folders(session, spb_client)
            summary["guest_deleted"] = n
            _log(f"Guest folders: {n} files deleted")
        except Exception as e:
            _warn(f"Guest folder cleanup failed: {e}")
            summary["errors"].append(f"guest: {e}")

        # 2. User folders (orphaned + 60-day expiry)
        try:
            n = await _cleanup_user_folders(session, spb_client)
            summary["user_deleted"] = n
            _log(f"User folders: {n} files deleted")
        except Exception as e:
            _warn(f"User folder cleanup failed: {e}")
            summary["errors"].append(f"user: {e}")

    total = summary["guest_deleted"] + summary["user_deleted"]
    _log(f"Cleanup complete. Total deleted: {total} files.")
    _log("============================================================")
    return summary


async def run_daily_storage_cleanup_loop(session_factory) -> None:
    """
    Background loop that runs storage cleanup once per day.
    Designed to be launched as an asyncio task from server.py lifespan.
    Runs first cleanup after a 60-second warm-up delay, then every 24 hours.
    """
    _log("Daily cleanup loop starting (first run in 60s)...")
    await asyncio.sleep(60)  # let DB / migrations settle after startup

    while True:
        try:
            summary = await run_storage_cleanup(session_factory)
            _log(
                f"Daily cleanup done: "
                f"guest={summary['guest_deleted']} user={summary['user_deleted']} "
                f"errors={summary['errors']}"
            )
        except Exception as e:
            _warn(f"Daily cleanup loop error: {e}")

        # Sleep 24 hours before next run
        await asyncio.sleep(24 * 60 * 60)
