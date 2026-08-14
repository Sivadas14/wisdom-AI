# Arunachala Samudra — Technical Manual

Wisdom guide answering strictly from the authenticated Sri Ramana Maharshi
library. FastAPI backend + React SPA, single container on AWS App Runner.

Last updated: 13 August 2026

---

## 1. Architecture

| Layer | Technology |
|---|---|
| Frontend | React + Vite SPA, built in Docker stage 1, served from `src/ui` |
| Backend | FastAPI, uvicorn `--factory` (`src.server:get_app`) |
| Database | PostgreSQL + `pgvector` (Supabase) |
| Chat LLM | Anthropic `claude-haiku-4-5-20251001` via official `anthropic` SDK |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) via official `openai` SDK |
| Hosting | AWS App Runner (`us-east-1`), image in ECR |
| CI/CD | GitHub Actions → ECR → App Runner |

All settings use `env_prefix="ASAM_"` (pydantic-settings), so every App Runner
environment variable is prefixed `ASAM_`.

---

## 2. Environment variables

| Variable | Purpose | Notes |
|---|---|---|
| `ASAM_ANTHROPIC_TOKEN` | **Chat.** Anthropic key (`sk-ant-…`) | Preferred; takes precedence over the legacy var |
| `ASAM_OPENAI_TOKEN` | **Embeddings.** OpenAI key (`sk-proj…`/`sk-…`) | Historical name — it fed the old TuneAPI proxy |
| `ASAM_EMBEDDING_TOKEN` | Optional explicit OpenAI embedding key | Overrides the above for embeddings only |
| `ASAM_ANTHROPIC_MODEL` | Override chat model ID | Default `claude-haiku-4-5-20251001` |
| `ASAM_RAG_MAX_DISTANCE` | Relevance cutoff, cosine distance | Default `0.65` |
| `ASAM_RAG_MAX_CHUNKS` | Passages retrieved per query | Default `10` |
| `ASAM_DB_URL` | Postgres async URL | |
| `ASAM_JWT_SECRET` | Auth signing secret | |

> The chat key and the embedding key are **different providers** and both are
> needed. Anthropic serves no embeddings API, and the stored vectors were built
> with OpenAI, so they must stay in the same vector space.

---

## 3. TuneAPI removal (completed)

TuneAPI was an LLM proxy that broke on 11 Aug 2026. It has been removed
entirely and replaced by `backend/src/llm_shim.py`, which reproduces the old
`tu` / `tt` / `ta` namespaces on top of `anthropic`, `openai`, `pydantic` and
the standard library — so call sites needed no rewriting.

**Verification:** no `tuneapi` import exists in any runtime file; it is absent
from `pyproject.toml` and has been purged from `uv.lock`. Remaining mentions are
historical comments explaining why the compatibility shims exist.

### Shim mapping

| Old TuneAPI | Replacement |
|---|---|
| `tu.logger`, `tu.to_json`, `tu.folder`, `tu.joinp`, `tu.get_snowflake` | stdlib (`logging`, `json`, `os.path`, `uuid`) |
| `tu.SimplerTimes.*` | `datetime` / `time` |
| `tt.BM`, `tt.F` | pydantic `BaseModel`, `Field` (via compat wrapper) |
| `tt.Message`, `tt.Thread` | Local classes; `Thread.to_anthropic()` splits system prompt and merges consecutive same-role turns |
| `ta.Anthropic`, `ta.Openai` | `AnthropicModel` (both names route to Anthropic) |
| `model.embedding_async` | OpenAI `embeddings.create` |

**`tt.F` compatibility.** TuneAPI called `Field("description", default)`
positionally. Pydantic v2 only accepts the *default* positionally, so a
wrapper detects the old signature and rewrites it to
`Field(default, description=...)`. Without this, `wire.py` fails at import.

---

## 4. RAG pipeline and guardrails

```
user question
  ↓ 1. intent classification   — keyword only, zero API cost
  ↓ 2. contextual query build  — resolves follow-ups ("what did he say about it?")
  ↓ 3. embed query             — OpenAI text-embedding-3-small
  ↓ 4. vector search           — pgvector cosine distance, active docs only
  ↓ 5. RELEVANCE THRESHOLD     — drop passages with distance > 0.65
  ↓ 6. no passages → refuse    — never invents an answer
  ↓ 7. LLM answer              — system prompt restricts to supplied passages
  ↓ 8. cite sources
```

**The guardrail layers**

1. **Intent classification** (`_classify_intent`) — clearly off-topic questions
   skip retrieval and the LLM entirely. Zero cost, instant.
2. **Active-documents filter** — only `SourceDocument.active == True` is searched.
3. **Relevance threshold** — the important one. Vector search *orders* by
   similarity but would otherwise always return its top N rows no matter how
   unrelated. Anything above `ASAM_RAG_MAX_DISTANCE` is discarded.
