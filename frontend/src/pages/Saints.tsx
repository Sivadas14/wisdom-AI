/**
 * Saints.tsx — Public page replicating arunachalasamudra.co.in/saints
 * Lists all saints of Tiruvannamalai. Accessible at /saints, no auth required.
 */

import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

// ─── Design tokens (matching Landing.tsx) ─────────────────────────────────────
const T = {
  cream:    "#F5F0EC",
  umber:    "#2E1208",
  brown:    "#472B20",
  muted:    "#8A6D5E",
  accent:   "#B85A2D",
  border:   "#E0D5CC",
  serif:    "'DM Serif Text', serif",
  sans:     "'Figtree', sans-serif",
};

// ─── Saint data ───────────────────────────────────────────────────────────────

interface Saint {
  name: string;
  slug?: string;          // sub-page slug within /saints/
  witnessesAnchor?: true; // special case: links to /#witnesses on landing
}

const ANCIENT_SAINTS: Saint[] = [
  { name: "Arunagirinathar",    slug: "arunagirinathar" },
  { name: "Guhai Namashivaya",  slug: "guhai-namashivaya" },
  { name: "Guru Namashivaya",   slug: "guru-namashivaya" },
  { name: "Isanya Desikar",     slug: "isanya-desikar" },
  { name: "Saiva Archaryas",    slug: "saiva-archaryas" },
];

const MODERN_SAINTS: Saint[] = [
  { name: "Abhishiktananda",     slug: "abhishiktananda" },
  { name: "Isakki Swamigal",    slug: "isakki-swamigal" },
  { name: "Mookupodi Swamigal", slug: "mookupodi-swamigal" },
  { name: "Nannagaru",          slug: "nannagaru" },
  { name: "Papa Ramdas",        slug: "papa-ramdas" },
  { name: "Paul Brunton",       witnessesAnchor: true },
  { name: "Poondi Swami",       slug: "poondi-swami" },
  { name: "Ramana Maharshi",    slug: "sri-ramana-maharshi" },
  { name: "Seshadri Swamigal",  slug: "seshadri-swamigal" },
  { name: "Sri Sadhu Om",       slug: "sri-sadhu-om" },
  { name: "Tinnai Swami",       slug: "tinnai-swami" },
  { name: "Yogi Ram Suratkumar", slug: "yogi-ram-suratkumar" },
];

// ─── Saint row ────────────────────────────────────────────────────────────────

function SaintRow({ saint }: { saint: Saint }) {
  const inner = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1rem 1.25rem",
        borderRadius: "6px",
        border: "1px solid rgba(224,213,204,0.18)",
        transition: "background 0.15s, border-color 0.15s",
        cursor: saint.slug || saint.witnessesAnchor ? "pointer" : "default",
      }}
      onMouseEnter={e => {
        if (!saint.slug && !saint.witnessesAnchor) return;
        const el = e.currentTarget as HTMLElement;
        el.style.background = "rgba(184,90,45,0.07)";
        el.style.borderColor = "rgba(184,90,45,0.35)";
      }}
      onMouseLeave={e => {
        const el = e.currentTarget as HTMLElement;
        el.style.background = "transparent";
        el.style.borderColor = "rgba(224,213,204,0.18)";
      }}
    >
      <span
        style={{
          fontFamily: T.serif,
          fontSize: "clamp(1rem, 2.5vw, 1.15rem)",
          color: saint.slug || saint.witnessesAnchor
            ? "rgba(245,230,210,0.9)"
            : "rgba(245,230,210,0.55)",
          fontWeight: 400,
          letterSpacing: "0.01em",
        }}
      >
        {saint.name}
      </span>
      {(saint.slug || saint.witnessesAnchor) && (
        <ArrowRight
          style={{
            width: "15px",
            height: "15px",
            color: "rgba(184,90,45,0.55)",
            flexShrink: 0,
          }}
        />
      )}
    </div>
  );

  if (saint.witnessesAnchor) {
    return <Link to="/#witnesses" style={{ textDecoration: "none", display: "block" }}>{inner}</Link>;
  }
  if (saint.slug) {
    return <Link to={`/saints/${saint.slug}`} style={{ textDecoration: "none", display: "block" }}>{inner}</Link>;
  }
  return <div>{inner}</div>;
}

// ─── Section ──────────────────────────────────────────────────────────────────

