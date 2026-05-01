/**
 * LanguageSwitcher.tsx — globe icon + dropdown of 9 Phase-1 languages.
 *
 * Behaviours:
 *   - Reads current language from URL prefix (priority) or i18next.
 *   - On select: updates i18next, persists to cookie/localStorage, syncs to
 *     Supabase language_preferences if user is logged in, then navigates to
 *     /<new-lang>/<same-rest-of-path>.
 *   - Closes on outside click.
 *   - Shows language names in their own script (हिन्दी, தமிழ்) for fast
 *     visual recognition.
 *
 * Mount this in your existing site header next to the user menu.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Globe, ChevronDown, Check } from "lucide-react";

import {
  SUPPORTED_LANGUAGES,
  SUPPORTED_LNG_CODES,
  type LanguageCode,
  setLanguage,
} from "@/i18n";
import { supabase } from "@/lib/supabase";   // existing Supabase client

interface LanguageSwitcherProps {
  className?: string;
  variant?: "compact" | "full";
}

export default function LanguageSwitcher({ className = "", variant = "full" }: LanguageSwitcherProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { i18n } = useTranslation();

  // Determine current language: URL prefix wins, fall back to i18next
  const urlLang = location.pathname.split("/")[1] as LanguageCode | undefined;
  const currentCode: LanguageCode = (
    urlLang && (SUPPORTED_LNG_CODES as string[]).includes(urlLang)
      ? urlLang
      : (i18n.language || "en").split("-")[0]
  ) as LanguageCode;
  const current = SUPPORTED_LANGUAGES.find(l => l.code === currentCode) || SUPPORTED_LANGUAGES[0];

  // Outside click closes the dropdown
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  // Sync language preference to Supabase when user is logged in
  async function syncToSupabase(code: LanguageCode) {
    try {
      const { data } = await supabase.auth.getUser();
      if (!data?.user) return;
      await supabase.from("language_preferences").upsert({
        user_id: data.user.id,
        preferred_language: code,
        last_updated: new Date().toISOString(),
      });
    } catch {
      // Silent fail — language is still set client-side
    }
  }

  function pick(code: LanguageCode) {
    setLanguage(code);
    syncToSupabase(code);

    // Rewrite URL: /<old-lang>/path → /<new-lang>/path
    const segments = location.pathname.split("/").filter(Boolean);
    const isLangPrefixed = segments.length > 0
      && (SUPPORTED_LNG_CODES as string[]).includes(segments[0]);

    // Phase 1A: setLanguage updates i18next + cookie + localStorage. URL prefix
    // routing is added in Phase 1B (see PATCHES/App_tsx.patch.md). For now the
    // URL stays the same; UI strings switch immediately on next render.
    //
    // To enable URL prefix routing, uncomment the navigate() call below AFTER
    // applying App_tsx.patch.md to wrap routes with /:lang/...
    /* eslint-disable @typescript-eslint/no-unused-vars */
    if (isLangPrefixed) {
      segments[0] = code;
    } else {
      segments.unshift(code);
    }
    // navigate("/" + segments.join("/") + location.search);  // ← Phase 1B
    setOpen(false);
  }

  return (
    <div ref={ref} className={`relative inline-block ${className}`}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Choose language"
        className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      >
        <Globe className="h-4 w-4" aria-hidden />
        {variant === "full" && <span className="text-sm font-medium">{current.native}</span>}
        <ChevronDown className="h-3 w-3 opacity-60" aria-hidden />
      </button>

      {open && (
        <ul
          role="menu"
          className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50 py-1 max-h-96 overflow-y-auto"
        >
          {SUPPORTED_LANGUAGES.map((l) => {
            const isCurrent = l.code === current.code;
            return (
              <li
                key={l.code}
                role="menuitem"
                tabIndex={0}
                onClick={() => pick(l.code as LanguageCode)}
                onKeyDown={(e) => e.key === "Enter" && pick(l.code as LanguageCode)}
                className={`px-4 py-2 cursor-pointer hover:bg-orange-50 dark:hover:bg-orange-950 flex items-center justify-between ${
                  isCurrent ? "font-semibold text-orange-700 dark:text-orange-300" : ""
                }`}
              >
                <div className="flex flex-col">
                  <span className="text-sm">{l.native}</span>
                  <span className="text-xs text-gray-500">{l.english}</span>
                </div>
                {isCurrent && <Check className="h-4 w-4" aria-hidden />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