4. **Empty-result refusal** — when nothing clears the bar, the user gets an
   honest "the passages do not cover this" rather than a confident answer
   assembled from irrelevant text.
5. **System prompt guardrails** — answer only from supplied passages, never use
   general knowledge, never speculate, never mention retrieval internals, never
   refer users to external sites.
6. **Citations** — sources returned alongside the answer.

**Vector search is authoritative.** If embeddings work but nothing is relevant,
the pipeline returns nothing. It does *not* fall through to full-text search,
which would resurrect the weak matches the threshold just rejected. Full-text
search is a fallback for embedding **outages** only, and while it is active
`/health` reports `retrieval: fulltext_fallback`.

---

## 4a. Answer presentation (humanizer)

Every chat reply, guest and paid, in all languages, is cleaned of AI-writing
tells before the seeker sees it. Two layers, neither costing an extra LLM call:

1. **Generation time** — both system prompts carry explicit writing rules: no
   praising the question, no "I hope this helps", no em dashes, no emojis or
   bold decoration, no "serves as"/"stands as", no padding vocabulary, no forced
   rule of three, vary sentence length, quote sources exactly.
2. **Display time** — `src/humanize.py` deterministically strips what slips
   through: em dashes, emojis, curly quotes, sycophantic openers, chatbot
   artifacts, signposting, filler, copula avoidance.

**Verbatim quotations are never modified.** Blockquotes, quoted spans and inline
code are masked out before any transformation and restored byte-for-byte, so
Bhagavan's recorded words keep their original wording *and* punctuation —
including em dashes.

**Negative parallelism is deliberately not rewritten.** Every regex form of
"it's not just X, it's Y" inverts meaning; an early draft turned "self-enquiry
is not just about technique" into "is about technique", the opposite of the
teaching. It is handled in the prompt instead.

Safety rails: emoji stripping excludes Indic script ranges; if filters would
remove more than half a reply the original is returned; any exception falls back
to the original text. Presentation polish must never cost a seeker their answer.

Tests: `backend/tests/test_humanize.py` (14 tests), ordered by priority —
meaning preservation, then quote protection, then tell removal.

Tuning: edit the pattern lists in `humanize.py`. Anything that could change
meaning belongs in the prompt, not in a regex.

---

## 4b. The corpus

53 source documents, all active, embedded with OpenAI `text-embedding-3-small`
into a `VECTOR(1536)` pgvector column. Ingestion happens through
`/admin` (Knowledge Base), which extracts text, chunks it, embeds each chunk and
writes to `document_chunks`.

**Indexing fails quietly.** `_index_pdf_background` embeds chunk by chunk and
catches per-chunk failures so one bad chunk cannot abort a whole book. The
consequence is that a document uploaded while embeddings are unavailable is
saved with status `completed` and **zero chunks**. It looks correct in the admin
list and is invisible to search. After any embedding outage, check
`/health/embedding` first, then re-upload anything added during the window.

Verify an upload functionally, not by its status: ask the chat something only
the new book can answer and confirm it cites that book.

Scanned PDFs with no text layer extract nothing and will index as zero chunks.
Check for a text layer before uploading.

---

## 4c. Which model does what

Every piece of *text* is Anthropic. Everything else is OpenAI, because Anthropic
serves no speech, image or embedding API.

| Feature | Text / reasoning | Media |
|---|---|---|
| Chat answers | Anthropic `claude-haiku-4-5` | — |
| Meditation script (audio, video) | Anthropic `claude-haiku-4-5` | OpenAI `gpt-4o-mini-tts` |
| Video meditation | Anthropic (script) | OpenAI TTS + `gpt-image-1` frames, assembled with ffmpeg |
| Contemplation card | Anthropic (quote + image prompt) | OpenAI `gpt-image-1` |
| RAG retrieval | — | OpenAI `text-embedding-3-small` |
| Voice input | — | OpenAI `whisper-1` |

**The `gpt-4o` names in the code are misleading.** Call sites still read
`get_llm("gpt-4o")`, a leftover from when TuneAPI proxied OpenAI. The shim maps
those ids to Claude through `_OPENAI_TO_ANTHROPIC`, so nothing reaches OpenAI
for text. Renaming them is cosmetic and deliberately deferred.

Image model is set by `ASAM_IMAGE_MODEL` (default `gpt-image-1`). Call sites were
written for dall-e-3, so sizes and quality words are translated rather than
rejected: `1792x1024` becomes `1536x1024`, `standard` becomes `medium`.

Check both media paths with `/health/media`, which calls speech and image
generation for real and reports the actual error and model.

---

## 5. Free-question quota (guests)

