/**
 * RamanaOnboardingModal.tsx
 *
 * 3-screen "New to Ramana?" introduction for first-time landing-page visitors.
 * Screen 1 — Who is Ramana Maharshi?
 * Screen 2 — What is Self-Inquiry?  (universality message prominent)
 * Screen 3 — How to use this portal
 *
 * Auto-shown once per browser (localStorage flag "ramana_intro_v1_seen").
 * Can always be re-triggered by clicking "New to Ramana?" in the nav.
 *
 * Portrait: picks a random public-domain Ramana photo from Wikimedia Commons.
 * URLs are resolved via the Wikimedia API at runtime (not hardcoded) so they
 * never break if files move. Falls back to ॥ symbol if all fetches fail.
 */

import { useEffect, useState } from "react";
import { X, ArrowRight, ArrowLeft, MessageCircle, Image as ImageIcon, Headphones } from "lucide-react";

// ── Design tokens (match Landing.tsx exactly) ──────────────────────────────
const T = {
  cream:   "#F5F0EC",
  umber:   "#2E1208",
  brown:   "#472B20",
  muted:   "#8A6D5E",
  accent:  "#B85A2D",
  border:  "#E0D5CC",
  warm:    "#FDF0E8",
  warmBorder: "#F0D8C8",
  serif:   "'DM Serif Text', serif",
  sans:    "'Figtree', sans-serif",
};

const SEEN_KEY = "ramana_intro_v1_seen";

/**
 * Public-domain Ramana Maharshi photo filenames on Wikimedia Commons.
 * We resolve the actual URLs via the Wikimedia API at runtime so we
 * never need to hardcode MD5-derived path prefixes (which break silently).
 *
 * Correct MD5 thumb paths for reference (computed from filename):
 *   Ramana_Maharshi_-_1948.jpg                          → d/df
 *   Sri_Ramana_Maharshi_in_1902.jpg                     → 1/13
 *   Ramana-Maharshi-sit-1.jpg                           → c/c0
 *   Ramana-Maharshi-walk.jpg                            → 4/4b
 *   Sri_Ramana_Maharshi_-_Portrait_-_G._G_Welling_-_1948.jpg → 4/4c
 */
const RAMANA_FILENAMES = [
  "Ramana_Maharshi_-_1948.jpg",
  "Sri_Ramana_Maharshi_in_1902.jpg",
  "Ramana-Maharshi-sit-1.jpg",
  "Ramana-Maharshi-walk.jpg",
  "Sri_Ramana_Maharshi_-_Portrait_-_G._G_Welling_-_1948.jpg",
];

/**
 * Resolve a Wikimedia Commons filename to its actual image URL via the API.
 * Uses origin=* for CORS. Returns null on any failure.
 */
async function resolveWikimediaUrl(filename: string): Promise<string | null> {
  try {
    const api = `https://commons.wikimedia.org/w/api.php?action=query&titles=${encodeURIComponent("File:" + filename)}&prop=imageinfo&iiprop=url&iilimit=1&format=json&origin=*`;
    const res = await fetch(api, { signal: AbortSignal.timeout(6000) });
    if (!res.ok) return null;
    const data = await res.json();
    const pages = data?.query?.pages ?? {};
    const page  = Object.values(pages)[0] as any;
    return (page?.imageinfo?.[0]?.url as string) ?? null;
  } catch {
    return null;
  }
}

interface Props {
  onClose: () => void;
}

// ── Individual screen components ───────────────────────────────────────────

