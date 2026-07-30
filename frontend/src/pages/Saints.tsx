/**
 * Saints.tsx — Public page listing saints associated with Arunachala / Ramana lineage.
 * Accessible at /saints (public, no auth required).
 */

import { Link } from "react-router-dom";
import { ArrowLeft, ExternalLink } from "lucide-react";

// ─── Design tokens (matching Landing.tsx) ─────────────────────────────────────
const T = {
  cream:    "#F5F0EC",
  creamMid: "#EDE5DC",
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
  dates?: string;
  description: string;
  witnessesLink?: string;   // anchor on landing page
  externalLink?: string;
  externalLabel?: string;
}

const ANCIENT_SAINTS: Saint[] = [
  {
    name: "Adi Shankaracharya",
    dates: "c. 788–820 CE",
    description:
      "The master consolidator of Advaita Vedanta. His commentaries on the Upanishads, Bhagavad Gita and Brahma Sutras remain the foundation of non-dual understanding in India.",
  },
  {
    name: "Ashtavakra",
    dates: "Vedic era",
    description:
      "Sage whose dialogue with King Janaka — the Ashtavakra Gita — is one of the most direct statements of the non-dual understanding ever recorded. Ramana Maharshi often quoted it.",
  },
  {
    name: "Ribhu",
    dates: "Vedic era",
    description:
      "Disciple of Brahma and teacher of Nidagha. The Ribhu Gita, extracted from the Shiva Rahasya Purana, was Ramana Maharshi's favourite text and is recited daily at Sri Ramanasramam.",
  },
];

const MODERN_SAINTS: Saint[] = [
  {
    name: "Sri Ramana Maharshi",
    dates: "1879–1950",
    description:
      "The Sage of Arunachala. At sixteen he underwent a spontaneous death-experience that resolved into the permanent recognition of the Self. He lived at the foot of Arunachala Hill for the remainder of his life, teaching mainly through silence and the practice of Self-enquiry (\"Who am I?\").",
    externalLink: "https://www.sriramanamaharshi.org",
    externalLabel: "Sri Ramanasramam",
  },
  {
    name: "Paul Brunton",
    dates: "1898–1981",
    description:
      "British philosopher and author who first brought Ramana Maharshi to the West through his 1934 book A Search in Secret India. Ramana said of him: \"Paul Brunton is one of my 'eyes.' My shakti is working through him. Follow him closely.\" His later work — sixteen volumes of The Notebooks of Paul Brunton — explores what he called The Short Path: the direct, immediate recognition of the Overself that is already present.",
    witnessesLink: "/#witnesses",
    externalLink: "https://www.paulbrunton.org",
    externalLabel: "paulbrunton.org — his books & archive",
  },
  {
    name: "Nisargadatta Maharaj",
    dates: "1897–1981",
    description:
      "Mumbai-based teacher of Advaita Vedanta whose dialogues were compiled in I Am That (1973). Like Ramana, he pointed directly to the sense 'I am' as the doorway to the Absolute.",
  },
  {
    name: "Swami Vivekananda",
    dates: "1863–1902",
    description:
      "Principal disciple of Sri Ramakrishna who introduced Vedanta and Yoga to the Western world at the Parliament of the World's Religions, Chicago, 1893.",
  },
];

// ─── Card component ───────────────────────────────────────────────────────────