Limit: **3 questions** per browser session per day *and* per IP per day
(`GUEST_MESSAGE_LIMIT` backend, `GUEST_LIMIT` frontend).

**A seeker is never charged for our failure.** The counter is incremented only
after a genuine answer has been produced — never before the LLM call.

Non-billable outcomes: LLM errors, rate limits, no relevant passages, off-topic
refusals (which cost no LLM call), and network failures.

The backend emits a `<no_charge/>` marker at the start of any non-billable
reply; the frontend strips the marker and skips its counter increment. A
structural marker is used rather than matching the message text so it keeps
working in every translated language.

---

## 6. Health and diagnostics

The chat path deliberately swallows LLM exceptions so users see a calm message.
That makes these endpoints the primary debugging tool — use them before reading
code.

| Endpoint | Reports |
|---|---|
| `/health` | Version (git SHA), retrieval mode, last retrieval error |
| `/health/llm` | Live Anthropic call; real error type/message; which key variable is in use |
| `/health/models` | Models this Anthropic account can actually serve |
| `/health/embedding` | Live OpenAI embedding call and its real error |

These sit outside `/api/*` because that prefix requires an authorization header.

Key fingerprints report length and prefix only — never the key itself.

---

## 7. Deployment

`git push origin main` → GitHub Actions builds the image, pushes to ECR, calls
`update-service`, and polls until `/health` reports the pushed SHA. Roughly
5–8 minutes.

**Docker build-time smoke test.** The image runs `get_app()` during the build,
so any startup crash fails the *build* with a real traceback instead of
producing a container that silently fails its health check while App Runner
reverts to the previous version. This is what finally exposed the import-time
failures during the TuneAPI removal.

`RUN uv lock` precedes `uv sync --frozen` so the build always reflects
`pyproject.toml` even if the committed lockfile drifts.

---

## 8. Incident log — August 2026

TuneAPI broke on 11 Aug. Removing it exposed a chain of defects, each hidden
behind the previous one:

| # | Defect | Fix |
|---|---|---|
| 1 | `tu.joinp` missing from shim | Added; server could not start |
| 2 | `uv.lock` stale, no `anthropic` | `RUN uv lock` in Dockerfile |
| 3 | `tt.F()` positional args rejected by pydantic v2 | Compat wrapper |
| 4 | `pillow` missing from dependencies | Added |
| 5 | Chat key was an **OpenAI** key sent to Anthropic | `ASAM_ANTHROPIC_TOKEN` |
| 6 | Account lacked `claude-3-5-haiku-20241022` (404) | `claude-haiku-4-5-20251001` |
| 7 | `settings.py` hardcoded the dead model, overriding the shim | Defers to shim |
| 8 | OpenAI credits exhausted → embeddings dead, silent FTS fallback | Loud logging + `/health` reporting |
| 9 | Guests charged a free question for our failures | Charge only on success + one-time refund |
| 10 | Vector search returned top-N regardless of relevance | Distance threshold |
| 11 | Production admin login advertised `admin` / `admin` and forged a session | Bypass removed |
| 12 | Shim never reimplemented TTS, image gen or transcription, so audio, video and cards had been dead since the TuneAPI removal | Methods added, routed to OpenAI |
| 13 | `Thread(id=...)` rejected by the shim, failing meditation jobs | Thread accepts id and extras |
| 14 | Account has no `dall-e-3` | Default to `gpt-image-1`, translate sizes |
| 15 | Guest generations charged before the job ran | Charge on success only, plus refund |

**Lesson.** Defects 5–8 were invisible because failures were swallowed into a
friendly message and retrieval degraded silently. Diagnostics that report the
*real* error, and health output that names degraded states, matter more than
any individual fix here.

---

## 9. Runbook

**A book was uploaded but the chat cannot find it**
→ Indexing skips failed chunks, so it may hold zero chunks. Check
`/health/embedding`, confirm the PDF has a text layer, then re-upload.

**Chat returns "Something unexpected interrupted the response"**
→ `GET /health/llm`. It names the real cause: `AuthenticationError` (wrong or
missing key), `NotFoundError` (model not available — check `/health/models`),
or a rate limit.

**Answers are vague or poorly sourced**
→ `GET /health`. If `retrieval` is `fulltext_fallback`, vector search is down;
`retrieval_error` gives the reason (usually exhausted OpenAI credits). Restore
credits and it self-heals with no deploy.

**Deployment "succeeds" but the old version stays live**
→ The new container failed its health check and App Runner reverted. The build
smoke test catches most causes; otherwise check App Runner logs for startup
tracebacks.

**A newly uploaded document returns no passages**
→ Indexing embeds chunk-by-chunk and skips failures. If it ran while embeddings
were unavailable, the document exists with **zero chunks**. Re-upload it once
`/health/embedding` reports `ok`.