function SaintSection({ title, saints }: { title: string; saints: Saint[] }) {
  return (
    <section style={{ marginBottom: "2.5rem" }}>
      <h2
        style={{
          fontFamily: T.sans,
          fontSize: "0.7rem",
          color: "rgba(196,168,146,0.5)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          fontWeight: 600,
          marginBottom: "1rem",
        }}
      >
        {title}
      </h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
        {saints.map(s => <SaintRow key={s.name} saint={s} />)}
      </div>
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const Saints = () => {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(160deg, #1a0c06 0%, #2E1208 40%, #1a0c06 100%)",
        fontFamily: T.sans,
        color: T.cream,
      }}
    >
      {/* ── Header ── */}
      <header
        style={{
          maxWidth: "720px",
          margin: "0 auto",
          padding: "2rem 1.5rem 0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Link
          to="/"
          style={{
            fontFamily: T.serif,
            fontSize: "1rem",
            color: "rgba(245,230,210,0.65)",
            textDecoration: "none",
            letterSpacing: "0.01em",
          }}
        >
          Arunachala Samudra
        </Link>
        <Link
          to="/register"
          style={{
            fontFamily: T.sans,
            fontSize: "0.8rem",
            color: "rgba(184,90,45,0.75)",
            textDecoration: "underline",
            textDecorationColor: "rgba(184,90,45,0.3)",
          }}
        >
          Wisdom AI →
        </Link>
      </header>

      {/* ── Hero ── */}
      <div
        style={{
          maxWidth: "720px",
          margin: "0 auto",
          padding: "3rem 1.5rem 2.5rem",
          borderBottom: "1px solid rgba(240,216,200,0.1)",
        }}
      >
        {/* Breadcrumb */}
        <p
          style={{
            fontFamily: T.sans,
            fontSize: "0.75rem",
            color: "rgba(196,168,146,0.45)",
            marginBottom: "1.25rem",
          }}
        >
          <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>Home</Link>
          {" › "}Saints
        </p>

        <h1
          style={{
            fontFamily: T.serif,
            fontSize: "clamp(2rem, 6vw, 3rem)",
            color: "rgba(245,230,210,0.95)",
            margin: "0 0 0.75rem",
            fontWeight: 400,
            lineHeight: 1.15,
            letterSpacing: "-0.01em",
          }}
        >
          Saints of Tiruvannamalai
        </h1>
        <p
          style={{
            fontFamily: T.sans,
            fontSize: "0.88rem",
            color: "rgba(196,168,146,0.55)",
            marginBottom: "0.4rem",
            fontStyle: "italic",
          }}
        >
          Be inspired by real journeys of transformation.
        </p>
        <p
          style={{
            fontFamily: T.sans,
            fontSize: "clamp(0.88rem, 2vw, 0.98rem)",
            color: "rgba(220,200,182,0.68)",
            maxWidth: "560px",
            lineHeight: 1.8,
            marginTop: "1.25rem",
          }}
        >
          Tiruvannamalai has been home to an unbroken lineage of saints — ancient and
          modern — who were drawn to the sacred hill of Arunachala and realised its grace
          through their lives. Their stories stand as living testimony to the
          transformative power of devotion, surrender, and self-inquiry.
        </p>
      </div>

      {/* ── Saint lists ── */}
      <main style={{ maxWidth: "720px", margin: "0 auto", padding: "3rem 1.5rem 5rem" }}>
        <SaintSection title="Ancient Saints" saints={ANCIENT_SAINTS} />
        <SaintSection title="Modern Saints"  saints={MODERN_SAINTS} />

        {/* CTA */}
        <div
          style={{
            marginTop: "3rem",
            padding: "1.75rem 2rem",
            background: "rgba(46,18,8,0.5)",
            border: "1px solid rgba(240,216,200,0.1)",
            borderRadius: "8px",
          }}
        >
          <p
            style={{
              fontFamily: T.serif,
              fontSize: "1.1rem",
              color: "rgba(245,230,210,0.88)",
              marginBottom: "0.4rem",
              fontWeight: 400,
            }}
          >
            Continue this inquiry with the Wisdom AI
          </p>
          <p
            style={{
              fontFamily: T.sans,
              fontSize: "0.85rem",
              color: "rgba(196,168,146,0.6)",
              marginBottom: "1.1rem",
              lineHeight: 1.6,
            }}
          >
            Ask anything about Ramana Maharshi's teachings — grounded in the source texts.
          </p>
          <Link
            to="/register"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              fontFamily: T.sans,
              fontSize: "0.85rem",
              color: T.accent,
              textDecoration: "underline",
              textDecorationColor: "rgba(184,90,45,0.35)",
            }}
          >
            Open the Wisdom AI <ArrowRight style={{ width: "13px", height: "13px" }} />
          </Link>
        </div>
      </main>
    </div>
  );
};

export default Saints;
