/**
 * Landing.tsx — Public landing page for Arunachala Samudra (.co.in)
 *
 * Entry experience:
 *   • IntroScreen — atmospheric overlay, "Who Am I?" holds 3s then fades 0.8s.
 *     Shown once per browser session (sessionStorage flag).
 *   • Landing — full page matching arunachalasamudra.in look & feel.
 *
 * Sections (in order):
 *   1. PublicHeader   — two-row sticky (logo row + nav row)
 *   2. HeroSection    — full-bleed atmospheric gradient + ghost "ARUNACHALA" watermark
 *   3. SelfEnquiryBanner — terracotta split, floating quote card
 *   4. DailyContemplation — atmospheric dark card (free, live API)
 *   5. SacredLibrary  — five texts, cream + mandala watermark
 *   6. FeaturesSection — "What's Inside": 4 portal features only
 *   7. PricingSection — dual USD + INR pricing
 *   8. FinalCTA
 *   9. Footer         — dark chocolate, 5-column, subscribe form, mandala
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { TEACHINGS } from "@/data/teachings";
import {
  BookOpen, Sparkles, MessageCircle, Music,
  ChevronDown, ChevronUp, ArrowRight, CheckCircle2,
  Menu, X, Mail, Layers, Send, Lock,
  Image as ImageIcon, Volume2, Video, Download,
} from "lucide-react";
import RamanaOnboardingModal, { SEEN_KEY } from "@/components/RamanaOnboardingModal";

// ─── Design tokens (matching arunachalasamudra.in) ────────────────────────────
const T = {
  cream:      "#F5F0EC",
  creamMid:   "#EDE5DC",
  umber:      "#2E1208",   // deep chocolate — footer / dark sections
  brown:      "#472B20",   // primary text / logo
  muted:      "#8A6D5E",
  accent:     "#B85A2D",   // terracotta CTA
  border:     "#E0D5CC",
  warmBorder: "#F0D8C8",   // used in header "New to Ramana?" button border
  serif:      "'DM Serif Text', serif",
  sans:       "'Figtree', sans-serif",
};

// Shared terracotta button style (rounded-rect, NOT pill — matches .in site)
const btn: React.CSSProperties = {
  backgroundColor: T.accent,
  color: "#fff",
  fontFamily: T.sans,
  fontSize: "0.85rem",
  fontWeight: 600,
  padding: "0.6rem 1.4rem",
  borderRadius: "5px",
  display: "inline-block",
  cursor: "pointer",
  transition: "opacity 0.2s",
  textDecoration: "none",
};

// ─── Decorative mandala SVG watermark ─────────────────────────────────────────
function Mandala({
  size = 500, color = T.brown, opacity = 0.07,
  style,
}: { size?: number; color?: string; opacity?: number; style?: React.CSSProperties }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 200 200"
      aria-hidden="true"
      style={{ opacity, pointerEvents: "none", userSelect: "none", flexShrink: 0, ...style }}
    >
      {[0, 30, 60, 90, 120, 150].map(r => (
        <g key={r} transform={`rotate(${r} 100 100)`}>
          <ellipse cx="100" cy="52" rx="8" ry="24" fill="none" stroke={color} strokeWidth="1" />
          <ellipse cx="100" cy="52" rx="4" ry="13" fill="none" stroke={color} strokeWidth="0.5" />
        </g>
      ))}
      <circle cx="100" cy="100" r="52" fill="none" stroke={color} strokeWidth="1" />
      <circle cx="100" cy="100" r="36" fill="none" stroke={color} strokeWidth="0.5" />
      <circle cx="100" cy="100" r="18" fill="none" stroke={color} strokeWidth="1" />
      <circle cx="100" cy="100" r="6"  fill={color} />
    </svg>
  );
}

// ─── 1. Intro Screen ──────────────────────────────────────────────────────────
// Shown once per browser session. Atmospheric overlay with "Who Am I?".
function IntroScreen({ onDone }: { onDone: () => void }) {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    // Start fade-out at 3s, fully gone at 3.8s
    const t1 = setTimeout(() => setFading(true), 3000);
    const t2 = setTimeout(() => onDone(), 3800);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [onDone]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        opacity: fading ? 0 : 1,
        transition: "opacity 0.8s ease-in-out",
        pointerEvents: fading ? "none" : "all",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: `
          linear-gradient(
            to bottom,
            #0f0704 0%,
            #1e0c06 12%,
            #3d1a0a 30%,
            #7a3318 48%,
            #b05828 62%,
            #7a3318 76%,
            #3d1a0a 88%,
            #1e0c06 100%
          )
        `,
        overflow: "hidden",
      }}
    >
      {/* Radial warm glow */}
      <div
        style={{
          position: "absolute", inset: 0, pointerEvents: "none",
          background: "radial-gradient(ellipse 80% 60% at 50% 55%, rgba(190,100,45,0.5) 0%, transparent 70%)",
        }}
      />

      {/* Ghost "ARUNACHALA" watermark */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          whiteSpace: "nowrap",
          fontFamily: T.serif,
          fontSize: "clamp(4rem, 18vw, 16rem)",
          color: "rgba(245,210,180,0.06)",
          letterSpacing: "0.06em",
          lineHeight: 1,
          userSelect: "none",
          pointerEvents: "none",
        }}
      >
        ARUNACHALA
      </div>

      {/* Mountain silhouette */}
      <svg
        viewBox="0 0 1440 300" preserveAspectRatio="none"
        style={{ position: "absolute", bottom: 0, left: 0, width: "100%", height: "180px", pointerEvents: "none" }}
        aria-hidden="true"
      >
        <path d="M0 300 L0 210 Q120 170 220 190 Q360 215 460 145 Q560 75 640 110 Q700 140 720 95 Q740 50 800 80 Q870 115 940 95 Q1020 60 1100 115 Q1180 170 1280 150 Q1360 135 1440 170 L1440 300 Z" fill="rgba(10,4,2,0.75)" />
        <path d="M0 300 L0 260 Q200 245 340 252 Q500 260 600 210 Q650 178 700 192 Q724 200 750 182 Q810 152 880 170 Q970 195 1080 172 Q1200 150 1320 198 L1440 215 L1440 300 Z" fill="rgba(10,4,2,0.9)" />
      </svg>

      {/* Main text */}
      <div style={{ position: "relative", zIndex: 10, textAlign: "center", padding: "0 2rem" }}>
        {/* Om symbol */}
        <p
          style={{ fontFamily: T.serif, color: "rgba(245,200,160,0.35)", fontSize: "2.5rem", marginBottom: "1.5rem", letterSpacing: "0.1em" }}
          aria-hidden="true"
        >
          ॐ
        </p>

        <h1
          style={{
            fontFamily: T.serif,
            color: "#F5F0EC",
            fontSize: "clamp(3rem, 10vw, 7.5rem)",
            lineHeight: 1.1,
            marginBottom: "1.25rem",
            fontStyle: "italic",
            letterSpacing: "-0.01em",
          }}
        >
          Who Am I?
        </h1>

        <p
          style={{
            fontFamily: T.sans,
            color: "rgba(245,210,180,0.55)",
            fontSize: "clamp(0.85rem, 2vw, 1rem)",
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            fontWeight: 400,
          }}
        >
          The Essential Inquiry of Sri Ramana Maharshi
        </p>

        {/* Subtle pulsing line */}
        <div
          style={{ width: "60px", height: "1px", backgroundColor: "rgba(245,200,160,0.25)", margin: "2rem auto 0" }}
        />
      </div>
    </div>
  );
}

