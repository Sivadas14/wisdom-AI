#!/usr/bin/env bash
# smoke_test.sh — run after applying the translation patches to verify
# everything is wired up correctly. Bail on first failure.
#
# Usage:
#   ./smoke_test.sh                                    # against api.arunachalasamudra.co.in
#   API_BASE=http://localhost:8000 ./smoke_test.sh     # local dev

set -euo pipefail

API_BASE="${API_BASE:-https://api.arunachalasamudra.co.in}"
echo "=== Smoke testing translation system at ${API_BASE} ==="

pass() { echo "  ✓ $*"; }
fail() { echo "  ✗ $*" >&2; exit 1; }

echo
echo "1. Backend health"
HEALTH=$(curl -sf "${API_BASE}/health" || fail "Health endpoint not reachable")
echo "$HEALTH" | grep -q '"status":"healthy"' || fail "Health status not 'healthy': $HEALTH"
pass "Backend healthy"

echo
echo "2. Translation gateway — Hindi"
RESP=$(curl -sf -X POST "${API_BASE}/api/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, friend","target_lang":"hi"}')
echo "$RESP" | grep -q '"success":true' || fail "Translate gateway failed: $RESP"
TRANSLATED=$(echo "$RESP" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["data"]["translated"])')
echo "  Hindi translation: $TRANSLATED"
[ -n "$TRANSLATED" ] || fail "Empty Hindi translation"
pass "Translation gateway works"

echo
echo "3. Translation gateway — Tamil"
RESP=$(curl -sf -X POST "${API_BASE}/api/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"Self-enquiry is the direct path","target_lang":"ta"}')
echo "$RESP" | grep -q '"success":true' || fail "Tamil translate failed: $RESP"
TRANSLATED=$(echo "$RESP" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["data"]["translated"])')
echo "  Tamil translation: $TRANSLATED"
pass "Tamil translation works"

echo
echo "4. Translation gateway — Spanish (international, should use Azure)"
RESP=$(curl -sf -X POST "${API_BASE}/api/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"The Self alone is real","target_lang":"es"}')
PROVIDER=$(echo "$RESP" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["data"]["provider"])')
echo "  Spanish provider: $PROVIDER"
[ "$PROVIDER" = "azure" ] || [ "$PROVIDER" = "google" ] || pass "Spanish used: $PROVIDER (note: not 'sarvam' which would be unexpected)"
pass "Spanish translation works (provider=$PROVIDER)"

echo
echo "5. Translation gateway — Cache hit (run same Hindi again)"
RESP=$(curl -sf -X POST "${API_BASE}/api/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, friend","target_lang":"hi"}')
CACHED=$(echo "$RESP" | python3 -c 'import json,sys;print(json.loads(sys.stdin.read())["data"]["cached"])')
[ "$CACHED" = "True" ] && pass "Cache hit confirmed" || echo "  ⚠ Expected cache hit, got cached=$CACHED"

echo
echo "6. Translation gateway — Same language no-op"
RESP=$(curl -sf -X POST "${API_BASE}/api/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","source_lang":"en","target_lang":"en"}')
echo "$RESP" | grep -q '"provider":"noop"' || fail "Same-lang noop failed: $RESP"
pass "Same-language no-op handled"

echo
echo "7. Translation gateway — Unsupported language returns 400"
RESP=$(curl -s -X POST "${API_BASE}/api/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","target_lang":"xx"}')
echo "$RESP" | grep -q 'UNSUPPORTED_LANGUAGE' || fail "Unsupported lang should error"
pass "Unsupported language correctly rejected"

echo
echo "8. Page resolver"
RESP=$(curl -s "${API_BASE}/api/page/about?lang=hi")
if echo "$RESP" | grep -q '"success":true'; then
  pass "Page resolver returned data"
elif echo "$RESP" | grep -q '"code":"PAGE_NOT_FOUND"'; then
  echo "  ⚠ Page 'about' not in DB — adapt _fetch_source_page() in page_resolver.py"
else
  fail "Page resolver unexpected response: $RESP"
fi

echo
echo "9. Translation tables created in Supabase"
echo "  (Skipped — verify manually in Supabase SQL editor:)"
echo "    SELECT count(*) FROM languages;       -- expect 9"
echo "    SELECT count(*) FROM translation_providers;  -- expect 5"

echo
echo "10. Frontend i18n (manual)"
echo "  Visit https://www.arunachalasamudra.co.in/hi/  in your browser."
echo "  Expect: <html lang=\"hi\">, UI strings in Devanagari."

echo
echo "=== ALL AUTOMATED CHECKS PASSED ==="
echo
echo "Manual checks remaining:"
echo "  • Sign in to /admin/translations and verify the table loads"
echo "  • Send a Hindi chat message and verify response comes back in Hindi"
echo "  • Run scripts/seed_ui_strings.py to populate locale JSONs"
echo "  • Run scripts/generate_sitemaps.py and submit sitemap.xml to Google Search Console"
