import { useState, useEffect, useCallback, useRef } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pencil, Save, Volume2, Mic, ArrowRight, ArrowLeft, Image as ImageIcon, Music, Video, Download, Loader2, Sparkles, Brain, Timer, BookOpen, PlayIcon, MusicIcon, LayoutGrid, X } from "lucide-react";
import { teachingTopics, personalTopics } from "@/data/chatTopics";
import ChatMessage from "@/components/ChatMessage";
import ExploreMore from "@/components/ExploreMore";
import InlineMeditationCreator from "@/components/InlineMeditationCreator";
import UserMenu from "@/components/UserMenu";
import { InlineMediaPlayer } from '@/components/InlineMediaPlayer';
import { AddonsModal } from "@/components/billing/AddonsModal";
import { chatAPI, contentAPI } from "@/apis/api";
import { useUsage } from "@/contexts/UsageContext";
import { toast } from "sonner";
import { getFullStorageUrl } from "@/lib/storage";
import type { Message as APIMessage, Conversation, ConversationDetailResponse, ContentGeneration } from "@/apis/wire";

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  thinking?: string;
  citations?: { name: string; url: string; }[];
  generatedContents?: {
    id: string;
    type: 'image' | 'audio' | 'video';
    url?: string;
    status: 'pending' | 'processing' | 'complete' | 'failed';
    transcript?: string | null;
  }[];
}

