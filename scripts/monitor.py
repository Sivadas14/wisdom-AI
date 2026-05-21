"""
Arunachala Samudra — Daily Health Monitor
==========================================
Run by GitHub Actions daily. Exits with code 1 if any check fails
(which triggers a GitHub notification email to the repo owner).

Checks:
  1. AWS App Runner (health endpoint + deployed version)
  2. Authentication endpoints (login, OTP, check-email)
  3. Public API endpoints (plans, notification bar, addons)
  4. Frontend SPA pages
  5. Admin API endpoints
  6. Knowledge base (indexed books count + failed books)
  7. Polar payment gateway reachability + webhook endpoint
  8. Razorpay payment gateway reachability + webhook endpoint
  9. Chat API availability
"""

import requests
import sys
from datetime import datetime, timezone

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL     = "https://www.arunachalasamudra.co.in"
POLAR_API    = "https://api.polar.sh"
RAZORPAY_API = "https://api.razorpay.com/v1"
TIMEOUT      = 15   # seconds per request

# ─── Helpers ──────────────────────────────────────────────────────────────────

results = []  # (label, ok, detail)

def check(label: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    results.append((label, ok, detail))
    suffix = f"  →  {detail}" if detail else ""
    print(f"  {icon}  {label}{suffix}")

def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def safe_get(url: str, **kwargs):
    return requests.get(url, timeout=TIMEOUT, **kwargs)

def safe_post(url: str, **kwargs):
    return requests.post(url, timeout=TIMEOUT, **kwargs)

# ─── 1. App Runner Health ─────────────────────────────────────────────────────

section("1 · AWS App Runner — Server Health")
try:
    r = safe_get(f"{BASE_URL}/health")
    data = r.json()
    ok = r.status_code == 200 and data.get("status") == "healthy"
    version = data.get("version", "unknown")[:12]
    ts = data.get("timestamp", "")[:19]
    check("Health endpoint",   ok,         f"status={data.get('status')}  version={version}  ts={ts}")
    check("HTTP 200 response", r.status_code == 200, f"HTTP {r.status_code}")
except Exception as e:
    check("Health endpoint",   False, str(e))
    check("HTTP 200 response", False, "request failed")

# ─── 2. Authentication ────────────────────────────────────────────────────────

section("2 · Authentication")

for label, path, method, payload in [
    ("Check-email endpoint", "/api/auth/check-email",  "POST", {"email": "healthcheck@monitor.test"}),
    ("Send-OTP endpoint",    "/api/auth/send-otp",     "POST", {"email": "healthcheck@monitor.test"}),
    ("Login endpoint",       "/api/auth/login",        "POST", {"email": "healthcheck@monitor.test", "password": "x"}),
    ("Google OAuth start",   "/api/auth/google",       "POST", {"redirect_uri": "https://example.com"}),
]:
    try:
        fn = safe_post if method == "POST" else safe_get
        r = fn(f"{BASE_URL}{path}", json=payload, headers={"Content-Type": "application/json"})
        # 4xx = endpoint alive but validation/auth failed (correct). 5xx = broken.
        check(label, r.status_code < 500, f"HTTP {r.status_code}")
    except Exception as e:
        check(label, False, str(e))

# ─── 3. Public API Endpoints ──────────────────────────────────────────────────

section("3 · Public API Endpoints")

for label, path in [
    ("Plans list",        "/api/plans/"),
    ("Notification bar",  "/api/notification-bar/"),
    ("Add-ons list",      "/api/addon/"),
    ("Features list",     "/api/features/"),
]:
    try:
        r = safe_get(f"{BASE_URL}{path}")
        check(label, r.status_code < 500, f"HTTP {r.status_code}")
    except Exception as e:
        check(label, False, str(e))

# ─── 4. Frontend SPA ──────────────────────────────────────────────────────────

section("4 · Frontend (React SPA)")

for label, path in [
    ("Home page",    "/"),
    ("Sign-in page", "/signin"),
    ("Admin login",  "/admin/login"),
]:
    try:
        r = safe_get(f"{BASE_URL}{path}")
        is_html = "text/html" in r.headers.get("content-type", "")
        check(label, r.status_code == 200 and is_html,
              f"HTTP {r.status_code}  html={is_html}")
    except Exception as e:
        check(label, False, str(e))

# ─── 5. Admin API Endpoints ───────────────────────────────────────────────────

section("5 · Admin API Endpoints")

for label, path in [
    ("Admin source-data list", "/api/admin/source-data/list"),
    ("Admin users list",       "/api/admin/users"),
    ("Admin feedback",         "/api/admin/feedback"),
]:
    try:
        r = safe_get(f"{BASE_URL}{path}")
        # 200 or 401/403 = endpoint alive; 500+ = broken
        note = " (auth required — expected)" if r.status_code in (401, 403) else ""
        check(label, r.status_code < 500, f"HTTP {r.status_code}{note}")
    except Exception as e:
        check(label, False, str(e))

# ─── 6. Knowledge Base ────────────────────────────────────────────────────────

section("6 · Knowledge Base")

try:
    r = safe_get(f"{BASE_URL}/api/admin/source-data/list")
    if r.status_code == 200:
        data = r.json()
        docs = data.get("files") or data.get("source_documents") or []
        indexed    = [d for d in docs if d.get("status") == "completed"]
        processing = [d for d in docs if d.get("status") == "processing"]
        failed     = [d for d in docs if d.get("status") == "failed"]
        check("Books endpoint",
              True,
              f"total={len(docs)}  indexed={len(indexed)}  processing={len(processing)}  failed={len(failed)}")
        if failed:
            for doc in failed:
                name = doc.get("filename", "?").split("/")[-1]
                check(f"  ⚠ Failed book: {name}", False, "status=failed — re-upload needed")
        if processing:
            check("Books still processing",
                  True,   # not an error, just informational
                  f"{len(processing)} book(s) still indexing (check back later)")
    else:
        check("Books endpoint", r.status_code < 500, f"HTTP {r.status_code}")
except Exception as e:
    check("Books endpoint", False, str(e))

# ─── 7. Polar Payment Gateway ─────────────────────────────────────────────────

section("7 · Polar Payment Gateway")

try:
    r = requests.get(f"{POLAR_API}/v1/products",
                     timeout=TIMEOUT,
                     headers={"Accept": "application/json"})
    # 401 = reachable, needs auth key. That's fine — gateway is up.
    note = " (auth required — gateway is up)" if r.status_code == 401 else ""
    check("Polar API reachable", r.status_code < 500, f"HTTP {r.status_code}{note}")
except requests.exceptions.ConnectionError:
    check("Polar API reachable", False, "Connection error — Polar unreachable")
except requests.exceptions.Timeout:
    check("Polar API reachable", False, "Timeout — Polar not responding")
except Exception as e:
    check("Polar API reachable", False, str(e))

try:
    r = safe_post(f"{BASE_URL}/api/subscriptions/webhook",
                  json={},
                  headers={"Content-Type": "application/json"})
    note = " (signature check — expected)" if r.status_code == 400 else ""
    check("Polar webhook endpoint", r.status_code < 500, f"HTTP {r.status_code}{note}")
except Exception as e:
    check("Polar webhook endpoint", False, str(e))

# ─── 8. Razorpay Payment Gateway ──────────────────────────────────────────────

section("8 · Razorpay Payment Gateway")

try:
    r = requests.get(f"{RAZORPAY_API}/payments",
                     timeout=TIMEOUT,
                     headers={"Accept": "application/json"})
    note = " (auth required — gateway is up)" if r.status_code == 401 else ""
    check("Razorpay API reachable", r.status_code < 500, f"HTTP {r.status_code}{note}")
except requests.exceptions.ConnectionError:
    check("Razorpay API reachable", False, "Connection error — Razorpay unreachable")
except requests.exceptions.Timeout:
    check("Razorpay API reachable", False, "Timeout — Razorpay not responding")
except Exception as e:
    check("Razorpay API reachable", False, str(e))

try:
    r = safe_post(f"{BASE_URL}/api/subscriptions/razorpay-webhook",
                  json={},
                  headers={"Content-Type": "application/json"})
    note = " (signature check — expected)" if r.status_code == 400 else ""
    check("Razorpay webhook endpoint", r.status_code < 500, f"HTTP {r.status_code}{note}")
except Exception as e:
    check("Razorpay webhook endpoint", False, str(e))

# ─── 9. Chat API ──────────────────────────────────────────────────────────────

section("9 · Chat API")

try:
    r = safe_get(f"{BASE_URL}/api/chat")
    note = " (auth required — expected)" if r.status_code in (401, 403) else ""
    check("Chat endpoint", r.status_code < 500, f"HTTP {r.status_code}{note}")
except Exception as e:
    check("Chat endpoint", False, str(e))

try:
    r = safe_post(f"{BASE_URL}/api/chat",
                  json={},
                  headers={"Content-Type": "application/json"})
    check("Chat create conversation", r.status_code < 500, f"HTTP {r.status_code}")
except Exception as e:
    check("Chat create conversation", False, str(e))

# ─── 10. Guest Chat — Real LLM Response (English) ─────────────────────────────
# Sends an actual question through the guest-chat path and verifies the AI
# streams back a real answer. This catches OpenAI outages, RAG retrieval
# failures, and silent prompt regressions that endpoint-only checks miss.
import time as _time
import uuid as _uuid

section("10 · Guest Chat — Real LLM (English)")

try:
    sid = f"monitor_{_uuid.uuid4().hex[:8]}"
    payload = {
        "message": "Who am I, according to Sri Ramana Maharshi?",
        "session_id": sid,
        "history": [],
        "lang": "en",
    }
    t0 = _time.time()
    r = requests.post(
        f"{BASE_URL}/api/chat/guest",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=45,
        stream=True,
    )
    # Aggregate streaming response chunks into a single string so we can
    # validate the content (not just that bytes arrived).
    body_chunks = []
    if r.status_code == 200:
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                import json as _json
                payload_str = line[6:].strip()
                if payload_str in ("[DONE]", ""):
                    continue
                try:
                    obj = _json.loads(payload_str)
                    content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        body_chunks.append(content)
                except Exception:
                    pass
    elapsed = _time.time() - t0
    text = "".join(body_chunks)
    # Strip backend metadata tags like <message_id>, <citations>, <questions>,
    # <title> so the content check measures only the visible answer.
    import re as _re
    visible = _re.sub(r"<(message_id|citations|questions|title)[^>]*>.*?</\1>", "", text, flags=_re.DOTALL)
    visible_clean = _re.sub(r"<[^>]+>", "", visible).strip()

    check(
        "Guest chat returns 200",
        r.status_code == 200,
        f"HTTP {r.status_code}  elapsed={elapsed:.1f}s",
    )
    check(
        "Guest chat answer is non-trivial",
        len(visible_clean) >= 80,
        f"answer_chars={len(visible_clean)}  elapsed={elapsed:.1f}s",
    )
    # Heuristic: a real Ramana answer should mention Ramana, self-inquiry,
    # or related core terms. Catches blank / refusal / hallucinated answers.
    keywords = ("Ramana", "self", "inquiry", "Self", "I am")
    has_keyword = any(kw.lower() in visible_clean.lower() for kw in keywords)
    check(
        "Guest chat answer mentions expected concepts",
        has_keyword,
        f"keywords_present={has_keyword}  preview={visible_clean[:90]!r}",
    )
except Exception as e:
    check("Guest chat real-LLM test", False, str(e))

# ─── 11. Guest Chat — Multilingual (Hindi) ────────────────────────────────────
# Verifies the Phase-1B translation pipeline: send Hindi input → backend
# translates to English → LLM answers → backend translates answer back to
# Hindi. We check the response actually contains Devanagari script so we
# know the translation step ran end-to-end, not just that bytes streamed.

section("11 · Guest Chat — Multilingual (Hindi)")

try:
    sid = f"monitor_hi_{_uuid.uuid4().hex[:8]}"
    payload = {
        "message": "मैं कौन हूँ?",  # "Who am I?" in Hindi
        "session_id": sid,
        "history": [],
        "lang": "hi",
    }
    t0 = _time.time()
    r = requests.post(
        f"{BASE_URL}/api/chat/guest",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,  # multilingual path takes longer (translate in + translate out)
        stream=True,
    )
    body_chunks = []
    if r.status_code == 200:
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                import json as _json
                payload_str = line[6:].strip()
                if payload_str in ("[DONE]", ""):
                    continue
                try:
                    obj = _json.loads(payload_str)
                    content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        body_chunks.append(content)
                except Exception:
                    pass
    elapsed = _time.time() - t0
    text = "".join(body_chunks)
    # Devanagari Unicode block: U+0900–U+097F
    devanagari_chars = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)

    check(
        "Hindi chat returns 200",
        r.status_code == 200,
        f"HTTP {r.status_code}  elapsed={elapsed:.1f}s",
    )
    check(
        "Hindi chat answer contains Devanagari",
        devanagari_chars >= 50,
        f"devanagari_chars={devanagari_chars}  total_chars={len(text)}",
    )
