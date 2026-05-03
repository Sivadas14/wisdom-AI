/**
 * react-i18next configuration for arunachalasamudra.co.in
 *
 * Phase 1 locales (9 total):
 *   en (default) + hi, ta, te, bn, ml, es, fr, ar
 *
 * Locale JSONs are served from /locales/{lng}/{ns}.json (Vite static).
 * Detection priority: URL path > cookie > localStorage > navigator > 'en'.
 */
import i18n from "i18next";
import HttpBackend from "i18next-http-backend";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

export const SUPPORTED_LANGUAGES = [
  { code: "en",    native: "English",    english: "English",     rtl: false },
  // Indian
  { code: "hi",    native: "हिन्दी",       english: "Hindi",       rtl: false },
  { code: "ta",    native: "தமிழ்",       english: "Tamil",       rtl: false },
  { code: "te",    native: "తెలుగు",      english: "Telugu",      rtl: false },
  { code: "bn",    native: "বাংলা",        english: "Bengali",     rtl: false },
  { code: "ml",    native: "മലയാളം",     english: "Malayalam",   rtl: false },
  // Western Europe
  { code: "es",    native: "Español",    english: "Spanish",     rtl: false },
  { code: "fr",    native: "Français",   english: "French",      rtl: false },
  { code: "de",    native: "Deutsch",    english: "German",      rtl: false },
  { code: "nl",    native: "Nederlands", english: "Dutch",       rtl: false },
  // Scandinavian + Finnish
  { code: "sv",    native: "Svenska",    english: "Swedish",     rtl: false },
  { code: "da",    native: "Dansk",      english: "Danish",      rtl: false },
  { code: "no",    native: "Norsk",      english: "Norwegian",   rtl: false },
  { code: "fi",    native: "Suomi",      english: "Finnish",     rtl: false },
  // Middle East
  { code: "ar",    native: "العربية",      english: "Arabic",      rtl: true  },
  // East Asia
  { code: "zh-CN", native: "中文",        english: "Chinese (Simplified)", rtl: false },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];
export const SUPPORTED_LNG_CODES: LanguageCode[] = SUPPORTED_LANGUAGES.map(l => l.code);
export const RTL_LANGS = new Set(SUPPORTED_LANGUAGES.filter(l => l.rtl).map(l => l.code));

/**
 * One-time bootstrap sync: when the user picked a language via the GTranslate
 * widget on the public Landing page, that choice lives in the `googtrans`
 * cookie (`/auto/hi`, `/en/ta`, etc.). The post-login react-i18next system
 * reads from our `pref_lang` cookie. Without bridging the two, the user's
 * Landing-language choice would not carry into the in-app experience.
 *
 * This runs at module load, BEFORE i18n.init() — so the LanguageDetector's
 * cookie lookup naturally picks up the synced value. We only seed pref_lang
 * if it isn't already set, so an explicit in-app choice (made via
 * LanguageSwitcher.tsx) always wins over GTranslate's choice.
 */
function bootstrapLanguageFromGoogtrans() {
  if (typeof document === "undefined") return;
  // If user already has an explicit pref_lang, do nothing.
  if (/(^|;\s*)pref_lang=/.test(document.cookie)) return;

  const m = document.cookie.match(/googtrans=\/[^/]+\/([a-zA-Z-]+)/);
  if (!m || !m[1]) return;

  const raw = m[1].toLowerCase();
  const code: string =
    raw === "zh-cn" ? "zh-CN" :
    raw === "zh-tw" ? "zh-TW" :
    raw;

  if (!(SUPPORTED_LNG_CODES as readonly string[]).includes(code)) return;

  document.cookie = `pref_lang=${code}; max-age=${60 * 60 * 24 * 365}; path=/; SameSite=Lax; Secure`;
  try { localStorage.setItem("preferredLang", code); } catch { /* private browsing */ }
}
bootstrapLanguageFromGoogtrans();

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: "en",
    supportedLngs: SUPPORTED_LNG_CODES as readonly string[],
    load: "currentOnly",
    ns: ["common"],
    defaultNS: "common",
    backend: {
      loadPath: "/locales/{{lng}}/{{ns}}.json",
    },
    detection: {
      // The lang-prefix in the URL takes priority — see LangPrefixRouter.tsx
      order: ["path", "cookie", "localStorage", "navigator"],
      lookupCookie: "pref_lang",
      lookupLocalStorage: "preferredLang",
      caches: ["cookie", "localStorage"],
      cookieMinutes: 60 * 24 * 365, // 1 year
    },
    interpolation: { escapeValue: false }, // React already escapes
    react: { useSuspense: false },
  });

/**
 * Switch language: updates i18next + cookie + localStorage + <html>
 * lang/dir attributes. Caller (LanguageSwitcher) is responsible for
 * navigating to /<lang>/<rest-of-path>.
 */
export function setLanguage(code: LanguageCode) {
  i18n.changeLanguage(code);
  document.documentElement.lang = code;
  document.documentElement.dir = RTL_LANGS.has(code) ? "rtl" : "ltr";
  // Cookie + localStorage are auto-set by i18next-browser-languagedetector
  // because we list them in `caches`. Belt-and-braces:
  try {
    document.cookie = `pref_lang=${code}; max-age=${60 * 60 * 24 * 365}; path=/; SameSite=Lax; Secure`;
    localStorage.setItem("preferredLang", code);
  } catch {/* private browsing */}
}

export default i18n;
