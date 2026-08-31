"""Helpers for marking ContentGeneration status from background tasks.

Step 2 of the video pipeline rebuild: these helpers make failures observable.
Previously, exceptions inside background tasks were logged-and-raised while the
ContentGeneration row was left with `content_path=None` forever — so the UI
just kept showing a spinner. Now every background task explicitly writes
'complete' or 'failed' to the row so the frontend can render the correct state.
"""

from src.llm_shim import tu
from sqlalchemy import select

from src.db import ContentGeneration, get_background_session


# Keep error messages bounded but large enough to include the tail of a
# subprocess stderr (where the actual error usually lives). We keep both
# the head (tells us which code path failed) and the tail (tells us why).
_MAX_ERROR_LENGTH = 2000


def _truncate_preserving_ends(text: str, max_len: int) -> str:
    """Truncate text keeping both ends so we retain context + cause."""
    if len(text) <= max_len:
        return text
    head = max_len // 3
    tail = max_len - head - 20  # leave room for the "... [truncated] ..." marker
    return f"{text[:head]}\n...[truncated]...\n{text[-tail:]}"


async def mark_content_failed(content_id: str, error: Exception | str) -> None:
    """Open a fresh DB session and set status='failed' + error_message.

    Uses its own session because the caller's session is typically rolled back
    by the exception that brought us here. Never raises — if we cannot write
    the failure, we log and move on (the task is already dead at that point).
    """
    error_text = _truncate_preserving_ends(str(error), _MAX_ERROR_LENGTH)

    try:
        async with get_background_session() as session:
            query = select(ContentGeneration).where(ContentGeneration.id == content_id)
            result = await session.execute(query)
            row = result.scalar_one_or_none()
            if not row:
                tu.logger.warning(
                    f"mark_content_failed: no ContentGeneration row for {content_id}"
                )
                return
            row.status = "failed"
            row.error_message = error_text
            await session.commit()
            tu.logger.info(
                f"Marked content {content_id} as failed: {error_text[:120]}"
            )

            # Give the credits back. This is the one place every generation
            # failure passes through, which is exactly why the refund belongs
            # here rather than at each of the several places that can fail.
            #
            # Safe to reach twice: refund_for_generation reads the original
            # debit and is guarded by UNIQUE (content_generation_id, REFUND),
            # so a retried failure handler cannot pay out twice. It is also a
            # no-op when nothing was charged — admins, trials, legacy plans and
            # contemplation cards all reach here with no debit to reverse.
            try:
                from src.services.credits import refund_for_generation

                await refund_for_generation(
                    content_id, session, note="Generation failed"
                )
            except Exception as credit_ex:      # noqa: BLE001
                # A failed refund must be loud: the seeker has been charged for
                # something they did not get, and only the log will say so.
                tu.logger.error(
                    f"[CREDITS] REFUND FAILED for {content_id} — a seeker has "
                    f"been charged for a generation that did not complete: "
                    f"{credit_ex}"
                )
    except Exception as ex:
        # Never raise from the failure-recorder; if this fails we lose
        # observability but the request is already doomed.
        tu.logger.error(
            f"mark_content_failed: could not record failure for {content_id}: {ex}"
        )