except Exception as e:
    check("Hindi chat multilingual test", False, str(e))

# ─── 12. Translation Engine ───────────────────────────────────────────────────
# Hits /api/translate directly in BOTH directions. The reverse direction
# (Indic → English) is what historically broke and what the chat
# retranslation effect depends on, so we test it explicitly.

section("12 · Translation Engine")

# Test 12a: English → Hindi (forward)
try:
    r = safe_post(
        f"{BASE_URL}/api/translate",
        json={"text": "The self is realized through self-inquiry.", "target_lang": "hi", "source_lang": "en"},
        headers={"Content-Type": "application/json"},
    )
    if r.status_code == 200:
        data = r.json()
        translated = data.get("data", {}).get("translated", "")
        provider = data.get("data", {}).get("provider", "?")
        devanagari = sum(1 for c in translated if 0x0900 <= ord(c) <= 0x097F)
        check(
            "Translate EN → HI",
            devanagari >= 8 and provider in ("sarvam", "azure", "google", "noop"),
            f"provider={provider}  devanagari={devanagari}  preview={translated[:60]!r}",
        )
    else:
        check("Translate EN → HI", False, f"HTTP {r.status_code}")
except Exception as e:
    check("Translate EN → HI", False, str(e))

# Test 12b: Hindi → English (reverse — this is what the chat-history
# retranslation depends on, and what broke for the user repeatedly).
try:
    r = safe_post(
        f"{BASE_URL}/api/translate",
        json={"text": "आत्म-विचार के माध्यम से आत्म-साक्षात्कार होता है।", "target_lang": "en", "source_lang": "hi"},
        headers={"Content-Type": "application/json"},
    )
    if r.status_code == 200:
        data = r.json()
        translated = data.get("data", {}).get("translated", "")
        provider = data.get("data", {}).get("provider", "?")
        # English result should be ASCII-heavy. Count letters in the
        # Basic Latin block as a rough sanity check.
        latin_chars = sum(1 for c in translated if c.isalpha() and ord(c) < 128)
        check(
            "Translate HI → EN",
            latin_chars >= 10 and provider in ("sarvam", "azure", "google", "noop"),
            f"provider={provider}  latin={latin_chars}  preview={translated[:60]!r}",
        )
    else:
        check("Translate HI → EN", False, f"HTTP {r.status_code}")
