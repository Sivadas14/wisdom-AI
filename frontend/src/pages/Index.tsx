
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArrowRight, MessageCircle, Heart, MessageSquare, HelpCircle, Plus } from "lucide-react";
import UserMenu from "@/components/UserMenu";
import AtmosphericEntry from "@/components/AtmosphericEntry";
import TeachingsSection from "@/components/TeachingsSection";
import { chatAPI, contemplationAPI } from "@/apis/api";
import { type Conversation, type Contemplation } from "@/apis/wire";

const Index = () => {
  const [query, setQuery] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  // Today's Contemplation — fetched from backend, same for every user each
  // day (IST). Used to build the first quick-prompt button's prompt text.
  const [contemplation, setContemplation] = useState<Contemplation | null>(null);
  const navigate = useNavigate();

  // Fetch conversations on component mount
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        setIsLoadingConversations(true);
        const response = await chatAPI.getConversations();
        setConversations(response.conversations);
      } catch (error) {
        console.error("Failed to fetch conversations:", error);
        // Fallback to empty array if fetch fails
        setConversations([]);
      } finally {
        setIsLoadingConversations(false);
      }
    };

    fetchConversations();
  }, []);

  // Fetch today's contemplation. On any failure, show a hardcoded
  // fallback so the card never gets stuck on the loading skeleton.
  useEffect(() => {
    let cancelled = false;
    const FALLBACK: Contemplation = {
      date: new Date().toISOString().slice(0, 10),
      quote: "Silence is the true teaching. Sit quietly, and notice what remains when thought subsides.",
      question: "Who is the one who is aware right now?",
    };
    contemplationAPI
      .getToday()
      .then((c) => {
        if (!cancelled) setContemplation(c);
      })
      .catch((err) => {
        console.error("Failed to fetch today's contemplation:", err);
        if (!cancelled) setContemplation(FALLBACK);
      });
    return () => {
      cancelled = true;
    };
  }, []);


  const handleSend = async () => {
    if (query.trim()) {
      // Navigate to the chat with the initial query
      // The conversation will be created when the first message is sent
      navigate("/chat", { state: { initialQuery: query } });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  const handleChatClick = (conversationId: string) => {
    navigate(`/chat/${conversationId}`);
  };

  const handleQuickPrompt = async (prompt: string) => {
    // Navigate to the chat with the initial query (if any)
    if (prompt.trim()) {
      navigate("/chat", { state: { initialQuery: prompt } });
    } else {
      // For empty prompts (like "New Chat"), just navigate without any initial query
      navigate("/chat");
    }
  };

  // Today's Contemplation: prompt text to send to chat when user taps "Begin Inquiry"
  const todaysPrompt = contemplation
    ? `${contemplation.quote}\n\n${contemplation.question}`
    : "What does Ramana Maharshi teach about turning attention inward?";

  const quickPrompts = [
    {
      icon: <MessageSquare className="w-4 h-4" />,
      label: "Share thoughts",
      prompt: "Share some thoughts of Bhagavan Ramana Maharshi about wisdom."
    },
    {
      icon: <HelpCircle className="w-4 h-4" />,
      label: "Resolve confusion",
      prompt: "What are some ways to reduce confusion?"
    },
    {
      icon: <Plus className="w-4 h-4" />,
      label: "New Chat",
      prompt: ""
    }
  ];

  // Helper function to format date
  const formatTimestamp = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));
    const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60));
    const diffInWeeks = Math.floor(diffInDays / 7);

    if (diffInHours < 1) {
      return "Just now";
    } else if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours === 1 ? '' : 's'} ago`;
    } else if (diffInDays === 1) {
      return "1 day ago";
    } else if (diffInDays < 7) {
      return `${diffInDays} days ago`;
    } else if (diffInWeeks === 1) {
      return "1 week ago";
    } else if (diffInWeeks < 4) {
      return `${diffInWeeks} weeks ago`;
    } else {
      const diffInMonths = Math.floor(diffInDays / 30);
      return `${diffInMonths} month${diffInMonths === 1 ? '' : 's'} ago`;
    }
  };

  return (
    <div className="min-h-full flex items-start justify-center p-4 md:pt-16 pb-20" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
      <AtmosphericEntry />
      <div className="w-full max-w-6xl mx-auto">
        {/* User Menu in top right - Hidden on mobile as it's in sidebar */}
        <div className="hidden md:flex justify-end mb-8">
          <UserMenu />
        </div>

        <div className="text-center mb-8 md:mb-12 mt-8 md:mt-0">
          <h1 className="text-4xl md:text-6xl font-heading text-brand-heading mb-4 md:mb-8">
            Wisdom AI
          </h1>
        </div>

        {/* Today's Contemplation Card */}
        <div className="max-w-2xl mx-auto mb-6 md:mb-8">
          <div
            onClick={() => handleQuickPrompt(todaysPrompt)}
            className="cursor-pointer rounded-2xl border border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50 shadow-md hover:shadow-lg transition-all duration-200 hover:scale-[1.01] hover:border-brand-button p-5 md:p-6"
          >
            <div className="flex items-center gap-2 mb-3">
              <Heart className="w-4 h-4 text-brand-button flex-shrink-0" />
              <span className="text-xs font-semibold tracking-widest uppercase text-brand-button font-body">
                Today's Contemplation
              </span>
            </div>

            {contemplation ? (
              <>
                <p className="text-brand-heading font-heading text-base md:text-lg leading-relaxed mb-4">
                  "{contemplation.quote}"
                </p>
                <p className="text-brand-body font-body text-sm md:text-base italic border-t border-orange-100 pt-3">
                  ✦ {contemplation.question}
                </p>
              </>
            ) : (
              /* Loading skeleton */
              <div className="space-y-2 animate-pulse">
                <div className="h-4 bg-orange-100 rounded w-full" />
                <div className="h-4 bg-orange-100 rounded w-4/5" />
                <div className="h-3 bg-orange-100 rounded w-3/5 mt-3" />
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <span className="text-xs text-brand-button font-body font-medium">
                Begin Inquiry →
              </span>
            </div>
          </div>
        </div>

        {/* Guided Introduction to the Teachings */}
        <TeachingsSection onExplore={handleQuickPrompt} />

        {/* Quick Prompts */}
        <div className="max-w-2xl mx-auto mb-10 md:mb-12">
          <div className="flex flex-wrap justify-center gap-2 md:gap-3">
            {quickPrompts.map((prompt, index) => (
              <Button
                key={index}
                onClick={() => handleQuickPrompt(prompt.prompt)}
                variant="outline"
                className="flex items-center gap-2 px-3 md:px-4 py-1.5 md:py-2 rounded-full bg-white/80 hover:bg-white border-gray-200 text-brand-body text-sm md:text-base font-body transition-all duration-200 hover:scale-105 hover:border-brand-button"
              >
                {prompt.icon}
                {prompt.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Previous Chats Section */}
        <div className="max-w-4xl mx-auto">
          {isLoadingConversations ? (
            <div className="text-center py-8">
              <p className="text-brand-body font-body">Loading conversations...</p>
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8">
              <h2 className="text-xl md:text-2xl font-heading text-brand-heading mb-4">No conversations</h2>
              <p className="text-brand-body font-body">Start a new conversation above!</p>
            </div>
          ) : (
            <>
              <h2 className="text-xl md:text-2xl font-heading text-brand-heading mb-6 text-center">Your Conversations</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {conversations.map((conversation) => (
                  <div
                    key={conversation.id}
                    onClick={() => handleChatClick(conversation.id)}
                    className="bg-white rounded-2xl p-6 shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer hover:scale-105 border border-gray-100 hover:border-brand-button"
                  >
                    <div className="flex items-start gap-3">
                      <div className="bg-orange-100 rounded-full p-2 flex-shrink-0">
                        <MessageCircle className="w-5 h-5 text-brand-button" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium font-heading text-brand-heading mb-2 truncate">
                          {conversation.title || "Untitled Conversation"}
                        </h3>
                        <p className="text-sm text-brand-body mb-3 line-clamp-2 font-body">
                          Click to continue this conversation...
                        </p>
                        <span className="text-xs text-gray-400 font-body">
                          {formatTimestamp(conversation.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Index;
