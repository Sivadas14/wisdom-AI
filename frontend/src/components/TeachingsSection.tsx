/**
 * TeachingsSection — a grid of five sacred-text cards shown on the home page.
 * Clicking a card opens TeachingModal with the full introduction and audio.
 */

import { useState } from "react";
import { BookOpen } from "lucide-react";
import { TEACHINGS, type Teaching } from "@/data/teachings";
import TeachingModal from "./TeachingModal";

interface TeachingsSectionProps {
  onExplore: (prompt: string) => void;
}

export default function TeachingsSection({ onExplore }: TeachingsSectionProps) {
  const [selected, setSelected] = useState<Teaching | null>(null);

  return (
    <>
      <div className="max-w-4xl mx-auto mb-10 md:mb-12">
        {/* Section header */}
        <div className="flex items-center gap-3 mb-5">
          <BookOpen className="w-5 h-5 flex-shrink-0" style={{ color: "#D05E2D" }} />
          <div>
            <h2 className="text-lg md:text-xl font-heading" style={{ color: "#472B20" }}>
              Guided Introduction to the Teachings
            </h2>
            <p className="text-xs font-body mt-0.5" style={{ color: "#9b6a4a" }}>
              Five sacred texts · tap to read &amp; listen
            </p>
          </div>
        </div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
          {TEACHINGS.map((teaching, idx) => (
            <button
              key={teaching.id}
              onClick={() => setSelected(teaching)}
              className="text-left rounded-2xl border p-5 transition-all duration-200 hover:scale-[1.02] hover:shadow-md group"
              style={{
                backgroundColor: "#fffaf5",
                borderColor: "#e8d5c4",
              }}
            >
              {/* Number badge */}
              <span
                className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-body font-semibold mb-3"
                style={{ backgroundColor: "#f0e0d0", color: "#D05E2D" }}
              >
                {idx + 1}
              </span>

              {/* Sanskrit name */}
              <p
                className="text-xs font-body tracking-widest uppercase mb-1"
                style={{ color: "#D05E2D" }}
              >
                {teaching.sanskrit}
              </p>

              {/* English title */}
              <h3
                className="text-base font-heading mb-1 leading-snug"
                style={{ color: "#472B20" }}
              >
                {teaching.title}
              </h3>

              {/* Author · era */}
              <p
                className="text-xs font-body mb-3"
                style={{ color: "#9b6a4a" }}
              >
                {teaching.author} · {teaching.era}
              </p>

              {/* Teaser */}
              <p
                className="text-xs font-body leading-relaxed line-clamp-3"
                style={{ color: "#6b4c38" }}
              >
                {teaching.teaser}
              </p>

              {/* Open hint */}
              <p
                className="text-xs font-body font-medium mt-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                style={{ color: "#D05E2D" }}
              >
                Read &amp; listen →
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Modal */}
      {selected && (
        <TeachingModal
          teaching={selected}
          onClose={() => setSelected(null)}
          onExplore={(prompt) => {
            setSelected(null);
            onExplore(prompt);
          }}
        />
      )}
    </>
  );
}
