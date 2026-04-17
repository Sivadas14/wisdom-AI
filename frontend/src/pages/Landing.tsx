/**
 * Landing.tsx — Public landing page for Arunachala Samudra
 *
 * Visible to everyone, no login required.
 * Authenticated users are offered a shortcut back to their portal.
 *
 * Sections:
 *   1. PublicHeader  — logo + nav
 *   2. Hero          — atmospheric headline + CTAs
 *   3. DailyContemplation — free, live from /api/contemplation/today
 *   4. SacredLibrary — 5 book teasers (teachings.ts)
 *   5. FreePlan      — what's free + what's inside paid
 *   6. Features      — portal benefits
 *   7. FinalCTA      — sign-up push
 *   8. Footer
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { TEACHINGS } from "@/data/teachings";
import {
  BookOpen, Sparkles, MessageCircle, Music, ChevronDown,
  ChevronUp, ArrowRight, CheckCircle2, Menu, X
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Contemplation {
  date: string;
  quote: string;
  question: string;
}

// ─── Colour tokens (matching .in Framer site) ─────────────────────────────────
// Background : #F5F0EC  (warm parchment)
// Text       : #472B20  (deep umber)
// Accent     : #D05E2D  (saffron orange)
// Border     : #E8DFD8
// Muted text : #8A6D5E

// ─── PublicHeader ─────────────────────────────────────────────────────────────

function PublicHeader({ isAuthenticated }: { isAuthenticated: boolean }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      style={{
        backgroundColor: scrolled ? "rgba(245,240,236,0.92)" : "#F5F0EC",
        borderBottom: "1px solid #E8DFD8",
        backdropFilter: scrolled ? "blur(12px)" : "none",
        WebkitBackdropFilter: scrolled ? "blur(12px)" : "none",
        transition: "background-color 0.2s, backdrop-filter 0.2s",
      }}
      className="sticky top-0 z-50"
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
          <span
            style={{ fontFamily: "'DM Serif Text', serif", color: "#472B20", fontSize: "1.25rem" }}
          >
            Arunachala Samudra
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {[
            { label: "Teachings", href: "#teachings" },
            { label: "Features",  href: "#features"  },
            { label: "Pricing",   href: "#pricing"   },
          ].map(({ label, href }) => (
            <a
              key={label}
              href={href}
              style={{ color: "#8A6D5E", fontFamily: "'Figtree', sans-serif", fontSize: "0.9rem" }}
              className="hover:text-[#472B20] transition-colors"
            >
              {label}
            </a>
          ))}
        </nav>

        {/* CTA buttons */}
        <div className="hidden md:flex items-center gap-3">
          {isAuthenticated ? (
            <Link
              to="/chat"
              style={{ backgroundColor: "#D05E2D", color: "#fff", fontFamily: "'Figtree', sans-serif" }}
              className="px-5 py-2 rounded-full text-sm font-medium hover:opacity-90 transition-opacity"
            >
              Go to Portal →
            </Link>
          ) : (
            <>
              <Link
                to="/signin"
                style={{ color: "#472B20", fontFamily: "'Figtree', sans-serif" }}
                className="px-4 py-2 text-sm font-medium hover:opacity-70 transition-opacity"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                style={{ backgroundColor: "#472B20", color: "#F5F0EC", fontFamily: "'Figtree', sans-serif" }}
                className="px-5 py-2 rounded-full text-sm font-medium hover:opacity-90 transition-opacity"
              >
                Start Free
              </Link>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2"
          style={{ color: "#472B20" }}
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div
          style={{ backgroundColor: "#F5F0EC", borderTop: "1px solid #E8DFD8" }}
          className="md:hidden px-6 pb-6 space-y-4"
        >
          {[
            { label: "Teachings", href: "#teachings" },
            { label: "Features",  href: "#features"  },
            { label: "Pricing",   href: "#pricing"   },
          ].map(({ label, href }) => (
            <a
              key={label}
              href={href}
              style={{ color: "#472B20", fontFamily: "'Figtree', sans-serif" }}
              className="block text-base"
              onClick={() => setMenuOpen(false)}
            >
              {label}
            </a>
          ))}
          <div className="flex flex-col gap-3 pt-2">
            {isAuthenticated ? (
              <Link
                to="/chat"
                style={{ backgroundColor: "#D05E2D", color: "#fff" }}
                className="px-5 py-3 rounded-full text-sm font-medium text-center"
                onClick={() => setMenuOpen(false)}
              >
                Go to Portal →
              </Link>
            ) : (
              <>
                <Link
                  to="/signin"
                  style={{ color: "#472B20", border: "1px solid #E8DFD8" }}
                  className="px-5 py-3 rounded-full text-sm font-medium text-center"
                  onClick={() => setMenuOpen(false)}
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  style={{ backgroundColor: "#472B20", color: "#F5F0EC" }}
                  className="px-5 py-3 rounded-full text-sm font-medium text-center"
                  onClick={() => setMenuOpen(false)}
                >
                  Start Free
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function HeroSection({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <section
      style={{ backgroundColor: "#F5F0EC" }}
      className="relative overflow-hidden"
    >
      {/* Soft radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 0%, rgba(208,94,45,0.08) 0%, transparent 70%)",
        }}
      />

      <div className="relative max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        {/* Overline */}
        <p
          style={{
            fontFamily: "'Figtree', sans-serif",
            color: "#D05E2D",
            fontSize: "0.8rem",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
          className="mb-5 font-semibold"
        >
          Arunachala Samudra · Wisdom Portal
        </p>

        {/* Headline */}
        <h1
          style={{
            fontFamily: "'DM Serif Text', serif",
            color: "#472B20",
            fontSize: "clamp(2rem, 6vw, 3.5rem)",
            lineHeight: 1.2,
          }}
          className="mb-6"
        >
          The complete teachings of
          <br />
          Sri Ramana Maharshi,
          <br />
          <em>alive and answering.</em>
        </h1>

        {/* Sub-headline */}
        <p
          style={{
            fontFamily: "'Figtree', sans-serif",
            color: "#8A6D5E",
            fontSize: "1.1rem",
            lineHeight: 1.7,
            maxWidth: "580px",
          }}
          className="mx-auto mb-10"
        >
          Ask any question from the sacred library — Who Am I?, Forty Verses,
          Upadesa Saram and more — and receive answers drawn solely from
          Bhagavan's authenticated words. Not a chatbot. A living library.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          {isAuthenticated ? (
            <Link
              to="/chat"
              style={{ backgroundColor: "#D05E2D", color: "#fff", fontFamily: "'Figtree', sans-serif" }}
              className="px-8 py-4 rounded-full font-semibold text-base hover:opacity-90 transition-opacity inline-flex items-center gap-2 justify-center"
            >
              Continue to your portal <ArrowRight className="w-4 h-4" />
            </Link>
          ) : (
            <>
              <Link
                to="/register"
                style={{ backgroundColor: "#D05E2D", color: "#fff", fontFamily: "'Figtree', sans-serif" }}
                className="px-8 py-4 rounded-full font-semibold text-base hover:opacity-90 transition-opacity inline-flex items-center gap-2 justify-center"
              >
                Begin — it's free <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/signin"
                style={{
                  backgroundColor: "transparent",
                  color: "#472B20",
                  border: "1.5px solid #C4B5A8",
                  fontFamily: "'Figtree', sans-serif",
                }}
                className="px-8 py-4 rounded-full font-semibold text-base hover:bg-[#ECE5DF] transition-colors justify-center inline-flex items-center gap-2"
              >
                Sign in
              </Link>
            </>
          )}
        </div>

        {/* Trust note */}
        <p
          style={{ fontFamily: "'Figtree', sans-serif", color: "#B09A8E", fontSize: "0.8rem" }}
          className="mt-6"
        >
          No credit card required · Free plan available · Answers from the authenticated library only
        </p>
      </div>
    </section>
  );
}

// ─── Daily Contemplation ──────────────────────────────────────────────────────

function DailyContemplationSection() {
  const [data, setData] = useState<Contemplation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/contemplation/today")
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => {
        setData({
          date: new Date().toISOString().slice(0, 10),
          quote: "Silence is the true teaching. Sit quietly, and notice what remains when thought subsides.",
          question: "Who is the one who is aware right now?",
        });
        setLoading(false);
      });
  }, []);

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <section
      style={{ backgroundColor: "#EEE6DF" }}
      className="py-20 px-6"
    >
      <div className="max-w-2xl mx-auto text-center">
        <p
          style={{
            fontFamily: "'Figtree', sans-serif",
            color: "#D05E2D",
            fontSize: "0.78rem",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
          className="mb-3 font-semibold"
        >
          Free · No login required
        </p>

        <h2
          style={{ fontFamily: "'DM Serif Text', serif", color: "#472B20", fontSize: "1.9rem" }}
          className="mb-2"
        >
          Today's Contemplation
        </h2>
        <p
          style={{ fontFamily: "'Figtree', sans-serif", color: "#8A6D5E", fontSize: "0.85rem" }}
          className="mb-10"
        >
          {today}
        </p>

        {loading ? (
          <div className="space-y-3">
            <div className="h-5 bg-[#D9CFC8] rounded-full animate-pulse mx-auto w-3/4" />
            <div className="h-5 bg-[#D9CFC8] rounded-full animate-pulse mx-auto w-1/2" />
          </div>
        ) : data ? (
          <div
            style={{
              backgroundColor: "#F9F5F1",
              border: "1px solid #E0D5CC",
              borderRadius: "1.25rem",
            }}
            className="p-8 md:p-10 text-left relative"
          >
            {/* Decorative quote mark */}
            <span
              style={{
                fontFamily: "'DM Serif Text', serif",
                color: "#D05E2D",
                fontSize: "5rem",
                lineHeight: 0.8,
                opacity: 0.25,
              }}
              className="absolute top-4 left-6 select-none"
            >
              "
            </span>

            <p
              style={{
                fontFamily: "'DM Serif Text', serif",
                color: "#472B20",
                fontSize: "1.35rem",
                lineHeight: 1.65,
              }}
              className="mb-8 relative z-10"
            >
              {data.quote}
            </p>

            <div
              style={{
                borderTop: "1px solid #E0D5CC",
                paddingTop: "1.5rem",
              }}
            >
              <p
                style={{
                  fontFamily: "'Figtree', sans-serif",
                  color: "#D05E2D",
                  fontSize: "0.75rem",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  fontWeight: 600,
                }}
                className="mb-2"
              >
                Inquiry for today
              </p>
              <p
                style={{
                  fontFamily: "'DM Serif Text', serif",
                  color: "#472B20",
                  fontSize: "1.1rem",
                  fontStyle: "italic",
                }}
              >
                {data.question}
              </p>
            </div>
          </div>
        ) : null}

        <p
          style={{ fontFamily: "'Figtree', sans-serif", color: "#B09A8E", fontSize: "0.8rem" }}
          className="mt-6"
        >
          A new contemplation is generated each day from Bhagavan's teachings.
          No account needed — come back any morning.
        </p>
      </div>
    </section>
  );
}

// ─── Sacred Library ────────────────────────────────────────────────────────────

function BookCard({ teaching }: { teaching: typeof TEACHINGS[0] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      style={{
        backgroundColor: "#F9F5F1",
        border: "1px solid #E0D5CC",
        borderRadius: "1rem",
      }}
      className="overflow-hidden transition-shadow hover:shadow-md"
    >
      <div className="p-6">
        {/* Era badge */}
        <span
          style={{
            backgroundColor: "#EEE6DF",
            color: "#8A6D5E",
            fontFamily: "'Figtree', sans-serif",
            fontSize: "0.72rem",
            letterSpacing: "0.08em",
          }}
          className="inline-block px-2.5 py-1 rounded-full mb-4 font-medium uppercase"
        >
          {teaching.era}
        </span>

        {/* Title */}
        <h3
          style={{
            fontFamily: "'DM Serif Text', serif",
            color: "#472B20",
            fontSize: "1.3rem",
          }}
          className="mb-1"
        >
          {teaching.title}
        </h3>
        <p
          style={{
            fontFamily: "'Figtree', sans-serif",
            color: "#D05E2D",
            fontSize: "0.82rem",
            fontStyle: "italic",
          }}
          className="mb-4"
        >
          {teaching.sanskrit} · {teaching.author}
        </p>

        {/* Teaser */}
        <p
          style={{
            fontFamily: "'Figtree', sans-serif",
            color: "#6B4F42",
            fontSize: "0.92rem",
            lineHeight: 1.65,
          }}
          className="mb-4"
        >
          {teaching.teaser}
        </p>

        {/* Expandable introduction */}
        {expanded && (
          <div
            style={{
              borderTop: "1px solid #E0D5CC",
              paddingTop: "1.25rem",
              marginBottom: "1rem",
            }}
          >
            {teaching.introduction.split("\n\n").map((para, i) => (
              <p
                key={i}
                style={{
                  fontFamily: "'Figtree', sans-serif",
                  color: "#5C3D30",
                  fontSize: "0.9rem",
                  lineHeight: 1.7,
                  marginBottom: "0.85rem",
                }}
              >
                {para.trim()}
              </p>
            ))}
          </div>
        )}

        {/* Read more / collapse */}
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            color: "#D05E2D",
            fontFamily: "'Figtree', sans-serif",
            fontSize: "0.85rem",
            fontWeight: 600,
          }}
          className="flex items-center gap-1 hover:opacity-75 transition-opacity"
        >
          {expanded ? (
            <><ChevronUp className="w-4 h-4" /> Show less</>
          ) : (
            <><ChevronDown className="w-4 h-4" /> Read introduction</>
          )}
        </button>
      </div>

      {/* Ask about this CTA */}
      <div
        style={{ backgroundColor: "#EEE6DF", borderTop: "1px solid #E0D5CC" }}
        className="px-6 py-4"
      >
        <Link
          to="/register"
          style={{
            color: "#472B20",
            fontFamily: "'Figtree', sans-serif",
            fontSize: "0.85rem",
            fontWeight: 600,
          }}
          className="flex items-center gap-1 hover:gap-2 transition-all"
        >
          Ask Wisdom AI about this teaching <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}

function SacredLibrarySection() {
  return (
    <section id="teachings" style={{ backgroundColor: "#F5F0EC" }} className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-14">
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#D05E2D",
              fontSize: "0.78rem",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
            className="mb-3 font-semibold"
          >
            The Sacred Library
          </p>
          <h2
            style={{ fontFamily: "'DM Serif Text', serif", color: "#472B20", fontSize: "2rem" }}
            className="mb-4"
          >
            Five texts. A lifetime of depth.
          </h2>
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#8A6D5E",
              fontSize: "1rem",
              maxWidth: "560px",
              lineHeight: 1.7,
            }}
            className="mx-auto"
          >
            The Wisdom Portal draws exclusively from these authenticated works — so every
            answer you receive is grounded in Bhagavan's own words.
          </p>
        </div>

        {/* Book grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {TEACHINGS.map(t => (
            <BookCard key={t.id} teaching={t} />
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Free Plan / Pricing ───────────────────────────────────────────────────────

const PLAN_FREE = [
  "5 conversations per month",
  "Today's Contemplation — free forever",
  "Access to the full Sacred Library introductions",
  "2 Contemplation Cards per month",
];

const PLAN_SEEKER = [
  "30 conversations per month",
  "Unlimited daily contemplation",
  "10 Contemplation Cards per month",
  "Guided meditation audio + video",
  "Priority answers from the full library",
  "Email support",
];

function PricingSection() {
  return (
    <section id="pricing" style={{ backgroundColor: "#EEE6DF" }} className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#D05E2D",
              fontSize: "0.78rem",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
            className="mb-3 font-semibold"
          >
            Transparent Pricing
          </p>
          <h2
            style={{ fontFamily: "'DM Serif Text', serif", color: "#472B20", fontSize: "2rem" }}
            className="mb-4"
          >
            Start free. Go deeper when you're ready.
          </h2>
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#8A6D5E",
              fontSize: "1rem",
              maxWidth: "500px",
              lineHeight: 1.7,
            }}
            className="mx-auto"
          >
            The teachings themselves are boundless. We simply ask for support to
            keep the library alive and growing.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {/* Free */}
          <div
            style={{
              backgroundColor: "#F9F5F1",
              border: "1px solid #E0D5CC",
              borderRadius: "1.25rem",
            }}
            className="p-8"
          >
            <p
              style={{
                fontFamily: "'Figtree', sans-serif",
                color: "#8A6D5E",
                fontSize: "0.8rem",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                fontWeight: 600,
              }}
              className="mb-2"
            >
              Free
            </p>
            <div className="flex items-end gap-1 mb-6">
              <span
                style={{ fontFamily: "'DM Serif Text', serif", color: "#472B20", fontSize: "2.5rem" }}
              >
                ₹0
              </span>
              <span
                style={{ fontFamily: "'Figtree', sans-serif", color: "#8A6D5E", fontSize: "0.9rem" }}
                className="mb-2"
              >
                / month
              </span>
            </div>
            <ul className="space-y-3 mb-8">
              {PLAN_FREE.map(item => (
                <li key={item} className="flex items-start gap-3">
                  <CheckCircle2
                    className="w-4 h-4 flex-shrink-0 mt-0.5"
                    style={{ color: "#D05E2D" }}
                  />
                  <span
                    style={{ fontFamily: "'Figtree', sans-serif", color: "#5C3D30", fontSize: "0.9rem" }}
                  >
                    {item}
                  </span>
                </li>
              ))}
            </ul>
            <Link
              to="/register"
              style={{
                display: "block",
                textAlign: "center",
                border: "1.5px solid #C4B5A8",
                color: "#472B20",
                fontFamily: "'Figtree', sans-serif",
                fontWeight: 600,
                fontSize: "0.9rem",
                borderRadius: "2rem",
                padding: "0.75rem",
              }}
              className="hover:bg-[#ECE5DF] transition-colors"
            >
              Start for free
            </Link>
          </div>

          {/* Seeker */}
          <div
            style={{
              backgroundColor: "#472B20",
              borderRadius: "1.25rem",
            }}
            className="p-8 relative overflow-hidden"
          >
            {/* Glow */}
            <div
              className="absolute top-0 right-0 w-40 h-40 rounded-full pointer-events-none"
              style={{
                background: "radial-gradient(circle, rgba(208,94,45,0.25) 0%, transparent 70%)",
                transform: "translate(30%, -30%)",
              }}
            />
            <p
              style={{
                fontFamily: "'Figtree', sans-serif",
                color: "#D05E2D",
                fontSize: "0.8rem",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                fontWeight: 600,
              }}
              className="mb-2"
            >
              Seeker
            </p>
            <div className="flex items-end gap-1 mb-6">
              <span
                style={{ fontFamily: "'DM Serif Text', serif", color: "#F5F0EC", fontSize: "2.5rem" }}
              >
                ₹499
              </span>
              <span
                style={{ fontFamily: "'Figtree', sans-serif", color: "#C4A892", fontSize: "0.9rem" }}
                className="mb-2"
              >
                / month
              </span>
            </div>
            <ul className="space-y-3 mb-8">
              {PLAN_SEEKER.map(item => (
                <li key={item} className="flex items-start gap-3">
                  <CheckCircle2
                    className="w-4 h-4 flex-shrink-0 mt-0.5"
                    style={{ color: "#D05E2D" }}
                  />
                  <span
                    style={{ fontFamily: "'Figtree', sans-serif", color: "#E8DCD4", fontSize: "0.9rem" }}
                  >
                    {item}
                  </span>
                </li>
              ))}
            </ul>
            <Link
              to="/register"
              style={{
                display: "block",
                textAlign: "center",
                backgroundColor: "#D05E2D",
                color: "#fff",
                fontFamily: "'Figtree', sans-serif",
                fontWeight: 600,
                fontSize: "0.9rem",
                borderRadius: "2rem",
                padding: "0.75rem",
              }}
              className="hover:opacity-90 transition-opacity"
            >
              Begin as Seeker
            </Link>
          </div>
        </div>

        <p
          style={{ fontFamily: "'Figtree', sans-serif", color: "#8A6D5E", fontSize: "0.8rem" }}
          className="text-center mt-8"
        >
          All plans include the free daily contemplation · Cancel anytime · Indian pricing in ₹
        </p>
      </div>
    </section>
  );
}