// ─── 2. Header ────────────────────────────────────────────────────────────────
function PublicHeader({ isAuthenticated, onNewToRamana }: { isAuthenticated: boolean; onNewToRamana: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        backgroundColor: scrolled ? "rgba(245,240,236,0.94)" : T.cream,
        backdropFilter: scrolled ? "blur(14px)" : "none",
        WebkitBackdropFilter: scrolled ? "blur(14px)" : "none",
        transition: "background-color 0.25s, backdrop-filter 0.25s",
        borderBottom: `1px solid ${T.border}`,
      }}
    >
      {/* Row 1 — logo + email */}
      <div
        style={{ borderBottom: `1px solid ${T.border}` }}
        className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between"
      >
        <a href="https://www.arunachalasamudra.in" style={{ textDecoration: "none" }}>
          <span style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.3rem", letterSpacing: "-0.01em" }}>
            Arunachala Samudra
          </span>
        </a>
        <div className="hidden md:flex items-center gap-1.5" style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.82rem" }}>
          <Mail className="w-3.5 h-3.5" />
          <a href="mailto:info@arunachalasamudra.co.in" className="hover:opacity-70 transition-opacity">
            info@arunachalasamudra.co.in
          </a>
        </div>
        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2"
          style={{ color: T.brown }}
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Row 2 — nav (desktop) */}
      <div className="hidden md:flex max-w-7xl mx-auto px-6 h-11 items-center justify-between">
        <nav className="flex items-center gap-8">
          {[
            { label: "Teachings",          href: "#teachings"    },
            { label: "Daily Contemplation",href: "#contemplation"},
            { label: "Try Free",           href: "#try"          },
            { label: "Features",           href: "#features"     },
            { label: "Pricing",            href: "#pricing"      },
          ].map(({ label, href }) => (
            <a
              key={label} href={href}
              style={{ color: T.brown, fontFamily: T.sans, fontSize: "0.85rem" }}
              className="hover:opacity-60 transition-opacity"
            >
              {label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-4">
          {/* "New to Ramana?" — softly styled trigger */}
          {!isAuthenticated && (
            <button
              onClick={onNewToRamana}
              style={{
                fontFamily: T.sans, fontSize: "0.82rem", color: T.accent,
                background: "none", border: `1px solid ${T.warmBorder}`,
                borderRadius: 5, padding: "0.3rem 0.75rem", cursor: "pointer",
                display: "flex", alignItems: "center", gap: "0.3rem",
              }}
            >
              ✦ New to Ramana?
            </button>
          )}
          <Link to="/signin" style={{ color: T.brown, fontFamily: T.sans, fontSize: "0.85rem" }} className="hover:opacity-60 transition-opacity">
            Sign In
          </Link>
          {isAuthenticated ? (
            <Link to="/home" style={btn}>Go to Portal →</Link>
          ) : (
            <a href="#try" style={btn}>Begin — it's free</a>
          )}
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div style={{ backgroundColor: T.cream, borderTop: `1px solid ${T.border}` }} className="md:hidden px-6 pb-6 pt-4">
          <div className="space-y-1 mb-4">
            {[
              { label: "Teachings",          href: "#teachings"    },
              { label: "Daily Contemplation",href: "#contemplation"},
              { label: "Features",           href: "#features"     },
              { label: "Pricing",            href: "#pricing"      },
            ].map(({ label, href }) => (
              <a
                key={label} href={href}
                style={{ color: T.brown, fontFamily: T.sans, display: "block", padding: "0.5rem 0" }}
                onClick={() => setMenuOpen(false)}
              >
                {label}
              </a>
            ))}
          </div>
          <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: "1rem" }} className="flex flex-col gap-3">
            {!isAuthenticated && (
              <button
                onClick={() => { setMenuOpen(false); onNewToRamana(); }}
                style={{ fontFamily: T.sans, color: T.accent, background: "none", border: `1px solid ${T.warmBorder}`, borderRadius: 5, padding: "0.5rem 0.75rem", cursor: "pointer", textAlign: "left" }}
              >
                ✦ New to Ramana? Start here
              </button>
            )}
            <Link to="/signin" style={{ color: T.brown, fontFamily: T.sans }} onClick={() => setMenuOpen(false)}>Sign In</Link>
            {isAuthenticated ? (
              <Link to="/home" style={{ ...btn, textAlign: "center" }} onClick={() => setMenuOpen(false)}>Go to Portal →</Link>
            ) : (
              <a href="#try" style={{ ...btn, textAlign: "center" }} onClick={() => setMenuOpen(false)}>Begin — it's free</a>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

// ─── 3. Hero ─────────────────────────────────────────────────────────────────
function HeroSection({ isAuthenticated, onNewToRamana }: { isAuthenticated: boolean; onNewToRamana: () => void }) {
  return (
    <section
      style={{
        position: "relative",
        overflow: "hidden",
        minHeight: "92vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(to bottom, #0f0704 0%, #1e0c06 12%, #3d1a0a 30%, #7a3318 48%, #b05828 62%, #7a3318 76%, #3d1a0a 88%, #1e0c06 100%)",
      }}
    >
      {/* Warm glow */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "radial-gradient(ellipse 90% 55% at 50% 60%, rgba(180,90,40,0.45) 0%, transparent 70%)" }} />

      {/* Ghost watermark */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute", top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          whiteSpace: "nowrap", pointerEvents: "none", userSelect: "none",
          fontFamily: T.serif,
          fontSize: "clamp(5rem, 20vw, 18rem)",
          color: "rgba(245,210,180,0.07)",
          letterSpacing: "0.05em", lineHeight: 1,
        }}
      >
        ARUNACHALA
      </div>

      {/* Mountain silhouette */}
      <svg viewBox="0 0 1440 320" preserveAspectRatio="none"
        style={{ position: "absolute", bottom: 0, left: 0, width: "100%", height: "200px", pointerEvents: "none" }} aria-hidden="true">
        <path d="M0 320 L0 220 Q120 180 200 200 Q320 220 400 160 Q520 80 600 120 Q680 160 720 100 Q760 40 800 80 Q860 120 920 100 Q1000 60 1080 120 Q1160 180 1240 160 Q1340 140 1440 180 L1440 320 Z" fill="rgba(15,7,4,0.7)" />
        <path d="M0 320 L0 260 Q180 240 300 250 Q480 260 560 210 Q620 170 680 190 Q720 200 760 180 Q820 150 880 170 Q960 195 1060 175 Q1180 155 1300 200 Q1380 225 1440 220 L1440 320 Z" fill="rgba(15,7,4,0.9)" />
      </svg>

      {/* Content */}
      <div style={{ position: "relative", zIndex: 10, textAlign: "center", padding: "0 1.5rem", maxWidth: "860px", margin: "0 auto" }}>
        <h1 style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "clamp(2.2rem, 6vw, 4rem)", lineHeight: 1.18, marginBottom: "1.5rem" }}>
          The complete teachings of
          <br />Sri Ramana Maharshi,
          <br /><em style={{ color: "rgba(220,160,110,0.9)" }}>alive and answering.</em>
        </h1>
        <p style={{ fontFamily: T.sans, color: "rgba(245,220,200,0.68)", fontSize: "1.05rem", lineHeight: 1.7, maxWidth: "540px", margin: "0 auto 2.5rem" }}>
          Ask any question from the sacred library — Who Am I?, Forty Verses, Upadesa Saram and more — and receive answers drawn solely from Bhagavan's authenticated words.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          {isAuthenticated ? (
            <Link to="/home" style={{ ...btn, fontSize: "0.95rem", padding: "0.85rem 2rem", display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
              Continue to portal <ArrowRight className="w-4 h-4" />
            </Link>
          ) : (
            <>
              <a href="#try" style={{ ...btn, fontSize: "0.95rem", padding: "0.85rem 2rem", display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
                Begin — it's free <ArrowRight className="w-4 h-4" />
              </a>
              <Link to="/signin" style={{ fontFamily: T.sans, fontSize: "0.95rem", fontWeight: 600, padding: "0.85rem 2rem", borderRadius: "5px", border: "1px solid rgba(245,220,200,0.28)", color: "rgba(245,220,200,0.88)", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                Sign in
              </Link>
            </>
          )}
        </div>
        <p style={{ fontFamily: T.sans, color: "rgba(200,170,140,0.5)", fontSize: "0.78rem", marginTop: "1.5rem" }}>
          No credit card required · Free plan available · Answers from authenticated texts only
        </p>
        {/* "New to Ramana?" ghost link — shown only to unauthenticated visitors */}
        {!isAuthenticated && (
          <button
            onClick={onNewToRamana}
            style={{
              marginTop: "1.25rem",
              background: "none", border: "none", cursor: "pointer",
              fontFamily: T.sans, fontSize: "0.82rem",
              color: "rgba(210,170,130,0.7)",
              display: "inline-flex", alignItems: "center", gap: "0.35rem",
              textDecoration: "underline", textDecorationColor: "rgba(210,170,130,0.3)",
            }}
          >
            First time here? Start with a 2-minute introduction →
          </button>
        )}
      </div>
    </section>
  );
}

// ─── 4. Terracotta "Path of Self-Enquiry" split ────────────────────────────────
function SelfEnquiryBanner({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <section style={{ backgroundColor: "#8B3A1A", position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "radial-gradient(ellipse 80% 100% at 80% 50%, rgba(180,90,40,0.3) 0%, transparent 70%)" }} />
      <div className="max-w-7xl mx-auto px-6 py-20 flex flex-col md:flex-row items-center gap-12 relative z-10">
        <div className="flex-1">
          <h2 style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "clamp(2rem, 5vw, 3.5rem)", lineHeight: 1.15, marginBottom: "1.25rem" }}>
            The Path of
            <br />Self-Enquiry
          </h2>
          <p style={{ fontFamily: T.sans, color: "rgba(245,220,200,0.72)", fontSize: "1rem", lineHeight: 1.7, maxWidth: "400px", marginBottom: "2rem" }}>
            Explore the timeless wisdom of Bhagavan Sri Ramana Maharshi — his key teachings and direct guidance on 'Who Am I?'.
          </p>
          <Link to={isAuthenticated ? "/home" : "/register"} style={{ ...btn, backgroundColor: "#fff", color: "#8B3A1A" }}>
            Go to Wisdom Portal
          </Link>
        </div>
        {/* Floating white quote card — exactly like the .in Ramana section */}
        <div className="flex-1 flex justify-center md:justify-end">
          <div style={{ backgroundColor: "#fff", borderRadius: "4px", padding: "2rem 2.5rem", maxWidth: "340px", boxShadow: "0 20px 60px rgba(0,0,0,0.25)" }}>
            <p style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.1rem", lineHeight: 1.65, marginBottom: "1rem", fontStyle: "italic" }}>
              "The universe is real if perceived as the Self, and unreal if perceived apart from the Self."
            </p>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.8rem", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>
              Sri Ramana Maharshi
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── 5. Daily Contemplation — atmospheric sunset card (free, public API) ──────
interface Contemplation { date: string; quote: string; question: string; }

function DailyContemplationSection() {
  const [data, setData] = useState<Contemplation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/contemplation/today")
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => {
        setData({ date: new Date().toISOString().slice(0, 10), quote: "Silence is the true teaching. Sit quietly and notice what remains when thought subsides.", question: "Who is the one who is aware right now?" });
        setLoading(false);
      });
  }, []);

  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <section id="contemplation" style={{ backgroundColor: T.cream }} className="py-20 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row gap-14 items-start">
          {/* Left — heading */}
          <div className="md:w-1/3 md:pt-2">
            <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem" }}>
              Free · No Login Required
            </p>
            <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "clamp(2rem, 4vw, 3rem)", lineHeight: 1.2, marginBottom: "1rem" }}>
              Daily Sacred
              <br />Contemplation
            </h2>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.9rem", lineHeight: 1.65, marginBottom: "1rem" }}>
              A new teaching is drawn each morning from Bhagavan's words. Come back any day — no account needed.
            </p>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.82rem" }}>{today}</p>
          </div>

          {/* Right — atmospheric card (Arunachala sunset style) */}
          <div className="md:w-2/3">
            {loading ? (
              <div style={{ background: "linear-gradient(135deg, #1e0c06 0%, #5c2510 40%, #8b4520 70%, #3d1a0a 100%)", borderRadius: "6px", padding: "3rem", minHeight: "260px", display: "flex", alignItems: "center" }}>
                <div className="w-full space-y-3">
                  <div className="h-4 bg-white/10 rounded animate-pulse" /><div className="h-4 bg-white/10 rounded animate-pulse w-4/5" /><div className="h-4 bg-white/10 rounded animate-pulse w-3/5" />
                </div>
              </div>
            ) : data ? (
              <div style={{ background: "linear-gradient(135deg, #1a0a04 0%, #4a2010 35%, #8b4520 60%, #5c2510 80%, #1a0a04 100%)", borderRadius: "6px", padding: "3rem 3rem 2.5rem", position: "relative", overflow: "hidden", boxShadow: "0 25px 70px rgba(0,0,0,0.28)" }}>
                <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "radial-gradient(ellipse 70% 60% at 60% 40%, rgba(180,100,50,0.38) 0%, transparent 70%)" }} />
                {/* SVG palm silhouettes */}
                <svg viewBox="0 0 500 200" style={{ position: "absolute", bottom: 0, right: 0, width: "220px", opacity: 0.15, pointerEvents: "none" }} aria-hidden="true">
                  <line x1="340" y1="200" x2="340" y2="75" stroke="#F5F0EC" strokeWidth="3" />
                  <path d="M340 75 Q312 38 272 52 Q304 62 316 86 Z" fill="#F5F0EC" /><path d="M340 75 Q322 28 352 12 Q350 48 358 72 Z" fill="#F5F0EC" /><path d="M340 75 Q366 32 402 46 Q378 58 360 82 Z" fill="#F5F0EC" />
                  <line x1="420" y1="200" x2="420" y2="95" stroke="#F5F0EC" strokeWidth="2.5" />
                  <path d="M420 95 Q396 62 358 75 Q390 83 403 105 Z" fill="#F5F0EC" /><path d="M420 95 Q440 52 470 65 Q448 75 436 98 Z" fill="#F5F0EC" />
                </svg>
                {/* Decorative quote mark */}
                <span aria-hidden="true" style={{ fontFamily: T.serif, color: "rgba(245,200,160,0.18)", fontSize: "5.5rem", lineHeight: 0.7, position: "absolute", top: "1.25rem", left: "1.75rem", userSelect: "none" }}>"</span>
                <div style={{ position: "relative", zIndex: 10 }}>
                  <p style={{ fontFamily: T.sans, color: "rgba(245,200,160,0.65)", fontSize: "0.72rem", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600, marginBottom: "1.25rem" }}>
                    {new Date().toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" })}
                  </p>
                  <p style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "clamp(1.1rem, 2.5vw, 1.4rem)", lineHeight: 1.65, marginBottom: "2rem" }}>
                    {data.quote}
                  </p>
                  <div style={{ borderTop: "1px solid rgba(245,200,160,0.18)", paddingTop: "1.25rem" }}>
                    <p style={{ fontFamily: T.sans, color: "rgba(245,200,160,0.6)", fontSize: "0.7rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.5rem" }}>Inquiry for today</p>
                    <p style={{ fontFamily: T.serif, color: "rgba(245,220,190,0.9)", fontSize: "1.05rem", fontStyle: "italic" }}>{data.question}</p>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── 6. Sacred Library ────────────────────────────────────────────────────────