const Chat = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { conversationId } = useParams<{ conversationId: string }>();
  const { usage, refreshUsage, checkQuota, setShowPlansModal } = useUsage();
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentInput, setCurrentInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showExploreMore, setShowExploreMore] = useState(false);
  const [showMeditationCreator, setShowMeditationCreator] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [title, setTitle] = useState("New Conversation");
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [conversationDetail, setConversationDetail] = useState<ConversationDetailResponse | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const [hasProcessedInitialQuery, setHasProcessedInitialQuery] = useState(false);
  const [topicTab, setTopicTab] = useState<"teachings" | "personal">("teachings");
  const [showTopicPicker, setShowTopicPicker] = useState(false);

  // Inline image generation states
  const [generatingImageForMessage, setGeneratingImageForMessage] = useState<string | null>(null);
  const [imageGenerationContentId, setImageGenerationContentId] = useState<string | null>(null);

  const [imageGenerationError, setImageGenerationError] = useState<string | null>(null);

  const [generatingAudioForMessage, setGeneratingAudioForMessage] = useState<string | null>(null);
  const [audioGenerationContentId, setAudioGenerationContentId] = useState<string | null>(null);
  const [audioGenerationError, setAudioGenerationError] = useState<string | null>(null);

  const [generatingVideoForMessage, setGeneratingVideoForMessage] = useState<string | null>(null);
  const [videoGenerationContentId, setVideoGenerationContentId] = useState<string | null>(null);
  const [videoGenerationError, setVideoGenerationError] = useState<string | null>(null);

  // Combined state for blocking concurrent generations
  const generatingContentForMessage = generatingImageForMessage || generatingAudioForMessage || generatingVideoForMessage;

  // Global busy state: strict "one process at a time" rule
  const isBusy = isThinking || isStreaming || !!generatingContentForMessage;

  // State for full screen player
  const [selectedMedia, setSelectedMedia] = useState<{ url: string; type: 'audio' | 'video' } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const messagesRef = useRef<Message[]>([]);
  const sendingRef = useRef(false);

  // Keep messagesRef in sync with messages
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Ref for the scroll container
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLength = useRef(0);

  // Auto-scroll logic
  useEffect(() => {
    const scrollContainer = messagesEndRef.current?.parentElement; // Assuming scroll on parent

    // Check if we should scroll (new message or streaming)
    const isNewMessage = messages.length > prevMessagesLength.current;
    const shouldScroll = isNewMessage || isStreaming || isThinking;

    if (shouldScroll) {
      // Use 'auto' (instant) for streaming to avoid jitter, 'smooth' for new messages
      const behavior = isStreaming ? 'auto' : 'smooth';

      // Small timeout to ensure DOM is updated
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior, block: 'end' });
      }, 100);
    }

    prevMessagesLength.current = messages.length;
  }, [messages, isStreaming, isThinking]);

  // Focus input and scroll to bottom when messages load
  useEffect(() => {
    if (!isLoadingConversation && messages.length > 0) {
      inputRef.current?.focus();
      // Force scroll to bottom on load
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
      }, 100);
    }
  }, [isLoadingConversation, messages.length]);

  // Check for checkout redirect and refresh usage
  useEffect(() => {
    const urlParams = new URLSearchParams(location.search);
    const checkoutSuccess = urlParams.get('checkout_success');
    const sessionId = urlParams.get('session_id');
    const customerSessionToken = urlParams.get('customer_session_token');

    if (checkoutSuccess === 'true' || sessionId || customerSessionToken) {
      console.log('🎉 [Chat] Checkout success detected, refreshing usage...');

      // Refresh usage to show new quota
      refreshUsage();

      // Show success message
      toast.success("Purchase successful! Your quota has been updated.");

      // Clean up the URL
      navigate(location.pathname, { replace: true });
    }
  }, [location.search, location.pathname, navigate, refreshUsage]);

  // Clear all state when conversationId changes or when going to home chat
  useEffect(() => {
    console.log(`💬 [Chat] Mounted/Updated. conversationId: ${conversationId}`);

    setCurrentInput("");

    // Reset states when conversationId becomes undefined (navigating to /chat)
    if (!conversationId) {
      setMessages([]);
      setTitle("New Conversation");
      setConversationDetail(null);
      setQuestions([]);
      setShowExploreMore(false);
      setShowMeditationCreator(false);
      setIsEditingTitle(false);
      // Clear any pending generation states
      setGeneratingImageForMessage(null);
      setImageGenerationContentId(null);
      setImageGenerationError(null);
      setGeneratingAudioForMessage(null);
      setAudioGenerationContentId(null);
      setAudioGenerationError(null);
      setGeneratingVideoForMessage(null);
      setVideoGenerationContentId(null);
      setVideoGenerationError(null);
    }
  }, [conversationId]);

  // Polling hook for all content generations
  useEffect(() => {
    // Collect all pending/processing content IDs from all messages
    const getPendingContentIds = (): Set<string> => {
      const pendingIds = new Set<string>();

      messagesRef.current.forEach(msg => {
        if (msg.generatedContents) {
          msg.generatedContents.forEach(content => {
            if (content.status === 'pending' || content.status === 'processing') {
              pendingIds.add(content.id);
            }
          });
        }
      });

      // Also add the current inline generations if active
      if (imageGenerationContentId) {
        pendingIds.add(imageGenerationContentId);
      }
      if (audioGenerationContentId) {
        pendingIds.add(audioGenerationContentId);
      }
      if (videoGenerationContentId) {
        pendingIds.add(videoGenerationContentId);
      }

      return pendingIds;
    };

    const pendingIds = getPendingContentIds();

    // Only set up polling if there are pending content generations
    if (pendingIds.size === 0) return;

    const pollContentGenerations = async () => {
      const currentPendingIds = getPendingContentIds();
      if (currentPendingIds.size === 0) return;

      // Poll each pending content
      const pollPromises = Array.from(currentPendingIds).map(async (contentId) => {
        try {
          const content = await contentAPI.getContent(contentId);

          console.log(`Polled content ${contentId}:`, content.status, content.content_url);

          // Only update if status changed to complete or failed
          if (content.status === "complete" || content.status === "failed") {
            setMessages(prev => prev.map(msg => {
              // Skip if message doesn't have any generated contents
              if (!msg.generatedContents || msg.generatedContents.length === 0) {
                return msg;
              }

              // Check if this message has the content we're updating
              const hasContent = msg.generatedContents.some(gc => gc.id === contentId);
              if (!hasContent) {
                return msg;
              }

              // Update the matching content
              const updatedContents = msg.generatedContents.map(gc => {
                if (gc.id === contentId) {
                  const updated = {
                    ...gc,
                    status: content.status as 'complete' | 'failed',
                    url: content.content_url ? getFullStorageUrl(content.content_url) : gc.url,
                    transcript: content.transcript || gc.transcript
                  };
                  console.log(`Updated content in message ${msg.id}:`, updated);
                  return updated;
                }
                return gc;
              });

              return {
                ...msg,
                generatedContents: updatedContents
              };
            }));

            // If this was an inline generation, clear the states
            if (contentId === imageGenerationContentId) {
              if (content.status === "complete") {
                setImageGenerationContentId(null);
                setGeneratingImageForMessage(null);
                setImageGenerationError(null);
              } else if (content.status === "failed") {
                setImageGenerationError("Image generation failed. Please try again.");
                setImageGenerationContentId(null);
                setGeneratingImageForMessage(null);
              }
            }

            if (contentId === audioGenerationContentId) {
              if (content.status === "complete") {
                setAudioGenerationContentId(null);
                setGeneratingAudioForMessage(null);
                setAudioGenerationError(null);
              } else if (content.status === "failed") {
                setAudioGenerationError("Audio generation failed. Please try again.");
                setAudioGenerationContentId(null);
                setGeneratingAudioForMessage(null);
              }
            }

            if (contentId === videoGenerationContentId) {
              if (content.status === "complete") {
                setVideoGenerationContentId(null);
                setGeneratingVideoForMessage(null);
                setVideoGenerationError(null);
              } else if (content.status === "failed") {
                setVideoGenerationError("Video generation failed. Please try again.");
                setVideoGenerationContentId(null);
                setGeneratingVideoForMessage(null);
              }
            }
          }
        } catch (err) {
          console.error(`Error polling content ${contentId}:`, err);

          // Only show error for inline generation
          if (contentId === imageGenerationContentId) {
            setImageGenerationError(err instanceof Error ? err.message : "Failed to check content status");
            setImageGenerationContentId(null);
            setGeneratingImageForMessage(null);
          }
        }
      });

      await Promise.allSettled(pollPromises);
    };

    // Set up polling interval (3 seconds for all content)
    const interval = setInterval(pollContentGenerations, 3000);

    // Cleanup
    return () => clearInterval(interval);
  }, [
    imageGenerationContentId, generatingImageForMessage,
    audioGenerationContentId, generatingAudioForMessage,
    videoGenerationContentId, generatingVideoForMessage
  ]);

  const loadConversationData = useCallback(async () => {
    if (conversationId) {
      // Don't reload if we already have this conversation's data
      if (conversationDetail?.conversation.id === conversationId && messages.length > 0) {
        return;
      }
      setIsLoadingConversation(true);
      try {
        const response = await chatAPI.getConversation(conversationId);
        setConversationDetail(response);
        setTitle(response.conversation.title || "Untitled Conversation");

        // Convert API messages to local message format with generated content
        const convertedMessages: Message[] = response.messages.map((msg: APIMessage) => {
          // Check if this message has associated content generations
          // Get all content generations for this message
          const contentGenerations = response.content_generations?.filter(
            cg => cg.message_id === msg.id
          ) || [];

          // Map all content generations
          const generatedContents = contentGenerations.map(cg => ({
            id: cg.id,
            type: cg.content_type,
            url: cg.content_url ? getFullStorageUrl(cg.content_url) : undefined,
            status: cg.status,
            transcript: cg.transcript
          }));

          return {
            id: msg.id,
            content: msg.content,
            isUser: msg.role.toLowerCase() === 'user',
            citations: msg.citations || [],
            ...(generatedContents.length > 0 && { generatedContents })
          };
        });

        setMessages(convertedMessages);

        // Extract follow-up questions from the latest assistant message that has them
        const latestAssistantMessageWithQuestions = response.messages
          .filter((msg: APIMessage) => msg.role.toLowerCase() === 'assistant' && msg.follow_up_questions?.questions?.length)
          .pop();

        if (latestAssistantMessageWithQuestions?.follow_up_questions?.questions) {
          setQuestions(latestAssistantMessageWithQuestions.follow_up_questions.questions);
        }
      } catch (error) {
        console.error("Failed to load conversation:", error);
      } finally {
        setIsLoadingConversation(false);
      }
    }
  }, [conversationId, conversationDetail, messages.length]);

  useEffect(() => {
    loadConversationData();
  }, [loadConversationData]);

  const handleSendMessage = useCallback(async (message: string) => {
    if (isBusy || sendingRef.current) return;
    if (!message.trim()) return;

    sendingRef.current = true;
    setIsThinking(true);

    try {
      let currentConversationId = conversationId;
      const command = message.trim().toLowerCase();

      // Check for generation commands
      if (['image', 'audio', 'video'].includes(command)) {
        const latestAssistantMessage = messages.filter(msg => !msg.isUser).pop();
        if (latestAssistantMessage) {
          setCurrentInput("");
          if (command === 'image') {
            handleGenerateImage(latestAssistantMessage.id);
          } else if (command === 'audio') {
            handleGenerateAudio(latestAssistantMessage.id);
          } else if (command === 'video') {
            handleGenerateVideo(latestAssistantMessage.id);
          }
          return; // Exit handleSendMessage
        }
      }

      if (!currentConversationId) {
        if (!checkQuota('chat')) return;

        try {
          const newConversation = await chatAPI.createConversation({ messages: [] });
          currentConversationId = newConversation.id;

          // Update URL and trigger router update
          navigate(`/chat/${newConversation.id}`, { replace: true });

          // Update local state to ensure header and other components see the CID immediately
          setTitle("New Conversation");
          setConversationDetail({
            conversation: newConversation,
            messages: [],
            content_generations: []
          });

          // Notify sidebar to refresh
          window.dispatchEvent(new CustomEvent('refresh-conversations'));
        } catch (error) {
          console.error("Failed to create conversation:", error);
          // Show error to user
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            content: "Failed to start conversation. Please try again.",
            isUser: false,
          }]);
          return;
        }
      }

      const userMessage: Message = {
        id: Date.now().toString(),
        content: message,
        isUser: true,
      };

      setMessages(prev => [...prev, userMessage]);
      setCurrentInput("");
      setIsThinking(true);

      // Create a placeholder AI message for streaming
      const aiMessageId = `ai-${Date.now()}`;
      const aiMessage: Message = {
        id: aiMessageId,
        content: "",
        isUser: false,
        citations: [],
      };

      setMessages(prev => [...prev, aiMessage]);
      setIsThinking(false);
      setIsStreaming(true);

      try {
        const response = await chatAPI.chatCompletion(
          currentConversationId!,
          {
            message: message,
            stream: true,
            mock: false,
          },
          (streamingContent: string) => {
            setMessages(prev => prev.map(msg =>
              msg.id === aiMessageId
                ? { ...msg, content: streamingContent }
                : msg
            ));
          }
        );

        setIsStreaming(false);

        // Update with complete response and check for content generations
        const updatedMessage = {
          id: response.message_id || aiMessageId,
          content: response.message,
          isUser: false,
          citations: response.citations || [],
        };

        setMessages(prev => prev.map(msg =>
          msg.id === aiMessageId ? updatedMessage : msg
        ));

        // Store questions for explore more functionality
        if (response.questions && response.questions.length > 0) {
          setQuestions(response.questions);
        }

        // Update conversation title if it was generated
        const currentTitle = title || conversationDetail?.conversation.title;
        const isDefaultTitle = !currentTitle || currentTitle === "New Conversation" || currentTitle === "Untitled Conversation";

        if (response.title && isDefaultTitle) {
          setTitle(response.title);
          if (conversationDetail) {
            setConversationDetail({
              ...conversationDetail,
              conversation: { ...conversationDetail.conversation, title: response.title }
            });
          }
          // Notify sidebar
          window.dispatchEvent(new CustomEvent('refresh-conversations'));
        }

        // Note: We don't reload conversation data here to avoid unnecessary page refreshes
        // The conversation will reload when:
        // 1. User navigates to a different conversation
        // 2. Image generation completes (handled by polling hook)
        // 3. User manually refreshes the page

        // Refresh usage stats
        refreshUsage();

        // Auto-update title if it's a new conversation or default title
        if (isDefaultTitle && currentConversationId) {
          try {
            // Small delay to ensure DB is updated with messages
            setTimeout(async () => {
              // chatAPI.getConversation(conversationId)

              try {
                const updatedConversation = await chatAPI.getConversation(currentConversationId!);

                if (updatedConversation.conversation.title) {
                  setTitle(updatedConversation.conversation.title);
                  if (conversationDetail) {
                    setConversationDetail({
                      ...conversationDetail,
                      conversation: { ...conversationDetail.conversation, title: updatedConversation.conversation.title }
                    });
                  }
                  // Notify sidebar
                  window.dispatchEvent(new CustomEvent('refresh-conversations'));
                }
              } catch (titleError) {
                console.error("Failed to auto-generate title:", titleError);
              }
            }, 500);
          } catch (e) {
            console.error("Title generation timer error:", e);
          }
        }

      } catch (error) {
        console.error("Failed to send message:", error);
        setIsThinking(false);
        setIsStreaming(false);

        let errorMessage = "Sorry, I encountered an error while processing your message. Please try again.";

        if (error instanceof Error) {
          if (error.message === 'QUOTA_EXCEEDED') {
            errorMessage = "You've reached your plan limit. Please upgrade to continue chatting.";
            setShowPlansModal(true);
          } else if (error.message.includes('Network')) {
            errorMessage = "Network error. Please check your connection and try again.";
          } else if (error.message.includes('401')) {
            errorMessage = "Authentication error. Please sign in again.";
          } else if (error.message.includes('timeout')) {
            errorMessage = "Request timed out. Please try again.";
          }
        }

        setMessages(prev => prev.map(msg =>
          msg.id === aiMessageId
            ? { ...msg, content: errorMessage }
            : msg
        ));
      }
    } finally {
      sendingRef.current = false;
      setIsThinking(false);
    }
  }, [conversationId, messages, isBusy, navigate, checkQuota, refreshUsage, loadConversationData, conversationDetail]);

  useEffect(() => {
    const initialQuery = location.state?.initialQuery;
    // Handle initial query even if no conversation ID yet
    if (initialQuery && !hasProcessedInitialQuery && !isLoadingConversation) {
      setHasProcessedInitialQuery(true);
      if (initialQuery.trim()) {
        setCurrentInput(initialQuery.trim());
        // Auto-focus the input with the initial query
        setTimeout(() => {
          inputRef.current?.focus();
        }, 100);
      }
      // Clear state but don't replace URL yet if we are on /chat
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [conversationId, location.state?.initialQuery, hasProcessedInitialQuery, isLoadingConversation, location.pathname, navigate]);

  const handleTitleSave = async () => {
    if (conversationId && title.trim() !== (conversationDetail?.conversation.title || "")) {
      try {
        await chatAPI.updateConversationTitle(conversationId, title.trim());
        if (conversationDetail) {
          setConversationDetail({
            ...conversationDetail,
            conversation: { ...conversationDetail.conversation, title: title.trim() }
          });
        }
        // Notify sidebar
        window.dispatchEvent(new CustomEvent('refresh-conversations'));
      } catch (error) {
        console.error("Failed to update title:", error);
        setTitle(conversationDetail?.conversation.title || "Untitled Conversation");
      }
    }
    setIsEditingTitle(false);
  };

  const handleMicClick = () => {
    setIsRecording(!isRecording);
    if (!isRecording) {
      setTimeout(() => {
        setCurrentInput("How can I practice mindfulness in daily life?");
        setIsRecording(false);
      }, 2000);
    }
  };

  const handleExploreMore = () => {
    setShowMeditationCreator(false);
    setShowExploreMore(!showExploreMore);
  };

  const handleMeditationGuide = () => {
    setShowExploreMore(false);
    setShowMeditationCreator(!showMeditationCreator);
  };

  // Inline image generation handler
  const handleGenerateImage = async (messageId: string) => {
    if (isBusy) {
      toast.error("Please wait for the current process to finish.");
      return;
    }
    // If no conversation ID (shouldn't happen if message exists), we can't generate
    if (!conversationId || !messageId) {
      setImageGenerationError("Missing conversation or message information");
      return;
    }
    console.log(usage);

    // Validation for Image Cards
    // Check remaining cards
    // Handle potential string vs number just in case, though schema says number
    if (!checkQuota('image')) return;

    setGeneratingImageForMessage(messageId);
    setImageGenerationError(null);

    try {
      const response = await contentAPI.createContent({
        conversation_id: conversationId,
        message_id: messageId,
        mode: "image"
      });

      // Immediately add the pending content to the message
      setMessages(prev => prev.map(msg => {
        if (msg.id === messageId) {
          const existingContents = msg.generatedContents || [];
          return {
            ...msg,
            generatedContents: [
              ...existingContents,
              {
                id: response.id,
                type: 'image' as const,
                status: 'pending' as const,
                url: undefined,
                transcript: null
              }
            ]
          };
        }
        return msg;
      }))

        ;

      console.log(`Started image generation with contentId: ${response.id} for message: ${messageId}`);
      setImageGenerationContentId(response.id);
      refreshUsage();
      // Polling will start automatically via the useEffect hook
    } catch (error) {
      console.error("Failed to initiate image generation:", error);
      if (error instanceof Error && error.message === 'QUOTA_EXCEEDED') {
        setImageGenerationError("You've reached your contemplation card limit. Please upgrade your plan.");
        setShowPlansModal(true);
      } else {
        setImageGenerationError(error instanceof Error ? error.message : "Failed to start image generation");
      }
      setGeneratingImageForMessage(null);
    }
  };

  const handleGenerateAudio = async (messageId: string, length?: string) => {
    if (isBusy) {
      console.log('Content generation already in progress');
      return;
    }

    if (!conversationId || !messageId) {
      setAudioGenerationError("Missing conversation or message information");
      return;
    }

    if (!checkQuota('audio')) return;

    setGeneratingAudioForMessage(messageId);
    setAudioGenerationError(null);

    try {
      const response = await contentAPI.createContent({
        conversation_id: conversationId,
        message_id: messageId,
        mode: "audio",
        length: length // Pass the length parameter
      });

      setMessages(prev => prev.map(msg => {
        if (msg.id === messageId) {
          const existingContents = msg.generatedContents || [];
          return {
            ...msg,
            generatedContents: [
              ...existingContents,
              {
                id: response.id,
                type: 'audio' as const,
                status: 'pending' as const,
                url: undefined,
                transcript: null
              }
            ]
          };
        }
        return msg;
      }));

      console.log(`Started audio generation with contentId: ${response.id} for message: ${messageId}`);
      setAudioGenerationContentId(response.id);
      refreshUsage();
    } catch (error) {
      console.error("Failed to initiate audio generation:", error);
      if (error instanceof Error && error.message === 'QUOTA_EXCEEDED') {
        setAudioGenerationError("You've reached your free meditation limit. Please upgrade your plan.");
        setShowPlansModal(true);
      } else {
        setAudioGenerationError(error instanceof Error ? error.message : "Failed to start audio generation");
      }
      setGeneratingAudioForMessage(null);
    }
  };

  const handleGenerateVideo = async (messageId: string, length?: string) => {
    if (isBusy) {
      console.log('Content generation already in progress');
      return;
    }

    if (!conversationId || !messageId) {
      setVideoGenerationError("Missing conversation or message information");
      return;
    }

    if (!checkQuota('video')) return;

    setGeneratingVideoForMessage(messageId);
    setVideoGenerationError(null);

    try {
      const response = await contentAPI.createContent({
        conversation_id: conversationId,
        message_id: messageId,
        mode: "video",
        length: length // Pass the length parameter
      });

      setMessages(prev => prev.map(msg => {
        if (msg.id === messageId) {
          const existingContents = msg.generatedContents || [];
          return {
            ...msg,
            generatedContents: [
              ...existingContents,
              {
                id: response.id,
                type: 'video' as const,
                status: 'pending' as const,
                url: undefined,
                transcript: null
              }
            ]
          };
        }
        return msg;
      }));

      console.log(`Started video generation with contentId: ${response.id} for message: ${messageId}`);
      setVideoGenerationContentId(response.id);
      refreshUsage();
    } catch (error) {
      console.error("Failed to initiate video generation:", error);
      if (error instanceof Error && error.message === 'QUOTA_EXCEEDED') {
        setVideoGenerationError("You've reached your free meditation limit. Please upgrade your plan.");
        setShowPlansModal(true);
      } else {
        setVideoGenerationError(error instanceof Error ? error.message : "Failed to start video generation");
      }
      setGeneratingVideoForMessage(null);
    }
  };

  const handleGenerateMeditation = (options: { mode: 'audio' | 'video', length: string }) => {
    const lastAssistantMessage = messages.filter(msg => !msg.isUser).pop();
    if (!lastAssistantMessage) return;

    if (options.mode === 'audio') {
      handleGenerateAudio(lastAssistantMessage.id, options.length);
    } else {
      handleGenerateVideo(lastAssistantMessage.id, options.length);
    }
  };

  const handleNewChat = () => {
    navigate("/chat");
  };

  const renderGeneratedContentThumbnail = (contents: Message['generatedContents'], messageId: string) => {
    if (!contents || contents.length === 0) return null;

    return (
      <div className="flex flex-col gap-4 mt-4">
        {contents.map((content) => {
          // Show loading state for pending/processing content
          if (content.status === 'pending' || content.status === 'processing') {
            if (content.type === 'image') {
              return (
                <div key={content.id} className="relative overflow-hidden rounded-lg bg-[#ECE5DF] aspect-[3/4] w-full max-w-[400px] h-[250px] flex items-center justify-center">
                  <div className="w-10 h-10 border-4 border-gray-300 border-t-gray-500 rounded-full animate-spin"></div>
                </div>
              );
            } else {
              const Icon = content.type === 'video' ? PlayIcon : MusicIcon;
              const label = content.type === 'video' ? 'Guided Meditation Video...' : 'Guided Meditation Audio...';
              return (
                <div key={content.id} className="flex items-center gap-3 p-4 bg-[#ECE5DF] rounded-lg border border-[#d05e2d]">
                  <div className="relative flex-shrink-0">
                    <Icon className="w-5 h-5 text-[#d05e2d] animate-pulse" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#472b20] animate-pulse">{label}</p>
                    <p className="text-xs text-gray-500 mt-1 animate-pulse">This may take a few moments</p>
                  </div>
                </div>
              );
            }
          }

          // Show error state for failed content
          if (content.status === 'failed') {
            return (
              <div key={content.id} className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-600">Failed to generate {content.type}. Please try again.</p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 text-xs h-7"
                  onClick={() => {
                    if (content.type === 'image') handleGenerateImage(messageId);
                    else if (content.type === 'audio') handleGenerateAudio(messageId);
                    else if (content.type === 'video') handleGenerateVideo(messageId);
                  }}
                  disabled={isBusy}
                >
                  Try Again
                </Button>
              </div>
            );
          }

          if (content.status !== 'complete' || !content.url) return null;

          switch (content.type) {
            case 'image':
              return (
                <div key={content.id} className="group relative inline-block max-w-[400px]">
                  <img
                    src={content.url}
                    alt="Generated image"
                    className="rounded-lg  max-w-full h-auto"
                    style={{ maxWidth: '100%', height: 'auto' }}
                  />
                  <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="bg-black/50 hover:bg-black/70 text-white rounded-full h-9 w-9 p-0 backdrop-blur-sm"
                      onClick={async () => {
                        try {
                          const response = await fetch(content.url!);
                          const blob = await response.blob();
                          const url = window.URL.createObjectURL(blob);
                          const link = document.createElement('a');
                          link.download = 'contemplation-card.png';
                          link.href = url;
                          link.click();
                          window.URL.revokeObjectURL(url);
                        } catch (error) {
                          console.error("Failed to download image:", error);
                        }
                      }}
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              );

            case 'audio':
              return (
                <InlineMediaPlayer
                  key={content.id}
                  url={content.url}
                  type="audio"
                  transcript={content.transcript}
                />
              );

            case 'video':
              return (
                <InlineMediaPlayer
                  key={content.id}
                  url={content.url}
                  type="video"
                  transcript={content.transcript}
                  onOpen={() => {
                    if (content.url) {
                      setSelectedMedia({ url: content.url, type: 'video' });
                      setShowMeditationCreator(true);
                    }
                  }}
                />
              );

            default:
              return null;
          }
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col flex-1 bg-[#F5F0EC] relative h-full overflow-y-auto">
      {/* Header - Minimal for Title - Only show when there's a conversation ID */}
      {conversationId && !isLoadingConversation && (
        <div className="sticky top-0 h-14 px-2 md:px-4 flex items-center justify-between border-b border-[#ECE5DF] bg-[#F5F0EC]/80 backdrop-blur-xl z-30 shrink-0">
          <div className="flex items-center md:hidden">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/")}
              className="text-[#472B20]"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </div>

          <div className="flex-1 flex justify-center">
            {isEditingTitle ? (
              <div className="flex items-center gap-2 max-w-full px-4">
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="text-sm font-medium text-gray-900 h-8 px-2 py-1 bg-transparent text-center min-w-[150px] md:min-w-[200px]"
                  autoFocus
                  onBlur={() => handleTitleSave()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleTitleSave();
                    }
                  }}
                />
                <Button
                  onClick={() => handleTitleSave()}
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-green-600 hover:bg-green-50 rounded-full"
                >
                  <Save className="w-3.5 h-3.5" />
                </Button>
              </div>
            ) : (
              <button
                className="flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg hover:bg-[#ECE5DF] transition-colors group max-w-full"
                onClick={() => setIsEditingTitle(true)}
              >
                <h1 className="text-sm font-medium text-gray-700 truncate max-w-[200px] md:max-w-[300px]">
                  {title}
                </h1>
                <Pencil className="w-3 h-3 text-gray-400 group-hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-all shrink-0" />
              </button>
            )}
          </div>

          {/* Spacer for mobile to keep title centered */}
          <div className="w-10 md:hidden" />
        </div>
      )}


      {/* Loading State - Centered in full viewport */}
      {isLoadingConversation && (
        <div className="absolute inset-0 flex items-center justify-center z-40">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-button mx-auto mb-4"></div>
            <p className="text-brand-button">Loading conversation...</p>
          </div>
        </div>
      )}

      {/* Messages Container */}
      <div className="flex-1 p-4 md:p-6 max-w-[816px] mx-auto w-full">

        {!isLoadingConversation && messages.length === 0 && (
          <div className="flex flex-col items-center w-full max-w-2xl mx-auto px-4 pt-8 pb-4">
            {/* Heading */}
            <h1 className="text-3xl md:text-4xl font-heading font-bold text-gray-800 mb-1 text-center">
              Arunachala Samudra
            </h1>
            <p className="text-gray-500 mb-6 text-sm md:text-base text-center">
              Ask anything about Ramana Maharshi's teachings, or choose a topic below
            </p>

            {/* Tabs + chips */}
            <div className="w-full">
              <div className="flex border-b border-gray-200 mb-4">
                <button
                  onClick={() => setTopicTab("teachings")}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    topicTab === "teachings"
                      ? "border-orange-500 text-orange-600"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  Ramana's Teachings
                </button>
                <button
                  onClick={() => setTopicTab("personal")}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    topicTab === "personal"
                      ? "border-orange-500 text-orange-600"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  What I'm Facing
                </button>
              </div>

              {/* Topic chips */}
              <div className="flex flex-wrap gap-2">
                {(topicTab === "teachings" ? teachingTopics : personalTopics).map((topic, i) => (
                  <button
                    key={i}
                    onClick={() => handleSendMessage(topic.question)}
                    className="px-3 py-1.5 text-sm rounded-full border border-orange-200 bg-orange-50 text-orange-800 hover:bg-orange-100 hover:border-orange-400 hover:shadow-sm transition-all duration-150"
                  >
                    {topic.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {!isLoadingConversation && messages.length > 0 && messages.map((message, index) => {
          const latestAssistantMessageIndex = messages.map((msg, idx) => ({ msg, idx }))
            .filter(({ msg }) => !msg.isUser)
            .pop()?.idx;

          return (
            <div key={message.id} className="mb-4 md:mb-6">
              <ChatMessage
                message={message}
                isStreaming={isStreaming && !message.isUser && index === messages.length - 1}
                showFeedback={!message.isUser && index === latestAssistantMessageIndex && !isStreaming}
              />

              {/* Show generated content thumbnail inline */}
              {!message.isUser && message.generatedContents && renderGeneratedContentThumbnail(message.generatedContents, message.id)}

              {/* Quick action buttons after the last assistant message */}
              {/* {!message.isUser && index === latestAssistantMessageIndex && (
                <div className="flex flex-wrap gap-2 mt-4 ml-12">
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full text-xs h-8"
                    onClick={() => handleGenerateImage(message.id)}
                    disabled={!!generatingImageForMessage}
                  >
                    <ImageIcon className="w-3 h-3 mr-1" />
                    Generate Image
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-full text-xs h-8"
                    onClick={handleMeditationGuide}
                  >
                    <Music className="w-3 h-3 mr-1" />
                    Create Meditation
                  </Button>
                </div>
              )} */}
            </div>
          );
        })}
        {/* 
        {isThinking && (
          <div className="mb-6 ml-12">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
              thinking...
            </div>
          </div>
        )} */}

        <div ref={messagesEndRef} />
        {/* Inline Explore More */}
        <ExploreMore
          isOpen={showExploreMore}
          questions={questions}
          onClose={() => setShowExploreMore(false)}
          onSelectQuestion={(q) => {
            setCurrentInput(q);
            setShowExploreMore(false);
            setTimeout(() => inputRef.current?.focus(), 100);
          }}
          inline={true}
        />
      </div>

      {/* Input Area - Fixed at bottom */}
      {!isLoadingConversation && (
        <div className="sticky bottom-0 bg-[#F5F0EC]/80 backdrop-blur-xl border-t border-[#ECE5DF] px-3 md:px-4 pt-4 md:pt-4 pb-4 md:pb-[10px] z-20 shrink-0">
          <div className="max-w-[816px] mx-auto">


            {/* Topic picker panel — slides in above input when toggled */}
            {messages.length > 0 && showTopicPicker && (
              <div className="mb-3 bg-white border border-orange-100 rounded-xl shadow-md overflow-hidden">
                {/* Panel header */}
                <div className="flex items-center justify-between px-3 pt-2.5 pb-1">
                  <div className="flex gap-0">
                    <button
                      onClick={() => setTopicTab("teachings")}
                      className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                        topicTab === "teachings"
                          ? "bg-orange-100 text-orange-700"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      Ramana's Teachings
                    </button>
                    <button
                      onClick={() => setTopicTab("personal")}
                      className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                        topicTab === "personal"
                          ? "bg-orange-100 text-orange-700"
                          : "text-gray-500 hover:text-gray-700"
                      }`}
                    >
                      What I'm Facing
                    </button>
                  </div>
                  <button onClick={() => setShowTopicPicker(false)} className="text-gray-400 hover:text-gray-600 p-1">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                {/* Chips */}
                <div className="px-3 pb-3 max-h-40 overflow-y-auto">
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {(topicTab === "teachings" ? teachingTopics : personalTopics).map((topic, i) => (
                      <button
                        key={i}
                        onClick={() => { handleSendMessage(topic.question); setShowTopicPicker(false); }}
                        className="px-2.5 py-1 text-xs rounded-full border border-orange-200 bg-orange-50 text-orange-800 hover:bg-orange-100 hover:border-orange-400 transition-all duration-150"
                      >
                        {topic.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons - Only show when there are messages */}
            {messages.length > 0 && (
              <div className="flex flex-nowrap md:flex-wrap gap-2 mb-3 md:mb-4 justify-start md:justify-center overflow-x-auto pb-2 md:pb-0 scrollbar-hide no-scrollbar">
                <Button
                  onClick={() => setShowTopicPicker(v => !v)}
                  variant="outline"
                  size="sm"
                  className={`rounded-full h-8 md:h-9 whitespace-nowrap px-3 text-xs md:text-sm ${showTopicPicker ? "bg-orange-50 border-orange-300 text-orange-700" : ""}`}
                >
                  <LayoutGrid className="w-3 md:w-3.5 h-3 md:h-3.5 mr-1 md:mr-1.5" />
                  Topics
                </Button>
                <Button
                  onClick={handleExploreMore}
                  disabled={isBusy}
                  variant="outline"
                  size="sm"
                  className="rounded-full h-8 md:h-9 whitespace-nowrap px-3 text-xs md:text-sm"
                >
                  Explore More
                </Button>
                <Button
                  onClick={() => {
                    const lastAssistantMessage = messages.filter(msg => !msg.isUser).pop();
                    if (lastAssistantMessage) {
                      handleGenerateImage(lastAssistantMessage.id);
                    }
                  }}
                  disabled={isBusy}
                  variant="outline"
                  size="sm"
                  className="rounded-full h-8 md:h-9 whitespace-nowrap px-3 text-xs md:text-sm"
                >
                  <ImageIcon className="w-3 md:w-3.5 h-3 md:h-3.5 mr-1 md:mr-1.5" />
                  Image
                </Button>
                <Button
                  onClick={handleMeditationGuide}
                  disabled={isBusy}
                  variant="outline"
                  size="sm"
                  className="rounded-full h-8 md:h-9 whitespace-nowrap px-3 text-xs md:text-sm"
                >
                  <Music className="w-3 md:w-3.5 h-3 md:h-3.5 mr-1 md:mr-1.5" />
                  Meditation
                </Button>
              </div>
            )}

            {/* Input with mic button — or upgrade CTA when quota exhausted */}
            {(() => {
              const chatRemaining = usage?.conversations?.remaining;
              const chatExhausted = typeof chatRemaining === 'number' && chatRemaining <= 0;
              if (chatExhausted) {
                return (
                  <div className="max-w-2xl mx-auto w-full">
                    <div className="flex flex-col items-center gap-3 py-4 px-5 rounded-xl bg-[#FDF4EF] border border-[#ECE5DF]">
                      <p className="text-sm text-[#472b20]/70 text-center">
                        You've used all <span className="font-semibold text-[#472b20]">10 free conversations</span>. Upgrade to keep the inquiry going.
                      </p>
                      <button
                        onClick={() => setShowPlansModal(true)}
                        className="px-5 py-2 rounded-full bg-[#D05E2D] hover:bg-[#B84E20] text-white text-sm font-semibold transition-colors"
                      >
                        Upgrade plan →
                      </button>
                    </div>
                    <p className="text-center text-[10px] md:text-xs text-gray-400 mt-2 md:mt-3">
                      Mindful AI can make mistakes. Consider checking important information.
                    </p>
                  </div>
                );
              }
              return (
                <div className="relative max-w-2xl mx-auto">
                  <Input
                    ref={inputRef}
                    value={currentInput}
                    onChange={(e) => setCurrentInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendMessage(currentInput)}
                    placeholder="Ask anything"
                    className="flex-1 bg-white border-0 h-12 md:h-11 text-sm md:text-base rounded-[10px] md:rounded-[12px] px-4 md:px-6 focus-visible:ring-brand-button focus-visible:ring-1"
                    disabled={isBusy}
                  />
                  <div className="absolute right-1.5 md:right-2 top-1/2 transform -translate-y-1/2 flex gap-1.5 md:gap-2">
                    <Button
                      onClick={() => handleSendMessage(currentInput)}
                      disabled={!currentInput.trim() || isBusy}
                      className={`rounded-full w-8 h-8 md:w-10 md:h-10 ${isBusy ? 'bg-gray-300' : 'bg-brand-button hover:bg-brand-button/90'} text-white transition-colors p-0`}
                    >
                      <ArrowRight className="w-4 h-4 md:w-5 md:h-5" />
                    </Button>
                  </div>
                  <p className="text-center text-[10px] md:text-xs text-gray-500 mt-2 md:mt-3">
                    Mindful AI can make mistakes. Consider checking important information.
                  </p>
                </div>
              );
            })()}
          </div>
        </div>
      )}


      <InlineMeditationCreator
        isOpen={showMeditationCreator}
        onClose={() => {
          setShowMeditationCreator(false);
          setSelectedMedia(null);
        }}
        conversationId={conversationId}
        messageId={messages[messages.length - 1]?.id}
        existingContentGenerations={
          conversationDetail?.content_generations?.filter(cg => cg.status === 'complete') || []
        }
        initialContent={selectedMedia}
        onGenerate={handleGenerateMeditation}
      />
    </div>
  );
};
export default Chat;