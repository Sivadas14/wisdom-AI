/**
 * HreflangTags.tsx — emit the proper <link rel="alternate" hreflang="..."> tags
 * on every route so Google understands language alternates.
 *
 * Mount this near the root of your render tree (inside <Routes> wrapper) so it
 * runs on every navigation. Uses react-helmet-async — make sure
 * <HelmetProvider> wraps your <App />.
 *
 * Output for /hi/wisdom-portal:
 *   <link rel="canonical" href="https://www.arunachalasamudra.co.in/hi/wisdom-portal" />
 *   <link rel="alternate" hreflang="en"        href=".../en/wisdom-portal" />
 *   <link rel="alternate" hreflang="hi"        href=".../hi/wisdom-portal" />
 *   ... (all other Phase-1 langs) ...
 *   <link rel="alternate" hreflang="x-default" href=".../wisdom-portal" />
 */
import { Helmet } from "react-helmet-async";
import { useLocation } from "react-router-dom";
import { SUPPORTED_LANGUAGES, SUPPORTED_LNG_CODES, RTL_LANGS } from "@/i18n";

const SITE_ORIGIN = "https://www.arunachalasamudra.co.in";

export default function HreflangTags() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  // Strip the language prefix to get the canonical path
  let restOfPath = location.pathname;
  let currentLang = "en";
  if (segments.length > 0 && (SUPPORTED_LNG_CODES as string[]).includes(segments[0])) {
    currentLang = segments[0];
    restOfPath = "/" + segments.slice(1).join("/");
    if (restOfPath === "/") restOfPath = "";
  }

  const canonicalUrl = `${SITE_ORIGIN}/${currentLang}${restOfPath}`;
  const isRtl = RTL_LANGS.has(currentLang);

  return (
    <Helmet>
      <html lang={currentLang} dir={isRtl ? "rtl" : "ltr"} />
      <link rel="canonical" href={canonicalUrl} />
      {SUPPORTED_LANGUAGES.map((l) => (
        <link
          key={l.code}
          rel="alternate"
          hrefLang={l.code}
          href={`${SITE_ORIGIN}/${l.code}${restOfPath}`}
        />
      ))}
      <link rel="alternate" hrefLang="x-default" href={`${SITE_ORIGIN}${restOfPath || "/"}`} />
    </Helmet>
  );
}
