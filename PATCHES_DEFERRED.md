# Deferred Patches — Manual Review Required

Patches that the automated apply pass deliberately skipped because they require
human judgement on existing-file-specific decisions:

## 1. `frontend/src/App.tsx` — lang-prefix routing (Phase 1B)

The App.tsx route structure is complex and project-specific. The proposed
restructure (per `wisdom-AI-translation-patches/PATCHES/App_tsx.patch.md`)
wraps every existing route under `<Route path=":lang">`. This works but requires
human review to ensure no edge cases break (auth callbacks, admin sub-routes,
catch-all order, etc.).

**Effect of skipping:**
- Language switcher still works (UI strings change)
- URL stays the same regardless of language (no `/hi/` prefix)
- SEO impact: hreflang tags still emit correctly via Helmet, but search engines
  see a single URL with content swapping based on cookie — Google handles this
  reasonably but the dedicated subfolder approach is stronger SEO.

**To apply later:**
1. Read `wisdom-AI-translation-patches/PATCHES/App_tsx.patch.md`
2. Restructure your `<Routes>` block to nest under `<Route path=":lang">`
3. Add the `LangBoundary` and `BareToLangRedirect` components from the patch
4. Re-enable the `navigate()` call in `LanguageSwitcher.tsx` (currently
   commented; search for "Phase 1B")

## 2. `frontend/src/components/ChatMessage.tsx` — `<lang_translated>` tag handling

The output-translation hook in chat.py is also deferred (Phase 1A enables only
INPUT translation). Once you enable output translation in chat.py (see
PATCHES/chat.patch.md §3 — currently the comment block "this commit enables
INPUT translation only"), apply the ChatMessage.tsx patch to display the
translated chunk.

**Effect of skipping:**
- Phase 1A: User types in Hindi → translated to English → existing RAG
  pipeline → response in **English**. The user's Indic message DOES get
  understood by the AI, but the response comes back in English. This is still
  useful (the AI grounds correctly in Ramana corpus) but isn't full
  bilingual.
- Phase 1B (after enabling output translation): Full bilingual chat.

## 3. `backend/src/services/chat.py` — output translation hook (Phase 1B)

Already partially patched: input translation is live. Adding the output hook
requires identifying the exact line in the streaming generator where
`ai_message.content` becomes finalised. This is project-specific (~50 lines of
custom streaming code) and needs eyes.