function BookCard({ teaching }: { teaching: typeof TEACHINGS[0] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{ backgroundColor: "#FBF7F3", border: `1px solid ${T.border}`, borderRadius: "4px" }} className="overflow-hidden hover:shadow-md transition-shadow">
      <div className="p-6">
        <span style={{ backgroundColor: T.creamMid, color: T.muted, fontFamily: T.sans, fontSize: "0.7rem", letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600 }} className="inline-block px-2.5 py-1 rounded mb-4">
          {teaching.era}
        </span>
        <h3 style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.25rem", marginBottom: "0.25rem" }}>{teaching.title}</h3>
        <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.8rem", fontStyle: "italic", marginBottom: "0.85rem" }}>{teaching.sanskrit} · {teaching.author}</p>
        <p style={{ fontFamily: T.sans, color: "#6B4F42", fontSize: "0.9rem", lineHeight: 1.65, marginBottom: "1rem" }}>{teaching.teaser}</p>
        {expanded && (
          <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: "1rem", marginBottom: "0.75rem" }}>
            {teaching.introduction.split("\n\n").map((para, i) => (
              <p key={i} style={{ fontFamily: T.sans, color: "#5C3D30", fontSize: "0.87rem", lineHeight: 1.7, marginBottom: "0.75rem" }}>{para.trim()}</p>
            ))}
          </div>
        )}
        <button onClick={() => setExpanded(e => !e)} style={{ color: T.accent, fontFamily: T.sans, fontSize: "0.83rem", fontWeight: 600 }} className="flex items-center gap-1 hover:opacity-70 transition-opacity">
          {expanded ? <><ChevronUp className="w-4 h-4" />Show less</> : <><ChevronDown className="w-4 h-4" />Read introduction</>}
        </button>
      </div>
      <div style={{ backgroundColor: T.creamMid, borderTop: `1px solid ${T.border}` }} className="px-6 py-3.5">
        <Link to="/register" style={{ color: T.brown, fontFamily: T.sans, fontSize: "0.83rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "4px" }} className="hover:gap-2 transition-all">
          Ask Wisdom AI about this teaching <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}

function SacredLibrarySection() {
  return (
    <section id="teachings" style={{ backgroundColor: T.cream, position: "relative", overflow: "hidden" }} className="py-20 px-6">
      <div style={{ position: "absolute", right: "-80px", top: "50%", transform: "translateY(-50%)" }}>
        <Mandala size={500} opacity={0.06} color={T.brown} />
      </div>
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="mb-14">
          <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem" }}>The Sacred Library</p>
          <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "clamp(2rem, 4vw, 3rem)", lineHeight: 1.2, marginBottom: "1rem", maxWidth: "560px" }}>
            Five texts.<br />A lifetime of depth.
          </h2>
          <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.95rem", lineHeight: 1.7, maxWidth: "520px" }}>
            The Wisdom Portal draws exclusively from these authenticated works — every answer is grounded in Bhagavan's own words.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {TEACHINGS.map(t => <BookCard key={t.id} teaching={t} />)}
        </div>
      </div>
    </section>
  );
}

// ─── 7. Features — "What's Inside the Portal" ─────────────────────────────────
// Note: Daily Contemplation and Sacred Library are already shown as full
// sections above, so they are intentionally NOT listed here.
// ─── Guest Chat ───────────────────────────────────────────────────────────────
const GUEST_SESSION_ID_KEY   = "as_guest_sid";
const GUEST_MSG_COUNT_KEY    = "as_guest_count";
const GUEST_MESSAGES_KEY     = "as_guest_msgs";
const GUEST_CONTENT_COUNT_KEY = "as_guest_content_count";
const GUEST_LIMIT            = 5;
const GUEST_CONTENT_LIMIT    = 3;
const API_BASE               = (import.meta.env.VITE_API_BASE_URL as string || "/api").replace(/\/$/, "");