function Screen1({ portraitUrl }: { portraitUrl: string | null }) {
  return (
    <div>
      {/* Portrait — public-domain Ramana photo fetched via Wikimedia API */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: "1.5rem" }}>
        <div style={{
          width: 130, height: 155, borderRadius: "12px",
          border: `3px solid ${T.warmBorder}`,
          boxShadow: `0 0 0 6px ${T.warm}, 0 0 0 8px ${T.warmBorder}`,
          overflow: "hidden", backgroundColor: T.warm,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          {portraitUrl ? (
            <img
              src={portraitUrl}
              alt="Sri Ramana Maharshi"
              style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
            />
          ) : (
            <div style={{ fontFamily: T.serif, fontSize: "2.5rem", color: T.accent, lineHeight: 1 }}>॥</div>
          )}
        </div>
      </div>

      <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.55rem", textAlign: "center", marginBottom: "1rem", lineHeight: 1.25 }}>
        Who is Ramana Maharshi?
      </h2>

      <p style={{ fontFamily: T.sans, color: T.brown, fontSize: "0.9rem", lineHeight: 1.75, marginBottom: "1rem" }}>
        Born in 1879 in Tamil Nadu, India. At sixteen — without a teacher, without scripture,
        without seeking — he had a spontaneous and complete experience of Self-realisation.
      </p>

      <p style={{ fontFamily: T.sans, color: T.brown, fontSize: "0.9rem", lineHeight: 1.75, marginBottom: "1rem" }}>
        He was drawn to Arunachala, the sacred hill in Tiruvannamalai, and never left.
        For 54 years, thousands came from every corner of the world —
        <strong> regardless of religion, nationality or belief</strong> — and sat in his presence,
        or asked him their deepest questions.
      </p>

      <p style={{ fontFamily: T.sans, color: T.brown, fontSize: "0.9rem", lineHeight: 1.75, marginBottom: "1.25rem" }}>
        He taught one thing above all: <em>"You are not what you think you are. Find out what you truly are."</em>
      </p>

      {/* Quote */}
      <div style={{
        backgroundColor: T.warm, border: `1px solid ${T.warmBorder}`,
        borderRadius: 10, padding: "0.9rem 1.1rem",
      }}>
        <p style={{ fontFamily: T.serif, color: T.accent, fontSize: "0.95rem", fontStyle: "italic", lineHeight: 1.6, margin: 0 }}>
          "Your own Self-Realization is the greatest service you can render the world."
        </p>
        <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.75rem", marginTop: "0.4rem", marginBottom: 0 }}>
          — Sri Ramana Maharshi
        </p>
      </div>
    </div>
  );
}

function Screen2() {
  return (
    <div>
      <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.55rem", textAlign: "center", marginBottom: "1.1rem", lineHeight: 1.25 }}>
        What is Self-Inquiry?
      </h2>

      {/* Universality banner — prominent */}
      <div style={{
        backgroundColor: T.warm, border: `1px solid ${T.warmBorder}`,
        borderRadius: 10, padding: "0.85rem 1rem", marginBottom: "1.25rem",
      }}>
        <p style={{ fontFamily: T.sans, fontWeight: 700, color: T.accent, fontSize: "0.78rem", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.35rem" }}>
          Open to Everyone · No Beliefs Required
        </p>
        <p style={{ fontFamily: T.sans, color: T.brown, fontSize: "0.88rem", lineHeight: 1.65, margin: 0 }}>
          This is not a religion. It is not based on any belief system, doctrine or faith.
          Self-Inquiry is a <strong>direct, experiential investigation</strong> — like a scientist
          turning attention upon itself. People of every religion, and of none, practise it
          worldwide. You need bring only honest attention.
        </p>
      </div>

      <p style={{ fontFamily: T.sans, color: T.brown, fontSize: "0.9rem", lineHeight: 1.75, marginBottom: "1rem" }}>
        Ramana's core teaching is called <em>Atma Vichara</em> — Self-Inquiry. It is simply
        the practice of asking: <strong>"Who Am I?"</strong> — not as a philosophical puzzle,
        but as a direct look inward.
      </p>

      {/* 3-step visual */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem", marginBottom: "1.25rem" }}>
        {[
          { n: "1", text: "A thought or feeling arises." },
          { n: "2", text: 'Ask: "To whom does this arise?" — The answer is: "To me."' },
          { n: "3", text: 'Ask: "And who is this me?" — Trace the sense of "I" back to its source.' },
        ].map(({ n, text }) => (
          <div key={n} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
            <div style={{
              width: 24, height: 24, borderRadius: "50%", backgroundColor: T.accent,
              color: "#fff", fontFamily: T.sans, fontSize: "0.75rem", fontWeight: 700,
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1,
            }}>{n}</div>
            <p style={{ fontFamily: T.sans, color: T.brown, fontSize: "0.88rem", lineHeight: 1.6, margin: 0 }}>{text}</p>
          </div>
        ))}
      </div>

      {/* Quote */}
      <div style={{
        backgroundColor: T.warm, border: `1px solid ${T.warmBorder}`,
        borderRadius: 10, padding: "0.9rem 1.1rem",
      }}>
        <p style={{ fontFamily: T.serif, color: T.accent, fontSize: "0.95rem", fontStyle: "italic", lineHeight: 1.6, margin: 0 }}>
          "The question 'Who am I?' is not meant to get an answer — it is meant to dissolve the questioner."
        </p>
        <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.75rem", marginTop: "0.4rem", marginBottom: 0 }}>
          — Sri Ramana Maharshi
        </p>
      </div>
    </div>
  );
}

function Screen3({ onBegin }: { onBegin: () => void }) {
  const features = [
    {
      icon: <MessageCircle style={{ width: 18, height: 18, color: T.accent }} />,
      title: "Ask Bhagavan",
      desc: "Type any question. The AI responds using only Ramana's authenticated texts — not invented wisdom, only his actual words from verified sources.",
    },
    {
      icon: <ImageIcon style={{ width: 18, height: 18, color: T.accent }} />,
      title: "Contemplation Cards",
      desc: "After receiving an answer, generate a visual card with a key quote to save and reflect on daily.",
    },
    {
      icon: <Headphones style={{ width: 18, height: 18, color: T.accent }} />,
      title: "Guided Meditations",
      desc: "Generate a 3-minute audio or video meditation personalised to your question — a way to sit with the teaching, not just read it.",
    },
  ];

  return (
    <div>
      <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.55rem", textAlign: "center", marginBottom: "0.5rem", lineHeight: 1.25 }}>
        How to use this portal
      </h2>
      <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.88rem", textAlign: "center", marginBottom: "1.25rem", lineHeight: 1.6 }}>
        Built entirely around Self-Inquiry — open to everyone, from any background.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.9rem", marginBottom: "1.4rem" }}>
        {features.map(({ icon, title, desc }) => (
          <div key={title} style={{
            display: "flex", gap: "0.9rem", alignItems: "flex-start",
            backgroundColor: T.warm, border: `1px solid ${T.warmBorder}`,
            borderRadius: 10, padding: "0.85rem 1rem",
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%", backgroundColor: T.cream,
              border: `1px solid ${T.warmBorder}`, display: "flex", alignItems: "center",
              justifyContent: "center", flexShrink: 0,
            }}>
              {icon}
            </div>
            <div>
              <p style={{ fontFamily: T.sans, fontWeight: 700, color: T.brown, fontSize: "0.88rem", marginBottom: "0.2rem" }}>{title}</p>
              <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.82rem", lineHeight: 1.6, margin: 0 }}>{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Universal closing */}
      <div style={{
        textAlign: "center", fontFamily: T.serif, color: T.muted,
        fontSize: "0.9rem", fontStyle: "italic", lineHeight: 1.65,
        marginBottom: "1.4rem", padding: "0 0.5rem",
      }}>
        You don't need to be Hindu, or spiritual, or even sure you believe in anything.<br />
        You need only one honest question. That's always enough.
      </div>

      {/* CTA */}
      <button
        onClick={onBegin}
        style={{
          width: "100%", backgroundColor: T.accent, color: "#fff",
          fontFamily: T.sans, fontWeight: 700, fontSize: "0.9rem",
          padding: "0.8rem 1.5rem", border: "none", borderRadius: 8,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem",
        }}
      >
        Ask Bhagavan your first question <ArrowRight style={{ width: 16, height: 16 }} />
      </button>
    </div>
  );
}

// ── Main modal ─────────────────────────────────────────────────────────────

const RamanaOnboardingModal = ({ onClose }: Props) => {
  const [screen, setScreen] = useState(0); // 0, 1, 2
  const [sliding, setSliding] = useState<"left" | "right" | null>(null);
  const [portraitUrl, setPortraitUrl] = useState<string | null>(null);

  // On mount: pick a random filename, resolve its URL via the Wikimedia API.
  // If that file doesn't resolve, try the next one — cycles through all 5.
  useEffect(() => {
    let cancelled = false;
    const startIdx = Math.floor(Math.random() * RAMANA_FILENAMES.length);

    (async () => {
      for (let i = 0; i < RAMANA_FILENAMES.length; i++) {
        const filename = RAMANA_FILENAMES[(startIdx + i) % RAMANA_FILENAMES.length];
        const url = await resolveWikimediaUrl(filename);
        if (cancelled) return;
        if (url) {
          setPortraitUrl(url);
          return;
        }
      }
      // All failed — leave portraitUrl null, ॥ fallback shows
    })();

    return () => { cancelled = true; };
  }, []);

  const handleClose = () => {
    localStorage.setItem(SEEN_KEY, "1");
    onClose();
  };

  const goNext = () => {
    if (screen >= 2) return;
    setSliding("left");
    setTimeout(() => { setScreen(s => s + 1); setSliding(null); }, 280);
  };

  const goPrev = () => {
    if (screen <= 0) return;
    setSliding("right");
    setTimeout(() => { setScreen(s => s - 1); setSliding(null); }, 280);
  };

  const handleBegin = () => {
    handleClose();
    // Scroll to the chat section after a beat
    setTimeout(() => {
      document.getElementById("try")?.scrollIntoView({ behavior: "smooth" });
    }, 200);
  };

  const slideStyle: React.CSSProperties = {
    transition: "opacity 0.28s ease, transform 0.28s ease",
    opacity: sliding ? 0 : 1,
    transform: sliding === "left" ? "translateX(-24px)" : sliding === "right" ? "translateX(24px)" : "none",
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      backgroundColor: "rgba(30,10,5,0.55)", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "1rem",
    }}>
      <div style={{
        position: "relative", width: "100%", maxWidth: 500,
        backgroundColor: T.cream, borderRadius: 16,
        border: `1px solid ${T.border}`,
        boxShadow: "0 24px 64px rgba(20,6,2,0.35)",
        maxHeight: "92vh", overflowY: "auto",
        padding: "2rem 1.75rem 1.75rem",
      }}>

        {/* Close button */}
        <button
          onClick={handleClose}
          aria-label="Close"
          style={{
            position: "absolute", top: "1rem", right: "1rem",
            background: "none", border: "none", cursor: "pointer",
            color: T.muted, padding: "0.25rem",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <X style={{ width: 18, height: 18 }} />
        </button>

        {/* Progress dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: "0.45rem", marginBottom: "1.5rem" }}>
          {[0, 1, 2].map(i => (
            <div key={i} style={{
              width: i === screen ? 24 : 8, height: 8,
              borderRadius: 4,
              backgroundColor: i === screen ? T.accent : T.warmBorder,
              transition: "width 0.3s ease, background-color 0.3s ease",
            }} />
          ))}
        </div>

        {/* Screen content */}
        <div style={slideStyle}>
          {screen === 0 && <Screen1 portraitUrl={portraitUrl} />}
          {screen === 1 && <Screen2 />}
          {screen === 2 && <Screen3 onBegin={handleBegin} />}
        </div>

        {/* Navigation */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginTop: "1.5rem", paddingTop: "1rem",
          borderTop: `1px solid ${T.border}`,
        }}>
          {/* Back */}
          <button
            onClick={goPrev}
            disabled={screen === 0}
            style={{
              display: "flex", alignItems: "center", gap: "0.3rem",
              background: "none", border: "none", cursor: screen === 0 ? "default" : "pointer",
              fontFamily: T.sans, fontSize: "0.82rem", color: screen === 0 ? T.border : T.muted,
              padding: "0.4rem 0", transition: "color 0.2s",
            }}
          >
            <ArrowLeft style={{ width: 14, height: 14 }} /> Back
          </button>

          {/* Skip / step count */}
          <button
            onClick={handleClose}
            style={{
              background: "none", border: "none", cursor: "pointer",
              fontFamily: T.sans, fontSize: "0.78rem", color: T.muted,
              padding: "0.4rem 0.6rem",
            }}
          >
            Skip intro
          </button>

          {/* Next (hidden on last screen — replaced by CTA in Screen3) */}
          {screen < 2 ? (
            <button
              onClick={goNext}
              style={{
                display: "flex", alignItems: "center", gap: "0.3rem",
                background: "none", border: "none", cursor: "pointer",
                fontFamily: T.sans, fontSize: "0.82rem", fontWeight: 600,
                color: T.accent, padding: "0.4rem 0", transition: "opacity 0.2s",
              }}
            >
              Next <ArrowRight style={{ width: 14, height: 14 }} />
            </button>
          ) : (
            <div style={{ width: 60 }} /> /* spacer to keep layout balanced */
          )}
        </div>
      </div>
    </div>
  );
};

export default RamanaOnboardingModal;
export { SEEN_KEY };
