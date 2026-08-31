// ============================================================
// What a 403 actually means
// ============================================================
//
// A 403 from this API is one of two very different things, and treating them
// the same was signing people out of their accounts.
//
//   QUOTA — the middlewares in backend/src/middlewares.py return 403 when a
//   plan limit is reached: CONVERSATION_LIMIT_REACHED, IMAGE_LIMIT_REACHED,
//   MEDITATION_DURATION_LIMIT_REACHED, FEATURE_NOT_AVAILABLE. They use
//   wire._ErrorResponse, so the body has a top-level `code` and a `details`
//   object carrying `upgrade_required: true`.
//
//   DEACTIVATED — get_current_user (backend/src/dependencies.py:56-60) raises
//   HTTPException(403, detail="Account deactivated. Please contact support.").
//   FastAPI renders that as {"detail": "..."}.
//
// The old handler signed out and redirected to /signin?error=deactivated on
// BOTH. A seeker who reached their conversation limit was logged out and told
// their account had been disabled.
//
// Signing someone out wrongly is much worse than showing the wrong error
// message, so deactivation has to be positively identified. Anything
// unrecognised is passed back to the caller untouched, and the session is left
// alone.

export type Verdict403 = 'quota' | 'deactivated' | 'other';

export function classify403(body: unknown): Verdict403 {
    const b = (body ?? {}) as Record<string, any>;

    const detail = typeof b.detail === 'string' ? b.detail : '';
    const message = typeof b.message === 'string' ? b.message : '';
    const code = String(b.code ?? '');

    // Quota first: a quota response can also carry prose that happens to
    // mention being unable to continue, and must never be read as a shutdown.
    if (
        b?.details?.upgrade_required === true ||
        b?.upgrade_required === true ||
        /LIMIT_REACHED|FEATURE_NOT_AVAILABLE|QUOTA/i.test(code)
    ) {
        return 'quota';
    }

    if (/deactivat|disabled|suspended/i.test(`${detail} ${message}`)) {
        return 'deactivated';
    }

    return 'other';
}