except Exception as e:
    check("Translate HI → EN", False, str(e))

# Test 12c: Tamil → English (separate Sarvam codepath; covers a
# different Indic family)
try:
    r = safe_post(
        f"{BASE_URL}/api/translate",
        json={"text": "சுய விசாரம் மூலம் சுய-உணர்வு அடையப்படுகிறது.", "target_lang": "en", "source_lang": "ta"},
        headers={"Content-Type": "application/json"},
    )
    if r.status_code == 200:
        data = r.json()
        translated = data.get("data", {}).get("translated", "")
        provider = data.get("data", {}).get("provider", "?")
        latin_chars = sum(1 for c in translated if c.isalpha() and ord(c) < 128)
        check(
            "Translate TA → EN",
            latin_chars >= 10 and provider in ("sarvam", "azure", "google", "noop"),
            f"provider={provider}  latin={latin_chars}  preview={translated[:60]!r}",
        )
    else:
        check("Translate TA → EN", False, f"HTTP {r.status_code}")
except Exception as e:
    check("Translate TA → EN", False, str(e))

# ─── Summary ──────────────────────────────────────────────────────────────────

total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
now    = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

print(f"\n{'═' * 60}")
print(f"  SUMMARY  —  {now}")
print(f"{'═' * 60}")
print(f"  Passed : {passed}/{total}")

if failed:
    print(f"  Failed : {failed}/{total}")
    print(f"\n  ⚠  Issues requiring attention:")
    for label, ok, detail in results:
        if not ok:
            print(f"    • {label}" + (f": {detail}" if detail else ""))
    sys.exit(1)
else:
    print(f"  All systems operational ✓")
    sys.exit(0)