type GMsg = { role: "user" | "assistant"; content: string };
type GenStatus = "idle" | "pending" | "processing" | "complete" | "failed";

function getGuestSessionId(): string {
  // localStorage persists across tab/window close — critical for rate limiting.
  // sessionStorage resets on close, which would allow users to bypass limits
  // by simply reopening the browser.
  try {
    let id = localStorage.getItem(GUEST_SESSION_ID_KEY);
    if (!id) {
      id = `g_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      localStorage.setItem(GUEST_SESSION_ID_KEY, id);
    }
    return id;
  } catch { return `g_${Date.now()}`; }
}

function GuestChatSection() {
  const [messages, setMessages] = useState<GMsg[]>(() => {
    // localStorage so conversation persists across tab close/reopen
    try { return JSON.parse(localStorage.getItem(GUEST_MESSAGES_KEY) || "[]"); }
    catch { return []; }
  });
  const [input, setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [count, setCount]   = useState<number>(() => {
    try { return parseInt(localStorage.getItem(GUEST_MSG_COUNT_KEY) || "0", 10); }
    catch { return 0; }
  });
  const [showModal, setShowModal] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const msgLenRef = useRef(0);

  // ── Content generation state ──────────────────────────────────────────────
  const [genMode,      setGenMode]      = useState<"image"|"audio"|"video"|null>(null);
  const [genStatus,    setGenStatus]    = useState<GenStatus>("idle");
  const [genContentId, setGenContentId] = useState<string|null>(null);
  const [genUrl,       setGenUrl]       = useState<string|null>(null);
  const [genType,      setGenType]      = useState<string|null>(null);
  const [genError,     setGenError]     = useState<string|null>(null);
  const [contentCount, setContentCount] = useState<number>(() => {
    try { return parseInt(localStorage.getItem(GUEST_CONTENT_COUNT_KEY) || "0", 10); }
    catch { return 0; }
  });

  // Poll for content status
  useEffect(() => {
    if (!genContentId || genStatus === "complete" || genStatus === "failed") return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/content/guest/${genContentId}`);
        if (!res.ok) return;
        const data = await res.json();
        setGenStatus(data.status);
        if (data.status === "complete") {
          setGenUrl(data.content_url);
          setGenType(data.content_type);
          clearInterval(timer);
        } else if (data.status === "failed") {
          setGenError(data.error || "Generation failed. Please try again.");
          clearInterval(timer);
        }
      } catch {}
    }, 2500);
    return () => clearInterval(timer);
  }, [genContentId, genStatus]);

  // Only auto-scroll when a new message pair is added (user sent a message),
  // NOT on every streaming token update. This prevents competing with the
  // user's own page scroll while the assistant is responding.
  useEffect(() => {
    if (messages.length !== msgLenRef.current) {
      msgLenRef.current = messages.length;
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const saveMsgs = (msgs: GMsg[]) => {
    try { localStorage.setItem(GUEST_MESSAGES_KEY, JSON.stringify(msgs.slice(-20))); } catch {}
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;
    if (count >= GUEST_LIMIT) { setShowModal(true); return; }

    const sid       = getGuestSessionId();
    const newCount  = count + 1;
    setCount(newCount);
    try { localStorage.setItem(GUEST_MSG_COUNT_KEY, String(newCount)); } catch {}

    const userMsg: GMsg = { role: "user", content: q };
    const prev = [...messages, userMsg];
    const withPlaceholder: GMsg[] = [...prev, { role: "assistant", content: "" }];
    setMessages(withPlaceholder);
    saveMsgs(prev);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat/guest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: q,
          session_id: sid,
          history: messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
        }),
      });

      if (!res.ok) {
        if (res.status === 429) { setShowModal(true); setMessages(prev); saveMsgs(prev); setLoading(false); return; }
        throw new Error("Failed");
      }

      const reader  = res.body!.getReader();
      const decoder = new TextDecoder();
      let partial   = "";
      let aiText    = "";

      outer: while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        partial += decoder.decode(value, { stream: true });
        const lines = partial.split("\n");
        partial = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim() || line === "[DONE]") continue;
          try {
            let content = "";
            if (line.startsWith("data: ")) {
              const jstr = line.slice(6).trim();
              if (jstr === "[DONE]") continue;
              const cd = JSON.parse(jstr);
              content = cd.choices?.[0]?.delta?.content || "";
            }
            // Skip backend metadata tags
            if (content && /<(message_id|citations|questions|title)[^>]*>/.test(content)) continue;
            if (content) {
              aiText += content;
              setMessages(p => {
                const u = [...p];
                u[u.length - 1] = { role: "assistant", content: aiText };
                return u;
              });
            }
          } catch {}
        }
      }

      // If the backend returned a "no passages found" message, it wasn't a real
      // answer — roll back the count so the user doesn't lose a free message.
      const NO_PASSAGE_MARKER = "The passages available do not yet cover";
      if (aiText.startsWith(NO_PASSAGE_MARKER)) {
        setCount(count);  // revert to pre-send value
        try { localStorage.setItem(GUEST_MSG_COUNT_KEY, String(count)); } catch {}
      }

      const finalMsgs: GMsg[] = [...prev, { role: "assistant", content: aiText || "…" }];
      setMessages(finalMsgs);
      saveMsgs(finalMsgs);
      if (newCount >= GUEST_LIMIT && !aiText.startsWith(NO_PASSAGE_MARKER)) {
        setTimeout(() => setShowModal(true), 1800);
      }
    } catch {
      const errMsgs: GMsg[] = [...prev, { role: "assistant", content: "Unable to respond right now. Please try again." }];
      setMessages(errMsgs);
      saveMsgs(errMsgs);
    } finally {
      setLoading(false);
    }
  };

  // ── Reset result view — go back to chat + format buttons ─────────────────
  const resetResult = () => {
    setGenStatus("idle");
    setGenContentId(null);
    setGenUrl(null);
    setGenType(null);
    setGenError(null);
    setGenMode(null);
  };

  // ── Generate content from last Q&A ────────────────────────────────────────
  const handleGenerate = async (mode: "image" | "audio" | "video") => {
    // Find last user + assistant pair
    let question = "", answer = "";
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant" && messages[i].content && !answer) answer = messages[i].content;
      if (messages[i].role === "user" && messages[i].content && !question) { question = messages[i].content; break; }
    }
    if (!question || !answer) return;

    // Reset any previous result before starting a new generation
    setGenMode(mode);
    setGenStatus("pending");
    setGenUrl(null);
    setGenType(null);
    setGenError(null);
    setGenContentId(null);

    try {
      const res = await fetch(`${API_BASE}/content/guest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, answer, mode, session_id: getGuestSessionId() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (res.status === 429) {
          setGenError("You've reached the free generation limit for today. Sign up for more.");
        } else {
          setGenError(err.detail || "Generation failed.");
        }
        setGenStatus("failed");
        return;
      }
      const data = await res.json();
      setGenContentId(data.content_id);
      setGenStatus("processing");
      const newCount = contentCount + 1;
      setContentCount(newCount);
      try { localStorage.setItem(GUEST_CONTENT_COUNT_KEY, String(newCount)); } catch {}
    } catch {
      setGenError("Network error. Please try again.");
      setGenStatus("failed");
    }
  };

  const remaining = Math.max(0, GUEST_LIMIT - count);
  const hasQA = messages.length >= 2 && messages.some(m => m.role === "user") && messages.some(m => m.role === "assistant" && m.content.length > 10);
  const isGenerating = genStatus === "pending" || genStatus === "processing";
  const genDone = genStatus === "complete";

  return (
    <section id="try" style={{ backgroundColor: T.umber, position: "relative", overflow: "hidden" }} className="py-20 px-6">
      {/* Atmospheric radial glow */}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 60% 70% at 50% 40%, rgba(184,90,45,0.15) 0%, transparent 70%)", pointerEvents: "none" }} />

      {/* Sign-up modal overlay */}
      {showModal && (
        <div style={{ position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "1.5rem" }}>
          <div style={{ backgroundColor: T.cream, borderRadius: "6px", padding: "2.5rem", maxWidth: "420px", width: "100%", textAlign: "center", position: "relative" }}>
            <button onClick={() => setShowModal(false)} style={{ position: "absolute", top: "1rem", right: "1rem", background: "none", border: "none", cursor: "pointer", color: T.muted, fontSize: "1.4rem" }} aria-label="Close">✕</button>
            <div style={{ width: "3rem", height: "3rem", borderRadius: "50%", backgroundColor: T.creamMid, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.25rem" }}>
              <Lock className="w-5 h-5" style={{ color: T.accent }} />
            </div>
            <h3 style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.5rem", marginBottom: "0.75rem" }}>
              You've used your {GUEST_LIMIT} free questions
            </h3>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.9rem", lineHeight: 1.7, marginBottom: "2rem" }}>
              Sign up free to continue your inquiry into the teachings of Sri Ramana Maharshi — with unlimited access to the wisdom guide.
            </p>
            <div className="flex flex-col gap-3">
              <Link to="/register" style={{ ...btn, display: "block", textAlign: "center", fontSize: "0.95rem", padding: "0.85rem" }}>
                Create free account
              </Link>
              <Link to="/register?plan=seeker" style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.85rem", textDecoration: "underline" }}>
                Or subscribe — Seeker $5.99 · Devotee $12.99 / month
              </Link>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-3xl mx-auto relative z-10">
        <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem", textAlign: "center" }}>
          Try free — no sign-up needed
        </p>
        <h2 style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "clamp(1.7rem, 3.5vw, 2.5rem)", lineHeight: 1.25, marginBottom: "0.75rem", textAlign: "center" }}>
          Ask Bhagavan anything
        </h2>
        <p style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.9rem", lineHeight: 1.7, marginBottom: "2rem", textAlign: "center" }}>
          Answers drawn exclusively from the authenticated Ramana Maharshi library — not the internet, not general AI.
          {remaining > 0
            ? <span style={{ color: T.accent, fontWeight: 600 }}> {remaining} free question{remaining !== 1 ? "s" : ""} remaining.</span>
            : <span style={{ color: "#e8a070" }}> You've used all your free questions.</span>
          }
        </p>

        {/* Chat window */}
        <div style={{ backgroundColor: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", overflow: "hidden" }}>
          {/* Messages */}
          <div style={{ height: "360px", overflowY: "auto", padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
            {messages.length === 0 && (
              <div style={{ margin: "auto", textAlign: "center" }}>
                <p style={{ fontFamily: T.serif, color: "#C4A892", fontSize: "1.05rem", fontStyle: "italic", marginBottom: "1rem" }}>
                  "Who am I?" — that is the enquiry.
                </p>
                <p style={{ fontFamily: T.sans, color: "#7A6054", fontSize: "0.82rem" }}>
                  Ask about self-inquiry, the nature of the mind, surrender, silence…
                </p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{
                  maxWidth: "80%",
                  padding: "0.75rem 1rem",
                  borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                  backgroundColor: m.role === "user" ? T.accent : "rgba(255,255,255,0.1)",
                  color: m.role === "user" ? "#fff" : "#E8DCD4",
                  fontFamily: T.sans,
                  fontSize: "0.88rem",
                  lineHeight: 1.65,
                }}>
                  {m.content || (loading && i === messages.length - 1 ? (
                    <span style={{ opacity: 0.7, display: "inline-flex", alignItems: "center", gap: "3px" }}>
                      <span style={{ animation: "pulse 1.2s ease-in-out infinite" }}>●</span>
                      <span style={{ animation: "pulse 1.2s ease-in-out 0.4s infinite" }}>●</span>
                      <span style={{ animation: "pulse 1.2s ease-in-out 0.8s infinite" }}>●</span>
                      <style>{`@keyframes pulse { 0%,100%{opacity:0.3} 50%{opacity:1} }`}</style>
                    </span>
                  ) : "…")}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.875rem 1rem", display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
            {remaining > 0 ? (
              <>
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder="Ask about self-inquiry, silence, the mind…"
                  disabled={loading}
                  rows={1}
                  style={{
                    flex: 1,
                    background: "transparent",
                    border: "1px solid rgba(255,255,255,0.15)",
                    borderRadius: "5px",
                    padding: "0.6rem 0.875rem",
                    color: "#F5F0EC",
                    fontFamily: T.sans,
                    fontSize: "0.88rem",
                    resize: "none",
                    outline: "none",
                    lineHeight: 1.5,
                  }}
                />
                <button
                  onClick={handleSend}
                  disabled={loading || !input.trim()}
                  style={{ ...btn, padding: "0.6rem 1rem", display: "flex", alignItems: "center", gap: "0.35rem", opacity: (loading || !input.trim()) ? 0.5 : 1, flexShrink: 0 }}
                >
                  <Send className="w-4 h-4" />
                </button>
              </>
            ) : (
              <div style={{ flex: 1, textAlign: "center" }}>
                <button onClick={() => setShowModal(true)} style={{ ...btn, padding: "0.65rem 1.75rem", display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
                  <Lock className="w-4 h-4" /> Sign up to continue
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── Content generation panel — appears after first Q&A ───────────── */}
        {hasQA && (
          <div style={{ marginTop: "2rem" }}>
            {/* Divider with label */}
            <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.25rem" }}>
              <div style={{ flex: 1, height: "1px", backgroundColor: "rgba(255,255,255,0.1)" }} />
              <p style={{ fontFamily: T.sans, color: "rgba(196,168,146,0.7)", fontSize: "0.72rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600, whiteSpace: "nowrap" }}>
                Now experience the full practice
              </p>
              <div style={{ flex: 1, height: "1px", backgroundColor: "rgba(255,255,255,0.1)" }} />
            </div>

            {/* ── Three format buttons — shown when idle and quota remains ── */}
            {!isGenerating && !genDone && contentCount < GUEST_CONTENT_LIMIT && (
              <>
                <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                  {([
                    { mode: "image" as const, icon: <ImageIcon className="w-4 h-4" />, label: "Card",  sub: "Contemplation image"     },
                    { mode: "audio" as const, icon: <Volume2   className="w-4 h-4" />, label: "Audio", sub: "3-min guided meditation"  },
                    { mode: "video" as const, icon: <Video     className="w-4 h-4" />, label: "Video", sub: "3-min meditation video"   },
                  ]).map(({ mode, icon, label, sub }) => (
                    <button
                      key={mode}
                      onClick={() => handleGenerate(mode)}
                      style={{
                        display: "flex", flexDirection: "column", alignItems: "center", gap: "0.3rem",
                        padding: "0.85rem 1.5rem",
                        backgroundColor: "rgba(255,255,255,0.07)",
                        border: "1px solid rgba(255,255,255,0.14)",
                        borderRadius: "6px", cursor: "pointer",
                        minWidth: "120px", transition: "background-color 0.2s",
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "rgba(255,255,255,0.13)"; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "rgba(255,255,255,0.07)"; }}
                    >
                      <span style={{ color: T.accent }}>{icon}</span>
                      <span style={{ fontFamily: T.sans, color: "#F5F0EC", fontSize: "0.88rem", fontWeight: 600 }}>{label}</span>
                      <span style={{ fontFamily: T.sans, color: "#9A8070", fontSize: "0.72rem" }}>{sub}</span>
                    </button>
                  ))}
                </div>
                <p style={{ fontFamily: T.sans, color: "rgba(154,128,112,0.7)", fontSize: "0.75rem", textAlign: "center" }}>
                  {GUEST_CONTENT_LIMIT - contentCount} free generation{GUEST_CONTENT_LIMIT - contentCount !== 1 ? "s" : ""} remaining today
                </p>
              </>
            )}

            {/* ── Quota exhausted — clear sign-up prompt, no disabled buttons ── */}
            {!isGenerating && !genDone && contentCount >= GUEST_CONTENT_LIMIT && (
              <div style={{ backgroundColor: "rgba(184,90,45,0.1)", border: "1px solid rgba(184,90,45,0.25)", borderRadius: "8px", padding: "1.25rem 1.5rem", textAlign: "center" }}>
                <p style={{ fontFamily: T.sans, color: "#F5F0EC", fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.4rem" }}>
                  You've used your 3 free generations
                </p>
                <p style={{ fontFamily: T.sans, color: "#9A8070", fontSize: "0.82rem", lineHeight: 1.6, marginBottom: "1rem" }}>
                  Sign up free to get unlimited cards, audio meditations and videos for every question you ask.
                </p>
                <Link to="/register" style={{ ...btn, display: "inline-block", fontSize: "0.85rem", padding: "0.6rem 1.5rem" }}>
                  Create free account →
                </Link>
              </div>
            )}

            {/* ── Loading spinner ── */}
            {isGenerating && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "2rem 0" }}>
                <div style={{ position: "relative", width: "4rem", height: "4rem", marginBottom: "1rem" }}>
                  <div style={{ position: "absolute", inset: 0, border: "4px solid rgba(184,90,45,0.25)", borderTopColor: T.accent, borderRadius: "50%", animation: "spin 1s linear infinite" }} />
                  <div style={{ position: "absolute", inset: "8px", background: `radial-gradient(circle, ${T.accent}, #8b3a1a)`, borderRadius: "50%", animation: "pulse2 1.5s ease-in-out infinite" }} />
                  <style>{`@keyframes spin{to{transform:rotate(360deg)}} @keyframes pulse2{0%,100%{opacity:.6}50%{opacity:1}}`}</style>
                </div>
                <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.95rem", fontWeight: 600 }}>
                  {genMode === "image" ? "Creating your contemplation card…" : genMode === "audio" ? "Generating your guided meditation audio…" : "Generating your meditation video…"}
                </p>
                <p style={{ fontFamily: T.sans, color: "#9A8070", fontSize: "0.8rem", marginTop: "0.35rem" }}>
                  {genMode === "video" ? "Video takes ~2 minutes — please keep this tab open" : "This may take a moment — please keep this tab open"}
                </p>
              </div>
            )}

            {/* ── Error with retry ── */}
            {genStatus === "failed" && genError && (
              <div style={{ backgroundColor: "rgba(200,60,60,0.12)", border: "1px solid rgba(200,60,60,0.25)", borderRadius: "6px", padding: "1rem", textAlign: "center", marginBottom: "0.75rem" }}>
                <p style={{ fontFamily: T.sans, color: "#e88888", fontSize: "0.88rem" }}>{genError}</p>
                <button
                  onClick={() => { setGenStatus("idle"); setGenMode(null); setGenUrl(null); setGenError(null); }}
                  style={{ ...btn, marginTop: "0.75rem", fontSize: "0.8rem", padding: "0.45rem 1rem" }}
                >
                  Try again
                </button>
              </div>
            )}

            {/* ── Result: image card ── */}
            {genDone && genUrl && genType === "image" && (
              <div style={{ textAlign: "center" }}>
                <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.72rem", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem" }}>
                  Your contemplation card
                </p>
                <div style={{ position: "relative", display: "inline-block", maxWidth: "380px", width: "100%" }}>
                  <img src={genUrl} alt="Contemplation card" style={{ width: "100%", borderRadius: "8px", boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }} />
                  <a
                    href={genUrl} download="contemplation-card.png" target="_blank" rel="noopener noreferrer"
                    style={{ position: "absolute", top: "0.75rem", right: "0.75rem", backgroundColor: "rgba(0,0,0,0.55)", color: "#fff", borderRadius: "50%", width: "2rem", height: "2rem", display: "flex", alignItems: "center", justifyContent: "center", textDecoration: "none" }}
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                </div>
                <p style={{ fontFamily: T.sans, color: "#9A8070", fontSize: "0.78rem", marginTop: "0.75rem" }}>
                  Subscribers get a new card for every question they ask.
                </p>
                {/* Format switch buttons — only when quota remains */}
                {contentCount < GUEST_CONTENT_LIMIT && (
                  <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap" }}>
                    <p style={{ width: "100%", fontFamily: T.sans, color: "#9A8070", fontSize: "0.75rem", marginBottom: "0.25rem" }}>Also try from your question:</p>
                    <button onClick={() => handleGenerate("audio")} style={{ ...btn, fontSize: "0.8rem", padding: "0.45rem 1.1rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <Volume2 className="w-3.5 h-3.5" /> Generate Audio
                    </button>
                    <button onClick={() => handleGenerate("video")} style={{ ...btn, fontSize: "0.8rem", padding: "0.45rem 1.1rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <Video className="w-3.5 h-3.5" /> Generate Video
                    </button>
                  </div>
                )}
                {/* Always-visible navigation row */}
                <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap", alignItems: "center" }}>
                  <button onClick={resetResult} style={{ fontFamily: T.sans, color: "#9A8070", background: "none", border: "1px solid rgba(154,128,112,0.35)", borderRadius: "6px", padding: "0.4rem 1rem", fontSize: "0.8rem", cursor: "pointer" }}>
                    ← Back to chat
                  </button>
                  <Link to="/register" style={{ ...btn, display: "inline-block", fontSize: "0.8rem", padding: "0.4rem 1.1rem" }}>Sign up for unlimited →</Link>
                </div>
              </div>
            )}

            {/* ── Result: audio ── */}
            {genDone && genUrl && genType === "audio" && (
              <div>
                <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.72rem", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem", textAlign: "center" }}>
                  Your 3-min guided meditation
                </p>
                <div style={{ backgroundColor: "rgba(255,255,255,0.06)", borderRadius: "8px", padding: "1.25rem 1.5rem" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Music className="w-4 h-4" style={{ color: T.accent }} />
                      <span style={{ fontFamily: T.sans, color: "#F5F0EC", fontSize: "0.88rem", fontWeight: 500 }}>Guided Meditation Audio</span>
                    </div>
                    <a href={genUrl} download="meditation-audio.mp3" target="_blank" rel="noopener noreferrer" title="Download" style={{ color: "#9A8070" }}>
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                  <audio key={genUrl} src={genUrl} controls preload="auto" style={{ width: "100%" }}>
                    Your browser does not support audio playback.
                  </audio>
                </div>
                <p style={{ fontFamily: T.sans, color: "#9A8070", fontSize: "0.78rem", marginTop: "0.75rem", textAlign: "center" }}>
                  Subscribers get personalised meditations for every question they ask.
                </p>
                {/* Format switch buttons — only when quota remains */}
                {contentCount < GUEST_CONTENT_LIMIT && (
                  <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap" }}>
                    <p style={{ width: "100%", fontFamily: T.sans, color: "#9A8070", fontSize: "0.75rem", marginBottom: "0.25rem", textAlign: "center" }}>Also try from your question:</p>
                    <button onClick={() => handleGenerate("image")} style={{ ...btn, fontSize: "0.8rem", padding: "0.45rem 1.1rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <ImageIcon className="w-3.5 h-3.5" /> Generate Card
                    </button>
                    <button onClick={() => handleGenerate("video")} style={{ ...btn, fontSize: "0.8rem", padding: "0.45rem 1.1rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <Video className="w-3.5 h-3.5" /> Generate Video
                    </button>
                  </div>
                )}
                {/* Always-visible navigation row */}
                <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap", alignItems: "center" }}>
                  <button onClick={resetResult} style={{ fontFamily: T.sans, color: "#9A8070", background: "none", border: "1px solid rgba(154,128,112,0.35)", borderRadius: "6px", padding: "0.4rem 1rem", fontSize: "0.8rem", cursor: "pointer" }}>
                    ← Back to chat
                  </button>
                  <Link to="/register" style={{ ...btn, display: "inline-block", fontSize: "0.8rem", padding: "0.4rem 1.1rem" }}>Sign up for unlimited →</Link>
                </div>
              </div>
            )}

            {/* ── Result: video ── */}
            {genDone && genUrl && genType === "video" && (
              <div>
                <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.72rem", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem", textAlign: "center" }}>
                  Your 3-min meditation video
                </p>
                <div style={{ borderRadius: "8px", overflow: "hidden", boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
                  <video key={genUrl} src={genUrl} controls preload="metadata" style={{ width: "100%", display: "block" }}>
                    Your browser does not support video playback.
                  </video>
                </div>
                <p style={{ fontFamily: T.sans, color: "#9A8070", fontSize: "0.78rem", marginTop: "0.75rem", textAlign: "center" }}>
                  Subscribers get personalised meditation videos for every question they ask.
                </p>
                {/* Format switch buttons — only when quota remains */}
                {contentCount < GUEST_CONTENT_LIMIT && (
                  <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap" }}>
                    <p style={{ width: "100%", fontFamily: T.sans, color: "#9A8070", fontSize: "0.75rem", marginBottom: "0.25rem", textAlign: "center" }}>Also try from your question:</p>
                    <button onClick={() => handleGenerate("image")} style={{ ...btn, fontSize: "0.8rem", padding: "0.45rem 1.1rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <ImageIcon className="w-3.5 h-3.5" /> Generate Card
                    </button>
                    <button onClick={() => handleGenerate("audio")} style={{ ...btn, fontSize: "0.8rem", padding: "0.45rem 1.1rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <Volume2 className="w-3.5 h-3.5" /> Generate Audio
                    </button>
                  </div>
                )}
                {/* Always-visible navigation row */}
                <div style={{ marginTop: "1rem", display: "flex", gap: "0.6rem", justifyContent: "center", flexWrap: "wrap", alignItems: "center" }}>
                  <button onClick={resetResult} style={{ fontFamily: T.sans, color: "#9A8070", background: "none", border: "1px solid rgba(154,128,112,0.35)", borderRadius: "6px", padding: "0.4rem 1rem", fontSize: "0.8rem", cursor: "pointer" }}>
                    ← Back to chat
                  </button>
                  <Link to="/register" style={{ ...btn, display: "inline-block", fontSize: "0.8rem", padding: "0.4rem 1.1rem" }}>Sign up for unlimited →</Link>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────
const FEATURES = [
  {
    icon: <MessageCircle className="w-5 h-5" />,
    title: "AI Wisdom Guide",
    description: "Ask any question and receive answers drawn exclusively from the authenticated Ramana Maharshi library — never from the internet, never from general AI training data. Pure signal, no noise.",
  },
  {
    icon: <Sparkles className="w-5 h-5" />,
    title: "Contextual Contemplation Card",
    description: "Every answer generates an associated contemplation card — a beautiful, shareable reflection drawn from the specific passage that answered your question.",
  },
  {
    icon: <Music className="w-5 h-5" />,
    title: "Guided Meditation — Audio & Video",
    description: "Based on what you ask, the portal generates a personalised guided meditation — audio or video — rooted in the teaching most relevant to your inquiry.",
  },
  {
    icon: <Layers className="w-5 h-5" />,
    title: "Pre-built Queries",
    description: "Not sure where to start? Choose from a curated set of inquiry prompts drawn from the core teachings — a gentle doorway for seekers at every level.",
  },
];

function FeaturesSection() {
  return (
    <section id="features" style={{ backgroundColor: "#EDE5DC", position: "relative", overflow: "hidden" }} className="py-20 px-6">
      <div style={{ position: "absolute", left: "-80px", bottom: "-80px" }}>
        <Mandala size={460} opacity={0.06} color={T.brown} />
      </div>
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="flex flex-col md:flex-row gap-14 items-start">
          <div className="md:w-1/3">
            <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem" }}>What's Inside</p>
            <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "clamp(2rem, 4vw, 3rem)", lineHeight: 1.2, marginBottom: "1rem" }}>
              Read, Reflect,
              <br />Realize
            </h2>
            <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.9rem", lineHeight: 1.7, marginBottom: "2rem" }}>
              Every feature is designed to support genuine inquiry — not to entertain, but to help you go deeper into the teachings.
            </p>
            <Link to="/register" style={btn}>Explore the portal</Link>
          </div>
          <div className="md:w-2/3 grid grid-cols-1 sm:grid-cols-2 gap-5">
            {FEATURES.map(({ icon, title, description }) => (
              <div key={title} style={{ backgroundColor: "#FBF7F3", border: `1px solid ${T.border}`, borderRadius: "4px", padding: "1.75rem" }}>
                <div style={{ width: "2.4rem", height: "2.4rem", borderRadius: "5px", backgroundColor: T.creamMid, color: T.accent, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "1rem" }}>
                  {icon}
                </div>
                <h3 style={{ fontFamily: T.serif, color: T.brown, fontSize: "1.1rem", marginBottom: "0.5rem" }}>{title}</h3>
                <p style={{ fontFamily: T.sans, color: "#6B4F42", fontSize: "0.87rem", lineHeight: 1.65 }}>{description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── 8. Pricing — dual USD + INR ──────────────────────────────────────────────
// Seeker = BASIC plan: 150 conversations/month, unlimited cards, 60 min audio+video/month
const PLAN_SEEKER: { text: string; highlight?: boolean }[] = [
  { text: "150 conversations per month" },
  { text: "Unlimited daily contemplation" },
  { text: "Unlimited Contextual Contemplation Cards" },
  { text: "Up to 60 min of personalised guided meditation per month (audio + video)", highlight: true },
  { text: "Pre-built inquiry queries for every level" },
  { text: "Full Ramana library access" },
  { text: "Email support" },
];

// Devotee = PRO plan: unlimited conversations, unlimited cards, 200 min audio+video/month
const PLAN_DEVOTEE: { text: string; highlight?: boolean }[] = [
  { text: "Everything in Seeker, plus:" },
  { text: "Unlimited conversations — no monthly cap", highlight: true },
  { text: "Up to 200 min of personalised guided meditation per month (audio + video)", highlight: true },
];

function PricingSection() {
  return (
    <section id="pricing" style={{ backgroundColor: T.cream }} className="py-20 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-14">
          <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem" }}>Transparent Pricing</p>
          <h2 style={{ fontFamily: T.serif, color: T.brown, fontSize: "clamp(2rem, 4vw, 3rem)", lineHeight: 1.2, marginBottom: "1rem" }}>
            Go deeper when you're ready.
          </h2>
          <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.95rem", lineHeight: 1.7, maxWidth: "480px" }}>
            The teachings themselves are boundless. We simply ask for support to keep the library alive and growing.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl">

          {/* Seeker plan */}
          <div style={{ backgroundColor: T.umber, borderRadius: "4px", padding: "2.25rem", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", top: 0, right: 0, width: "160px", height: "160px", background: "radial-gradient(circle, rgba(184,90,45,0.28) 0%, transparent 70%)", transform: "translate(30%, -30%)", pointerEvents: "none" }} />
            <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.5rem" }}>Seeker</p>
            <div className="flex items-end gap-1.5 mb-1">
              <span style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "2.75rem", lineHeight: 1 }}>$5.99</span>
              <span style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.88rem", marginBottom: "0.35rem" }}>/&nbsp;month</span>
            </div>
            <p style={{ fontFamily: T.sans, color: "#8A6D5E", fontSize: "0.8rem", marginBottom: "1.5rem" }}>
              ₹499 / month
            </p>
            <ul className="space-y-3 mb-8">
              {PLAN_SEEKER.map(item => (
                <li key={item.text} className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: T.accent }} />
                  <span style={{ fontFamily: T.sans, color: "#E8DCD4", fontSize: "0.88rem" }}>{item.text}</span>
                </li>
              ))}
            </ul>
            <Link to="/register?plan=seeker" style={{ ...btn, display: "block", textAlign: "center", borderRadius: "4px" }}>
              Begin as Seeker
            </Link>
          </div>

          {/* Devotee plan */}
          <div style={{ backgroundColor: T.umber, borderRadius: "4px", padding: "2.25rem", position: "relative", overflow: "hidden", border: `2px solid ${T.accent}` }}>
            {/* "Most popular" badge */}
            <div style={{ position: "absolute", top: "1.1rem", right: "1.1rem", backgroundColor: T.accent, color: "#fff", fontFamily: T.sans, fontSize: "0.68rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", padding: "0.25rem 0.65rem", borderRadius: "3px" }}>
              Most Popular
            </div>
            <div style={{ position: "absolute", top: 0, right: 0, width: "200px", height: "200px", background: "radial-gradient(circle, rgba(184,90,45,0.38) 0%, transparent 70%)", transform: "translate(30%, -30%)", pointerEvents: "none" }} />
            <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.74rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.5rem" }}>Devotee</p>
            <div className="flex items-end gap-1.5 mb-1">
              <span style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "2.75rem", lineHeight: 1 }}>$12.99</span>
              <span style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.88rem", marginBottom: "0.35rem" }}>/&nbsp;month</span>
            </div>
            <p style={{ fontFamily: T.sans, color: "#8A6D5E", fontSize: "0.8rem", marginBottom: "1.5rem" }}>
              ₹999 / month
            </p>
            <ul className="space-y-3 mb-8">
              {PLAN_DEVOTEE.map(item => (
                <li key={item.text} className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: item.highlight ? "#F5C58A" : T.accent }} />
                  <span style={{ fontFamily: T.sans, color: item.highlight ? "#F5C58A" : "#E8DCD4", fontSize: "0.88rem", fontWeight: item.highlight ? 500 : 400 }}>{item.text}</span>
                </li>
              ))}
            </ul>
            <Link to="/register?plan=devotee" style={{ ...btn, display: "block", textAlign: "center", borderRadius: "4px", backgroundColor: "#C96A3A" }}>
              Begin as Devotee
            </Link>
          </div>

        </div>

        <p style={{ fontFamily: T.sans, color: T.muted, fontSize: "0.78rem", marginTop: "1.5rem" }}>
          Try 5 free questions — no account needed · Cancel anytime · Indian pricing in ₹ · International pricing in $
        </p>
      </div>
    </section>
  );
}

// ─── 9. Final CTA ─────────────────────────────────────────────────────────────
function FinalCTA({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <section style={{ backgroundColor: T.umber, position: "relative", overflow: "hidden" }} className="py-24 px-6 text-center">
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", background: "radial-gradient(ellipse 70% 80% at 50% 50%, rgba(184,90,45,0.16) 0%, transparent 70%)" }} />
      <div aria-hidden="true" style={{ position: "absolute", bottom: "-2rem", right: "-2rem", fontFamily: T.serif, fontSize: "11rem", color: "#F5F0EC", opacity: 0.04, lineHeight: 1, userSelect: "none", pointerEvents: "none" }}>OM</div>
      <div style={{ position: "relative", zIndex: 10, maxWidth: "640px", margin: "0 auto" }}>
        <h2 style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "clamp(1.8rem, 4vw, 2.6rem)", lineHeight: 1.25, marginBottom: "1.25rem" }}>
          The inquiry begins with
          <br />a single question.
        </h2>
        <p style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "1rem", lineHeight: 1.7, marginBottom: "2.5rem" }}>
          Whether you are new to Ramana's teachings or have studied them for years, the portal meets you exactly where you are.
        </p>
        {isAuthenticated ? (
          <Link to="/home" style={{ ...btn, fontSize: "0.95rem", padding: "0.85rem 2.25rem", display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
            Return to your portal <ArrowRight className="w-4 h-4" />
          </Link>
        ) : (
          <a href="#try" style={{ ...btn, fontSize: "0.95rem", padding: "0.85rem 2.25rem", display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
            Begin — it's free <ArrowRight className="w-4 h-4" />
          </a>
        )}
      </div>
    </section>
  );
}

// ─── 10. Footer ───────────────────────────────────────────────────────────────
function Footer() {
  const [email, setEmail] = useState("");
  const [subscribeState, setSubscribeState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubscribe = async () => {
    const trimmed = email.trim();
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setErrorMsg("Please enter a valid email address.");
      setSubscribeState("error");
      return;
    }
    setSubscribeState("loading");
    setErrorMsg("");
    try {
      const res = await fetch("/api/newsletter/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setSubscribeState("success");
      } else {
        setErrorMsg(data.detail || "Something went wrong. Please try again.");
        setSubscribeState("error");
      }
    } catch {
      setErrorMsg("Network error. Please try again.");
      setSubscribeState("error");
    }
  };

  return (
    <footer style={{ backgroundColor: T.umber, borderTop: "1px solid #3D2518", position: "relative", overflow: "hidden" }} className="px-6 pt-14 pb-8">
      <div style={{ position: "absolute", bottom: "-120px", left: "50%", transform: "translateX(-50%)" }}>
        <Mandala size={700} opacity={0.045} color="#F5F0EC" />
      </div>
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
          {/* Brand + subscribe */}
          <div className="col-span-2">
            <p style={{ fontFamily: T.serif, color: "#F5F0EC", fontSize: "1.15rem", marginBottom: "0.75rem" }}>Arunachala Samudra</p>
            <p style={{ fontFamily: T.sans, color: "#8A6D5E", fontSize: "0.83rem", lineHeight: 1.65, maxWidth: "240px", marginBottom: "1.5rem" }}>
              A living library of Sri Ramana Maharshi's authenticated teachings, made accessible through AI.
            </p>
            <p style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "0.75rem" }}>
              Subscribe for wisdom articles
            </p>
            {subscribeState === "success" ? (
              <p style={{ fontFamily: T.sans, color: T.accent, fontSize: "0.85rem" }}>✓ Thank you — we'll be in touch.</p>
            ) : (
              <>
                <div className="flex gap-2">
                  <input
                    type="email"
                    placeholder="Your email"
                    value={email}
                    onChange={e => { setEmail(e.target.value); if (subscribeState === "error") setSubscribeState("idle"); }}
                    onKeyDown={e => { if (e.key === "Enter") handleSubscribe(); }}
                    disabled={subscribeState === "loading"}
                    style={{ fontFamily: T.sans, fontSize: "0.83rem", backgroundColor: "rgba(255,255,255,0.07)", border: `1px solid ${subscribeState === "error" ? "#e07a5f" : "rgba(255,255,255,0.12)"}`, color: "#F5F0EC", borderRadius: "4px", padding: "0.5rem 0.85rem", outline: "none", flex: 1, minWidth: 0 }}
                  />
                  <button
                    onClick={handleSubscribe}
                    disabled={subscribeState === "loading"}
                    style={{ ...btn, padding: "0.5rem 1rem", borderRadius: "4px", fontSize: "0.8rem", flexShrink: 0, opacity: subscribeState === "loading" ? 0.65 : 1 }}
                  >
                    {subscribeState === "loading" ? "…" : "Subscribe"}
                  </button>
                </div>
                {subscribeState === "error" && (
                  <p style={{ fontFamily: T.sans, color: "#e07a5f", fontSize: "0.78rem", marginTop: "0.4rem" }}>{errorMsg}</p>
                )}
              </>
            )}
          </div>

          {/* Portal links */}
          <div>
            <p style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "1rem" }}>Portal</p>
            <ul className="space-y-2">
              {[
                { label: "Sign In",   to: "/signin"   },
                { label: "Register",  to: "/register" },
                { label: "Privacy",   to: "/privacy"  },
                { label: "Terms",     to: "/terms"    },
              ].map(({ label, to }) => (
                <li key={label}><Link to={to} style={{ fontFamily: T.sans, color: "#8A6D5E", fontSize: "0.85rem" }} className="hover:text-[#C4A892] transition-colors">{label}</Link></li>
              ))}
            </ul>
          </div>

          {/* Teachings */}
          <div>
            <p style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "1rem" }}>Teachings</p>
            <ul className="space-y-2">
              {TEACHINGS.map(t => (
                <li key={t.id}><a href="#teachings" style={{ fontFamily: T.sans, color: "#8A6D5E", fontSize: "0.85rem" }} className="hover:text-[#C4A892] transition-colors">{t.title}</a></li>
              ))}
            </ul>
          </div>

          {/* External resources */}
          <div>
            <p style={{ fontFamily: T.sans, color: "#C4A892", fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 600, marginBottom: "1rem" }}>Resources</p>
            <ul className="space-y-2">
              {[
                { label: "Arunachala Samudra .in",   href: "https://www.arunachalasamudra.in"                          },
                { label: "Digital Experience Centre", href: "https://www.arunachalasamudra.in/digital-experience-centre" },
                { label: "Sacred Teachings",          href: "https://www.arunachalasamudra.in/sacred-teachings"         },
                { label: "Ramanasramam",              href: "https://www.gururamana.org"                                        },
                { label: "Mountain Path Journal",     href: "https://www.gururamana.org/Resources/mountain-path"            },
                { label: "David Godman",              href: "https://www.davidgodman.org"                                    },
                { label: "Paul Brunton",              href: "https://www.paulbrunton.org"                                    },
                { label: "Arunachala Ashrama NY",     href: "https://www.arunachala.org"        },
              ].map(({ label, href }) => (
                <li key={label}><a href={href} target="_blank" rel="noopener noreferrer" style={{ fontFamily: T.sans, color: "#8A6D5E", fontSize: "0.85rem" }} className="hover:text-[#C4A892] transition-colors">{label}</a></li>
              ))}
            </ul>
          </div>
        </div>

        <div style={{ borderTop: "1px solid #3D2518", paddingTop: "1.5rem" }} className="flex flex-col sm:flex-row justify-between items-center gap-3">
          <p style={{ fontFamily: T.sans, color: "#5C3D30", fontSize: "0.78rem" }}>© 2026 Arunachala Samudra. All rights reserved.</p>
          <a href="mailto:info@arunachalasamudra.co.in" style={{ fontFamily: T.sans, color: "#5C3D30", fontSize: "0.78rem" }} className="hover:text-[#8A6D5E] transition-colors">
            info@arunachalasamudra.co.in
          </a>
        </div>
      </div>
    </footer>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────
const INTRO_SESSION_KEY = "as_intro_seen_v2"; // bumped → forces re-show after timing fix (3s→3.8s)

export default function Landing() {
  const { isAuthenticated } = useAuth();

  // ── Atmospheric intro screen (once per session) ──────────────────────────
  const [showIntro, setShowIntro] = useState(() => {
    try {
      return !sessionStorage.getItem(INTRO_SESSION_KEY);
    } catch {
      return true;
    }
  });

  const handleIntroDone = () => {
    try { sessionStorage.setItem(INTRO_SESSION_KEY, "1"); } catch { /* ignore */ }
    setShowIntro(false);
  };

  // ── "New to Ramana?" onboarding modal (once per browser, localStorage) ───
  const [showOnboarding, setShowOnboarding] = useState(false);

  // Auto-show: fires 1.5 s after the intro screen finishes (or immediately
  // if the intro was already seen), but only for unauthenticated visitors
  // who haven't seen the onboarding before.
  useEffect(() => {
    if (isAuthenticated) return;
    try { if (localStorage.getItem(SEEN_KEY)) return; } catch { return; }

    // If IntroScreen is still showing, delay until it finishes + 1.5s
    const delay = showIntro ? 3800 + 1500 : 1500;
    const t = setTimeout(() => setShowOnboarding(true), delay);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // run once on mount

  const handleOnboardingClose = () => setShowOnboarding(false);
  const openOnboarding = () => setShowOnboarding(true);

  return (
    <div style={{ backgroundColor: T.cream, scrollBehavior: "smooth" }} className="min-h-screen overflow-x-hidden">
      {showIntro && <IntroScreen onDone={handleIntroDone} />}
      {showOnboarding && <RamanaOnboardingModal onClose={handleOnboardingClose} />}
      <PublicHeader isAuthenticated={isAuthenticated} onNewToRamana={openOnboarding} />
      <main>
        <HeroSection isAuthenticated={isAuthenticated} onNewToRamana={openOnboarding} />
        <SelfEnquiryBanner isAuthenticated={isAuthenticated} />
        <DailyContemplationSection />
        <GuestChatSection />
        <SacredLibrarySection />
        <FeaturesSection />
        <PricingSection />
        <FinalCTA isAuthenticated={isAuthenticated} />
      </main>
      <Footer />
    </div>
  );
}