// ─── Features ─────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: <MessageCircle className="w-6 h-6" />,
    title: "AI Wisdom Guide",
    description:
      "Ask any question and receive answers drawn exclusively from the authenticated Ramana Maharshi library — never from the internet, never from general AI training data.",
  },
  {
    icon: <Sparkles className="w-6 h-6" />,
    title: "Daily Contemplation",
    description:
      "Each morning a new contemplation is generated — a quote and an inquiry question — rooted in Bhagavan's teachings. Free to everyone, every day.",
  },
  {
    icon: <BookOpen className="w-6 h-6" />,
    title: "Sacred Library",
    description:
      "Five foundational texts — Who Am I?, Forty Verses, Upadesa Saram, Devikalottara, and the Ashtavakra Gita — indexed and searchable through natural language.",
  },
  {
    icon: <Music className="w-6 h-6" />,
    title: "Guided Meditations",
    description:
      "Audio and video contemplation guides generated from the teachings, personalised to the questions you ask. A practice companion, not just a reference.",
  },
];

function FeaturesSection() {
  return (
    <section id="features" style={{ backgroundColor: "#F5F0EC" }} className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#D05E2D",
              fontSize: "0.78rem",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
            }}
            className="mb-3 font-semibold"
          >
            What's Inside
          </p>
          <h2
            style={{ fontFamily: "'DM Serif Text', serif", color: "#472B20", fontSize: "2rem" }}
            className="mb-4"
          >
            A practice partner, not a search engine.
          </h2>
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#8A6D5E",
              fontSize: "1rem",
              maxWidth: "520px",
              lineHeight: 1.7,
            }}
            className="mx-auto"
          >
            Every feature is designed to support genuine inquiry — not to entertain,
            but to help you go deeper into the teachings.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
          {FEATURES.map(({ icon, title, description }) => (
            <div
              key={title}
              style={{
                backgroundColor: "#F9F5F1",
                border: "1px solid #E0D5CC",
                borderRadius: "1rem",
              }}
              className="p-7"
            >
              <div
                style={{
                  backgroundColor: "#EEE6DF",
                  color: "#D05E2D",
                  width: "2.75rem",
                  height: "2.75rem",
                  borderRadius: "0.75rem",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
                className="mb-5"
              >
                {icon}
              </div>
              <h3
                style={{
                  fontFamily: "'DM Serif Text', serif",
                  color: "#472B20",
                  fontSize: "1.15rem",
                }}
                className="mb-3"
              >
                {title}
              </h3>
              <p
                style={{
                  fontFamily: "'Figtree', sans-serif",
                  color: "#6B4F42",
                  fontSize: "0.9rem",
                  lineHeight: 1.7,
                }}
              >
                {description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Final CTA ────────────────────────────────────────────────────────────────

function FinalCTA({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <section
      style={{ backgroundColor: "#472B20" }}
      className="py-20 px-6 text-center relative overflow-hidden"
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 80% at 50% 50%, rgba(208,94,45,0.15) 0%, transparent 70%)",
        }}
      />
      <div className="relative max-w-2xl mx-auto">
        <h2
          style={{
            fontFamily: "'DM Serif Text', serif",
            color: "#F5F0EC",
            fontSize: "clamp(1.6rem, 4vw, 2.4rem)",
            lineHeight: 1.3,
          }}
          className="mb-5"
        >
          The inquiry begins with a single question.
        </h2>
        <p
          style={{
            fontFamily: "'Figtree', sans-serif",
            color: "#C4A892",
            fontSize: "1rem",
            lineHeight: 1.7,
          }}
          className="mb-10"
        >
          Whether you are new to Ramana's teachings or have studied them for years,
          the portal meets you exactly where you are.
        </p>
        {isAuthenticated ? (
          <Link
            to="/chat"
            style={{
              backgroundColor: "#D05E2D",
              color: "#fff",
              fontFamily: "'Figtree', sans-serif",
              fontWeight: 600,
              fontSize: "1rem",
            }}
            className="inline-flex items-center gap-2 px-10 py-4 rounded-full hover:opacity-90 transition-opacity"
          >
            Return to your portal <ArrowRight className="w-4 h-4" />
          </Link>
        ) : (
          <Link
            to="/register"
            style={{
              backgroundColor: "#D05E2D",
              color: "#fff",
              fontFamily: "'Figtree', sans-serif",
              fontWeight: 600,
              fontSize: "1rem",
            }}
            className="inline-flex items-center gap-2 px-10 py-4 rounded-full hover:opacity-90 transition-opacity"
          >
            Begin — it's free <ArrowRight className="w-4 h-4" />
          </Link>
        )}
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer
      style={{ backgroundColor: "#2E1A12", borderTop: "1px solid #3D2518" }}
      className="px-6 py-12"
    >
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-10">
          {/* Brand */}
          <div>
            <p
              style={{
                fontFamily: "'DM Serif Text', serif",
                color: "#F5F0EC",
                fontSize: "1.1rem",
              }}
              className="mb-3"
            >
              Arunachala Samudra
            </p>
            <p
              style={{
                fontFamily: "'Figtree', sans-serif",
                color: "#8A6D5E",
                fontSize: "0.85rem",
                lineHeight: 1.65,
              }}
            >
              A living library of Sri Ramana Maharshi's authenticated teachings,
              made accessible through AI.
            </p>
          </div>

          {/* Links */}
          <div>
            <p
              style={{
                fontFamily: "'Figtree', sans-serif",
                color: "#C4A892",
                fontSize: "0.75rem",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                fontWeight: 600,
              }}
              className="mb-4"
            >
              Portal
            </p>
            <ul className="space-y-2">
              {[
                { label: "Sign In",  href: "/signin"   },
                { label: "Register", href: "/register" },
                { label: "Privacy",  href: "/privacy"  },
                { label: "Terms",    href: "/terms"    },
              ].map(({ label, href }) => (
                <li key={label}>
                  <Link
                    to={href}
                    style={{
                      fontFamily: "'Figtree', sans-serif",
                      color: "#8A6D5E",
                      fontSize: "0.88rem",
                    }}
                    className="hover:text-[#C4A892] transition-colors"
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* External */}
          <div>
            <p
              style={{
                fontFamily: "'Figtree', sans-serif",
                color: "#C4A892",
                fontSize: "0.75rem",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                fontWeight: 600,
              }}
              className="mb-4"
            >
              Resources
            </p>
            <ul className="space-y-2">
              {[
                { label: "Ramanasramam.org",      href: "https://www.ramanasramam.org" },
                { label: "David Godman",           href: "https://www.davidgodman.org"  },
                { label: "Mountain Path Journal",  href: "https://www.mountainpath.org" },
                { label: "Arunachala Ashrama NY",  href: "https://www.arunachala.org"   },
              ].map(({ label, href }) => (
                <li key={label}>
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      fontFamily: "'Figtree', sans-serif",
                      color: "#8A6D5E",
                      fontSize: "0.88rem",
                    }}
                    className="hover:text-[#C4A892] transition-colors"
                  >
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div
          style={{ borderTop: "1px solid #3D2518", paddingTop: "1.5rem" }}
          className="flex flex-col sm:flex-row justify-between items-center gap-3"
        >
          <p
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#5C3D30",
              fontSize: "0.8rem",
            }}
          >
            © 2026 Arunachala Samudra. All rights reserved.
          </p>
          <a
            href="mailto:info@arunachalasamudra.in"
            style={{
              fontFamily: "'Figtree', sans-serif",
              color: "#5C3D30",
              fontSize: "0.8rem",
            }}
            className="hover:text-[#8A6D5E] transition-colors"
          >
            info@arunachalasamudra.in
          </a>
        </div>
      </div>
    </footer>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

export default function Landing() {
  const { isAuthenticated } = useAuth();

  return (
    <div
      style={{ backgroundColor: "#F5F0EC", scrollBehavior: "smooth" }}
      className="min-h-screen overflow-x-hidden"
    >
      <PublicHeader isAuthenticated={isAuthenticated} />
      <main>
        <HeroSection isAuthenticated={isAuthenticated} />
        <DailyContemplationSection />
        <SacredLibrarySection />
        <FeaturesSection />
        <PricingSection />
        <FinalCTA isAuthenticated={isAuthenticated} />
      </main>
      <Footer />
    </div>
  );
}
