import { useEffect, useState } from "react";

/**
 * AtmosphericEntry — a ~6-second sacred overlay that plays on the first
 * visit of a browser session to the public landing or the logged-in home.
 *
 * Timeline (ms):
 *   0    → cream background, nothing visible yet
 *   300  → dawn gradient + mountain silhouette fade in (800ms)
 *   1800 → tagline "Who am I?" fades in (600ms)
 *   5000 → everything fades out (1000ms)
 *   6000 → overlay unmounts, page interactive
 *
 * Respects prefers-reduced-motion (skips instantly).
 * Dismissible by click, tap, or Escape key.
 * Shows at most once per browser session (sessionStorage key below).
 */

const SESSION_KEY = "arunachala_entry_shown_v1";

type Phase = "cream" | "mountain" | "tagline" | "fadeout" | "done";

export default function AtmosphericEntry() {
  // Start invisible; useEffect decides whether to render after mount so the
  // sessionStorage check and the reduced-motion check both run client-side.
  const [phase, setPhase] = useState<Phase | null>(null);

  useEffect(() => {
    // Skip if we've already shown it this session.
    try {
      if (sessionStorage.getItem(SESSION_KEY) === "1") return;
    } catch {
      // sessionStorage can throw in private mode / cross-origin frames — fall
      // through and show anyway; better to over-show than crash.
    }

    // Respect accessibility preference.
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduced) {
      // Mark as shown but don't display — honor the preference fully.
      try {
        sessionStorage.setItem(SESSION_KEY, "1");
      } catch {
        // ignore
      }
      return;
    }

    // Mount and run the phase timeline.
    setPhase("cream");
    const t1 = window.setTimeout(() => setPhase("mountain"), 300);
    const t2 = window.setTimeout(() => setPhase("tagline"), 1800);
    const t3 = window.setTimeout(() => setPhase("fadeout"), 5000);
    const t4 = window.setTimeout(() => {
      setPhase("done");
      try {
        sessionStorage.setItem(SESSION_KEY, "1");
      } catch {
        // ignore
      }
    }, 6000);

    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      window.clearTimeout(t3);
      window.clearTimeout(t4);
    };
  }, []);

  // Escape key dismisses.
  useEffect(() => {
    if (phase === null || phase === "done") return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleDismiss();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const handleDismiss = () => {
    setPhase("done");
    try {
      sessionStorage.setItem(SESSION_KEY, "1");
    } catch {
      // ignore
    }
  };

  if (phase === null || phase === "done") return null;

  // Opacity driven by phase — CSS transitions handle the actual fade.
  const mountainVisible =
    phase === "mountain" || phase === "tagline" || phase === "fadeout";
  const taglineVisible = phase === "tagline" || phase === "fadeout";
  const overlayOpacity = phase === "fadeout" ? 0 : 1;

  return (
    <div
      role="presentation"
      aria-hidden="true"
      onClick={handleDismiss}
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center cursor-pointer select-none"
      style={{
        // Dawn gradient: warm violet-brown at top → coral/amber middle → cream.
        // Matches the brand palette (#472B20 heading, #D05E2D button) and the
        // literal meaning of "Aruna" (dawn / reddish glow).
        background:
          "linear-gradient(180deg, #3a2318 0%, #6b3a22 32%, #D05E2D 62%, #ecd9c6 88%, #ece5df 100%)",
        opacity: overlayOpacity,
        transition: "opacity 1000ms ease-in-out",
      }}
    >
      {/* Arunachala mountain silhouette — hand-crafted SVG, no external asset.
          viewBox is 600x400; the path draws a rounded, slightly asymmetric
          conical peak resembling the hill's iconic profile. */}
      <svg
        viewBox="0 0 600 400"
        className="w-[80%] max-w-[520px] h-auto"
        style={{
          opacity: mountainVisible ? 1 : 0,
          transform: mountainVisible ? "translateY(0)" : "translateY(12px)",
          transition:
            "opacity 800ms ease-out, transform 800ms ease-out",
          filter: "drop-shadow(0 4px 16px rgba(58, 35, 24, 0.35))",
        }}
      >
        {/* Subtle warm glow behind the peak */}
        <defs>
          <radialGradient id="peakGlow" cx="52%" cy="78%" r="55%">
            <stop offset="0%" stopColor="#ffd7a8" stopOpacity="0.55" />
            <stop offset="60%" stopColor="#ffd7a8" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="mountainFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2a1810" />
            <stop offset="100%" stopColor="#472B20" />
          </linearGradient>
        </defs>

        <ellipse cx="300" cy="345" rx="290" ry="70" fill="url(#peakGlow)" />

        {/* Arunachala silhouette — profile viewed from Tiruvannamalai (south).
            Characteristic features: broad base sprawled across a flat plain,
            a single broad rounded dome peak slightly left of center, a
            shorter steeper left flank, and a longer right-side ridge that
            descends through two secondary humps before flattening to the
            plain. Not a sharp alpine peak — a rounded "mound of fire". */}
        <path
          d="
            M 10 380
            C 55 378, 100 370, 140 352
            C 180 332, 215 298, 245 250
            C 265 220, 285 185, 310 160
            C 325 148, 350 145, 370 160
            C 388 175, 400 200, 412 228
            C 422 250, 432 265, 445 268
            C 462 270, 475 260, 488 265
            C 505 275, 535 320, 590 378
            L 590 400
            L 10 400
            Z
          "
          fill="url(#mountainFill)"
        />
      </svg>

      {/* Tagline */}
      <div
        className="mt-10 text-center px-6"
        style={{
          opacity: taglineVisible ? 1 : 0,
          transform: taglineVisible ? "translateY(0)" : "translateY(8px)",
          transition: "opacity 600ms ease-out, transform 600ms ease-out",
        }}
      >
        <p
          className="font-heading"
          style={{
            color: "#fff7ea",
            fontSize: "clamp(1.6rem, 3.8vw, 2.4rem)",
            letterSpacing: "0.02em",
            fontStyle: "italic",
            textShadow: "0 2px 10px rgba(0,0,0,0.25)",
          }}
        >
          “Who am I?”
        </p>
        <p
          className="mt-2 font-body"
          style={{
            color: "rgba(255, 247, 234, 0.78)",
            fontSize: "clamp(0.8rem, 1.6vw, 0.95rem)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Ramana Maharshi
        </p>
      </div>

      {/* Tiny skip hint, only when tagline is up, so we don't add clutter
          earlier. Non-interactive — the whole overlay dismisses on click. */}
      <div
        className="absolute bottom-6 right-6 font-body text-xs"
        style={{
          opacity: taglineVisible && phase !== "fadeout" ? 0.55 : 0,
          color: "#fff7ea",
          transition: "opacity 400ms ease-in-out",
          letterSpacing: "0.08em",
        }}
      >
        tap to continue
      </div>
    </div>
  );
}