function SaintCard({ saint }: { saint: Saint }) {
  return (
    <div
      style={{
        backgroundColor: "rgba(255,252,249,0.04)",
        border: "1px solid rgba(240,216,200,0.15)",
        borderRadius: "8px",
        padding: "1.5rem 1.75rem",
        transition: "border-color 0.2s",
      }}
      onMouseEnter={e =>
        ((e.currentTarget as HTMLElement).style.borderColor = "rgba(184,90,45,0.4)")
      }
      onMouseLeave={e =>
        ((e.currentTarget as HTMLElement).style.borderColor = "rgba(240,216,200,0.15)")
      }
    >
      {/* Name + dates */}
      <div style={{ marginBottom: "0.75rem" }}>
        <h3
          style={{
            fontFamily: T.serif,
            fontSize: "clamp(1.1rem, 2.5vw, 1.3rem)",
            color: "rgba(245,230,210,0.92)",
            margin: 0,
            fontWeight: 400,
            letterSpacing: "0.01em",
          }}
        >
          {saint.name}
        </h3>
        {saint.dates && (
          <p
            style={{
              fontFamily: T.sans,
              fontSize: "0.72rem",
              color: "rgba(196,168,146,0.55)",
              marginTop: "0.2rem",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            {saint.dates}
          </p>
        )}
      </div>

      {/* Description */}
      <p
        style={{
          fontFamily: T.sans,
          fontSize: "0.9rem",
          color: "rgba(220,200,182,0.78)",
          lineHeight: 1.75,
          margin: 0,
          marginBottom: saint.witnessesLink || saint.externalLink ? "1.1rem" : 0,
        }}
      >
        {saint.description}
      </p>

      {/* Links */}
      {(saint.witnessesLink || saint.externalLink) && (
        <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
          {saint.witnessesLink && (
            <Link
              to={saint.witnessesLink}
              style={{
                fontFamily: T.sans,
                fontSize: "0.82rem",
                color: "rgba(184,90,45,0.85)",
                textDecoration: "underline",
                textDecorationColor: "rgba(184,90,45,0.35)",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              View his profile on this site
              <ArrowLeft
                style={{ transform: "rotate(180deg)", width: "13px", height: "13px" }}
              />
            </Link>
          )}
          {saint.externalLink && (
            <a
              href={saint.externalLink}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontFamily: T.sans,
                fontSize: "0.82rem",
                color: "rgba(196,168,146,0.65)",
                textDecoration: "underline",
                textDecorationColor: "rgba(196,168,146,0.3)",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
            >
              {saint.externalLabel ?? saint.externalLink}
              <ExternalLink style={{ width: "11px", height: "11px" }} />
            </a>
          )}
        </div>
      )}
    </div>
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
          maxWidth: "860px",
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
            color: "rgba(245,230,210,0.7)",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.4rem",
            letterSpacing: "0.01em",
          }}
        >
          <ArrowLeft style={{ width: "15px", height: "15px" }} />
          Arunachala Samudra
        </Link>

        <Link
          to="/register"
          style={{
            fontFamily: T.sans,
            fontSize: "0.8rem",
            color: "rgba(184,90,45,0.8)",
            textDecoration: "underline",
            textDecorationColor: "rgba(184,90,45,0.3)",
          }}
        >
          Enter the Portal →
        </Link>
      </header>

      {/* ── Hero ── */}
      <div
        style={{
          maxWidth: "860px",
          margin: "0 auto",
          padding: "3.5rem 1.5rem 2.5rem",
          borderBottom: "1px solid rgba(240,216,200,0.1)",
        }}
      >
        <p
          style={{
            fontFamily: T.sans,
            fontSize: "0.72rem",
            color: "rgba(196,168,146,0.5)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "0.75rem",
          }}
        >
          Arunachala Samudra
        </p>
        <h1
          style={{
            fontFamily: T.serif,
            fontSize: "clamp(2rem, 6vw, 3.25rem)",
            color: "rgba(245,230,210,0.95)",
            margin: "0 0 1rem",
            fontWeight: 400,
            lineHeight: 1.15,
            letterSpacing: "-0.01em",
          }}
        >
          Saints & Sages
        </h1>
        <p
          style={{
            fontFamily: T.sans,
            fontSize: "clamp(0.92rem, 2vw, 1.05rem)",
            color: "rgba(220,200,182,0.7)",
            maxWidth: "560px",
            lineHeight: 1.75,
          }}
        >
          The teachers and witnesses who have walked the path of Arunachala — from
          ancient seers to modern sages who carried the flame of Self-enquiry into the
          contemporary world.
        </p>
      </div>

      {/* ── Content ── */}
      <main style={{ maxWidth: "860px", margin: "0 auto", padding: "0 1.5rem 5rem" }}>

        {/* Ancient sages */}
        <section style={{ paddingTop: "3rem" }}>
          <h2
            style={{
              fontFamily: T.sans,
              fontSize: "0.72rem",
              color: "rgba(196,168,146,0.5)",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "1.5rem",
              fontWeight: 600,
            }}
          >
            Ancient Sages
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {ANCIENT_SAINTS.map(s => (
              <SaintCard key={s.name} saint={s} />
            ))}
          </div>
        </section>

        {/* Divider */}
        <div
          style={{
            borderTop: "1px solid rgba(240,216,200,0.08)",
            margin: "3rem 0",
          }}
        />

        {/* Modern saints */}
        <section>
          <h2
            style={{
              fontFamily: T.sans,
              fontSize: "0.72rem",
              color: "rgba(196,168,146,0.5)",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "1.5rem",
              fontWeight: 600,
            }}
          >
            Modern Saints
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {MODERN_SAINTS.map(s => (
              <SaintCard key={s.name} saint={s} />
            ))}
          </div>
        </section>

        {/* Footer note */}
        <div
          style={{
            marginTop: "4rem",
            paddingTop: "2rem",
            borderTop: "1px solid rgba(240,216,200,0.08)",
            textAlign: "center",
          }}
        >
          <p
            style={{
              fontFamily: T.sans,
              fontSize: "0.82rem",
              color: "rgba(196,168,146,0.45)",
              lineHeight: 1.75,
            }}
          >
            This list grows as the lineage is explored. If you feel a saint belongs
            here, write to us at{" "}
            <a
              href="mailto:info@arunachalasamudra.in"
              style={{ color: "rgba(184,90,45,0.6)", textDecoration: "underline" }}
            >
              info@arunachalasamudra.in
            </a>
            .
          </p>
          <Link
            to="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              marginTop: "1.5rem",
              fontFamily: T.sans,
              fontSize: "0.84rem",
              color: "rgba(245,230,210,0.55)",
              textDecoration: "none",
            }}
          >
            <ArrowLeft style={{ width: "13px", height: "13px" }} />
            Return to Arunachala Samudra
          </Link>
        </div>
      </main>
    </div>
  );
};

export default Saints;
