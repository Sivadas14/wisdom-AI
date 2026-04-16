/**
 * TeachingModal — full-screen overlay that shows a teaching introduction
 * with browser-native text-to-speech audio.
 *
 * Audio uses the Web Speech API (window.speechSynthesis) — no audio files
 * needed, works on all modern browsers including iOS Safari and Chrome.
 */

import { useEffect, useRef, useState } from "react";
import { X, Play, Pause, Square, Volume2 } from "lucide-react";
import { type Teaching } from "@/data/teachings";

interface TeachingModalProps {
  teaching: Teaching;
  onClose: () => void;
  onExplore: (prompt: string) => void;
}

type AudioState = "idle" | "playing" | "paused";

export default function TeachingModal({
  teaching,
  onClose,
  onExplore,
}: TeachingModalProps) {
  const [audioState, setAudioState] = useState<AudioState>("idle");
  const [speechSupported] = useState(() => "speechSynthesis" in window);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        stopAudio();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Cancel speech when modal closes
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
    };
  }, []);

  const stopAudio = () => {
    window.speechSynthesis?.cancel();
    setAudioState("idle");
    utteranceRef.current = null;
  };

  const startAudio = () => {
    if (!speechSupported) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(teaching.introduction);
    utterance.rate = 0.88;
    utterance.pitch = 0.95;

    // Prefer a calm, clear English voice
    const loadVoice = () => {
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(
        (v) =>
          v.name === "Google UK English Female" ||
          v.name === "Samantha" ||
          v.name === "Karen" ||
          v.name === "Moira" ||
          (v.lang.startsWith("en") && v.name.toLowerCase().includes("female"))
      );
      if (preferred) utterance.voice = preferred;
    };

    // Voices may not be loaded yet on first call
    if (window.speechSynthesis.getVoices().length > 0) {
      loadVoice();
    } else {
      window.speechSynthesis.onvoiceschanged = loadVoice;
    }

    utterance.onstart = () => setAudioState("playing");
    utterance.onpause = () => setAudioState("paused");
    utterance.onresume = () => setAudioState("playing");
    utterance.onend = () => {
      setAudioState("idle");
      utteranceRef.current = null;
    };
    utterance.onerror = () => {
      setAudioState("idle");
      utteranceRef.current = null;
    };

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
    setAudioState("playing");
  };

  const handlePlayPause = () => {
    if (!speechSupported) return;
    if (audioState === "idle") {
      startAudio();
    } else if (audioState === "playing") {
      window.speechSynthesis.pause();
      setAudioState("paused");
    } else {
      window.speechSynthesis.resume();
      setAudioState("playing");
    }
  };

  const handleStop = () => stopAudio();

  const handleExplore = () => {
    stopAudio();
    onExplore(teaching.chatPrompt);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8"
      style={{ backgroundColor: "rgba(58, 35, 24, 0.75)", backdropFilter: "blur(4px)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          stopAudio();
          onClose();
        }
      }}
    >
      <div
        className="relative w-full max-w-2xl max-h-[90vh] flex flex-col rounded-3xl shadow-2xl overflow-hidden"
        style={{ backgroundColor: "#fdf6ef" }}
      >
        {/* Header */}
        <div
          className="flex-shrink-0 px-6 pt-6 pb-4"
          style={{
            background: "linear-gradient(135deg, #3a2318 0%, #6b3a22 100%)",
          }}
        >
          <button
            onClick={() => { stopAudio(); onClose(); }}
            className="absolute top-4 right-4 text-white/60 hover:text-white transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>

          <p className="text-xs font-body tracking-widest uppercase text-orange-300 mb-1">
            {teaching.sanskrit}
          </p>
          <h2 className="text-2xl md:text-3xl font-heading text-white mb-1">
            {teaching.title}
          </h2>
          <p className="text-sm font-body text-white/60">
            {teaching.author} · {teaching.era}
          </p>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {teaching.introduction.split("\n\n").map((para, i) => (
            <p
              key={i}
              className="font-body text-base leading-relaxed mb-4"
              style={{ color: "#472B20" }}
            >
              {para}
            </p>
          ))}
        </div>

        {/* Audio bar */}
        <div
          className="flex-shrink-0 px-6 py-4 border-t"
          style={{ borderColor: "#e8d5c4", backgroundColor: "#fdf0e6" }}
        >
          <div className="flex items-center gap-3">
            {speechSupported ? (
              <>
                <button
                  onClick={handlePlayPause}
                  className="flex items-center justify-center w-10 h-10 rounded-full transition-all duration-200 hover:scale-105"
                  style={{
                    backgroundColor: "#D05E2D",
                    color: "white",
                  }}
                  title={audioState === "playing" ? "Pause" : "Play reading aloud"}
                >
                  {audioState === "playing" ? (
                    <Pause className="w-4 h-4" />
                  ) : (
                    <Play className="w-4 h-4 ml-0.5" />
                  )}
                </button>

                {audioState !== "idle" && (
                  <button
                    onClick={handleStop}
                    className="flex items-center justify-center w-8 h-8 rounded-full transition-colors hover:bg-orange-100"
                    style={{ color: "#D05E2D" }}
                    title="Stop"
                  >
                    <Square className="w-3.5 h-3.5" />
                  </button>
                )}

                <div className="flex items-center gap-2 ml-1">
                  <Volume2 className="w-3.5 h-3.5" style={{ color: "#9b6a4a" }} />
                  <span
                    className="text-xs font-body"
                    style={{ color: "#9b6a4a" }}
                  >
                    {audioState === "playing"
                      ? "Reading aloud…"
                      : audioState === "paused"
                      ? "Paused"
                      : "Listen to this text"}
                  </span>
                  {audioState === "playing" && (
                    <span className="flex gap-0.5">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="inline-block w-1 rounded-full"
                          style={{
                            backgroundColor: "#D05E2D",
                            height: "12px",
                            animation: `bounce 1s ease-in-out ${i * 0.15}s infinite alternate`,
                          }}
                        />
                      ))}
                    </span>
                  )}
                </div>
              </>
            ) : (
              <span className="text-xs font-body" style={{ color: "#9b6a4a" }}>
                Audio not supported in this browser
              </span>
            )}

            {/* Explore button — pushed to right */}
            <button
              onClick={handleExplore}
              className="ml-auto flex items-center gap-2 px-4 py-2 rounded-full text-sm font-body font-medium transition-all duration-200 hover:scale-105"
              style={{
                backgroundColor: "#472B20",
                color: "#fff7ea",
              }}
            >
              Explore with Wisdom AI →
            </button>
          </div>
        </div>
      </div>

      {/* Bounce animation for audio bars */}
      <style>{`
        @keyframes bounce {
          from { transform: scaleY(0.4); }
          to   { transform: scaleY(1.0); }
        }
      `}</style>
    </div>
  );
}
