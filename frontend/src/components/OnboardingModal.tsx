import { useState } from "react";
import { MessageCircle, Image, Headphones, Sparkles, X } from "lucide-react";
import { profileAPI } from "@/apis/api";

interface OnboardingModalProps {
    onClose: () => void;
}

const FEATURES = [
    {
        icon: <MessageCircle className="w-5 h-5 text-[#D05E2D]" />,
        title: "10 guided conversations",
        description: "Ask Ramana Maharshi-inspired questions and receive wisdom tailored to your inquiry.",
    },
    {
        icon: <Image className="w-5 h-5 text-[#D05E2D]" />,
        title: "3 contemplation cards",
        description: "Generate a beautiful image-based card to anchor your daily reflection practice.",
    },
    {
        icon: <Headphones className="w-5 h-5 text-[#D05E2D]" />,
        title: "15 min of audio meditation",
        description: "Receive a guided audio session — roughly three 5-minute meditations.",
    },
];

const OnboardingModal = ({ onClose }: OnboardingModalProps) => {
    const [closing, setClosing] = useState(false);

    const handleClose = async () => {
        setClosing(true);
        try {
            await profileAPI.markOnboardingSeen();
        } catch (e) {
            // Non-critical — modal will still close
            console.warn("[Onboarding] Could not mark seen on server:", e);
        }
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
            <div className="relative w-full max-w-md bg-[#FFFAF6] rounded-2xl shadow-2xl border border-[#ECE5DF] p-8 animate-in fade-in zoom-in-95 duration-300">

                {/* Close button */}
                <button
                    onClick={handleClose}
                    disabled={closing}
                    className="absolute top-4 right-4 text-[#472b20]/40 hover:text-[#472b20]/80 transition-colors"
                    aria-label="Close"
                >
                    <X className="w-5 h-5" />
                </button>

                {/* Header */}
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-12 h-12 rounded-full bg-[#FDE8D8] flex items-center justify-center mb-3">
                        <Sparkles className="w-6 h-6 text-[#D05E2D]" />
                    </div>
                    <h2 className="text-xl font-semibold text-[#472b20] leading-snug">
                        Welcome to Arunachala Samudra
                    </h2>
                    <p className="text-sm text-[#472b20]/60 mt-1">
                        A space for stillness, inquiry, and inner contemplation.
                    </p>
                </div>

                {/* Free plan callout */}
                <div className="rounded-xl bg-[#FDF0E8] border border-[#F0D8C8] p-4 mb-6">
                    <p className="text-xs font-semibold text-[#D05E2D] uppercase tracking-wider mb-3">
                        Your free plan includes
                    </p>
                    <ul className="space-y-3">
                        {FEATURES.map(({ icon, title, description }) => (
                            <li key={title} className="flex gap-3 items-start">
                                <div className="mt-0.5 shrink-0">{icon}</div>
                                <div>
                                    <p className="text-sm font-medium text-[#472b20]">{title}</p>
                                    <p className="text-xs text-[#472b20]/60 leading-relaxed">{description}</p>
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* CTA */}
                <button
                    onClick={handleClose}
                    disabled={closing}
                    className="w-full py-3 rounded-xl bg-[#D05E2D] hover:bg-[#B84E20] text-white text-sm font-semibold transition-colors disabled:opacity-60"
                >
                    {closing ? "Opening…" : "Begin your journey →"}
                </button>

                <p className="text-center text-xs text-[#472b20]/40 mt-3">
                    Upgrade anytime from the sidebar for unlimited access.
                </p>
            </div>
        </div>
    );
};

export default OnboardingModal;
