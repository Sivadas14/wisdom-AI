// Run: node tests/classify403.test.mjs   (see package.json "test:classify403")
//
// The bodies below are the REAL shapes the backend produces, not invented ones:
//   quota      -> wire.Error(code, message, details) in middlewares.py
//   deactivated-> HTTPException(403, detail=...) in dependencies.py:56-60
import { classify403 } from '../dist-test/classify403.js';

let pass = 0, fail = 0;
const check = (name, got, want) => {
    if (got === want) { console.log(`PASS  ${name}`); pass++; }
    else { console.log(`FAIL  ${name}: got ${got}, want ${want}`); fail++; }
};

// ── Quota: must NEVER sign the user out ─────────────────────────────────────
check('conversation limit', classify403({
    success: false, code: 'CONVERSATION_LIMIT_REACHED',
    message: 'You have reached your conversation limit.',
    details: { plan_name: 'Explore', limit: 20, used: 20, upgrade_required: true },
}), 'quota');

check('image limit', classify403({
    success: false, code: 'IMAGE_LIMIT_REACHED', message: 'Card limit reached.',
    details: { upgrade_required: true },
}), 'quota');

check('meditation duration limit', classify403({
    success: false, code: 'MEDITATION_DURATION_LIMIT_REACHED',
    message: 'Limit reached.', details: { upgrade_required: true },
}), 'quota');

check('feature not available', classify403({
    success: false, code: 'FEATURE_NOT_AVAILABLE',
    message: 'Audio is not enabled in your plan.',
    details: { upgrade_required: true, suggestion: 'Upgrade your plan or purchase an addon.' },
}), 'quota');

check('quota flagged only by details', classify403({
    details: { upgrade_required: true },
}), 'quota');

// The trap: quota prose that mentions being unable to continue must not be
// mistaken for a shutdown.
check('quota prose mentioning disabled', classify403({
    code: 'IMAGE_LIMIT_REACHED',
    message: 'Card generation is disabled until you upgrade.',
    details: { upgrade_required: true },
}), 'quota');

// ── Deactivation: the only case that may sign out ───────────────────────────
check('account deactivated', classify403({
    detail: 'Account deactivated. Please contact support.',
}), 'deactivated');

check('account suspended', classify403({ detail: 'Account suspended.' }), 'deactivated');

// ── Anything else: leave the session alone ──────────────────────────────────
check('unknown 403', classify403({ detail: 'Not permitted.' }), 'other');
check('empty body', classify403({}), 'other');
check('null body', classify403(null), 'other');
check('undefined body', classify403(undefined), 'other');
check('string body', classify403('nope'), 'other');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
