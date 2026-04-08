import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Download, Volume2, Video, Eye } from "lucide-react";
import BaseModal from "./BaseModal";
import { contentAPI } from "@/apis/api";
import { getFullStorageUrl } from "@/lib/storage";
import type { ContentGeneration } from "@/apis/wire";
import { useUsage } from "@/contexts/UsageContext";

interface InlineMeditationCreatorProps {
  isOpen: boolean;
  onClose: () => void;
  conversationId?: string;
  messageId?: string;
  existingContentGenerations?: ContentGeneration[];
  initialContent?: {
    url: string;
    type: 'audio' | 'video';
  } | null;
  initialMode?: 'audio' | 'video';
  onGenerate?: (options: { mode: 'audio' | 'video', length: string }) => void;
}

// Custom hook for polling content status
const useContentPolling = (contentId: string | null, shouldPoll: boolean) => {
  const [status, setStatus] = useState<'pending' | 'processing' | 'complete' | 'failed' | null>(null);
  const [contentUrl, setContentUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollContent = useCallback(async () => {
    if (!contentId) return;

    try {
      const content = await contentAPI.getContent(contentId);
      setStatus(content.status);
      console.log("meditation content", content);
      console.log("meditation content.status", content.status);

      if (content.status === "complete" && content.content_url) {
        // Use the full storage URL
        setContentUrl(getFullStorageUrl(content.content_url));
      } else if (content.status === "failed") {
        setError("Meditation guide generation failed");
      }
    } catch (err) {
      console.error("Error polling meditation content:", err);
      setError(err instanceof Error ? err.message : "Failed to check meditation guide status");
    }
  }, [contentId]);

  useEffect(() => {
    if (!shouldPoll || !contentId) return;

    // Initial poll
    pollContent();

    // Set up polling interval
    const interval = setInterval(() => {
      pollContent();
    }, 2000);

    // Cleanup
    return () => clearInterval(interval);
  }, [shouldPoll, contentId, pollContent]);

  // Stop polling when complete or failed
  useEffect(() => {
    if (status === 'complete' || status === 'failed') {
      // Polling will stop naturally due to shouldPoll dependency
    }
  }, [status]);

  return { status, contentUrl, error };
};

const InlineMeditationCreator = ({
  isOpen,
  onClose,
  conversationId,
  messageId,
  existingContentGenerations = [],
  initialContent,
  initialMode,
  onGenerate
}: InlineMeditationCreatorProps) => {
  const [selectedLength, setSelectedLength] = useState("5 min");
  const [selectedFormat, setSelectedFormat] = useState("Audio");
  const [fullScreen, setFullScreen] = useState(false);
  const [contentId, setContentId] = useState<string | null>(null);
  const [isInitiating, setIsInitiating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentContentUrl, setCurrentContentUrl] = useState<string | null>(null);
  const [currentContentType, setCurrentContentType] = useState<'audio' | 'video' | null>(null);

  // const lengths = ["5 min", "10 min", "15 min", "20 min"];
  const { usage } = useUsage();

  const lengths = ["5 min", "10 min", "15 min", "20 min"];

  // Standard formats
  const formats = ["Audio", "Video"];

  // Helper to check if format is enabled
  const isFormatEnabled = (format: string) => {
    if (!usage) return true; // Default to enabled if loading
    if (format === "Audio") return usage.audio_enabled;
    if (format === "Video") return usage.video_enabled;
    return true;
  };

  // Helper to check if length is allowed
  const isLengthEnabled = (lengthStr: string) => {
    if (!usage) return true;
    const minutes = parseInt(lengthStr);
    if (isNaN(minutes)) return true;
    const totalRemaining = usage.meditation_duration.remaining + (usage.addon_minutes?.remaining || 0);
    return minutes <= totalRemaining;
  };

  // Auto-select valid format if current selection is disabled
  useEffect(() => {
    if (selectedFormat === "Video" && usage && !usage.video_enabled) {
      setSelectedFormat("Audio");
    }
    // If audio is also disabled, we might have a problem, but usually audio is base
  }, [usage, selectedFormat]);

  // Auto-select valid length if current selection is disabled
  useEffect(() => {
    if (!isLengthEnabled(selectedLength)) {
      // Find first enabled length
      const validLength = lengths.find(l => isLengthEnabled(l));
      if (validLength) {
        setSelectedLength(validLength);
      }
    }
  }, [usage, selectedLength]);

  // Use polling hook - stop polling when in fullscreen
  const shouldPoll = !!(contentId && !fullScreen);
  const { status, contentUrl, error: pollingError } = useContentPolling(contentId, shouldPoll);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setFullScreen(false);
      setContentId(null);
      setCurrentContentUrl(null);
      setCurrentContentType(null);
      setIsInitiating(false);
      setError(null);
      setSelectedLength("10 min");
      setSelectedFormat("Audio");
    } else if (initialContent) {
      // If initialContent is provided, go straight to full screen
      setFullScreen(true);
      setCurrentContentUrl(initialContent.url);
      setCurrentContentType(initialContent.type);
    } else if (initialMode) {
      // Pre-select format based on which button the user clicked
      setSelectedFormat(initialMode === 'video' ? 'Video' : 'Audio');
    }
  }, [isOpen, initialContent, initialMode]);

  // Handle when content is complete
  useEffect(() => {
    if (status === 'complete' && contentUrl) {
      // Reset generation state to show the new content in thumbnails
      setContentId(null);
      setCurrentContentUrl(null);
      setCurrentContentType(null);
      setIsInitiating(false);
      setError(null);
    }
  }, [status, contentUrl]);

  // Combine errors from initiation and polling
  const displayError = error || pollingError;

  const handleGenerateGuide = async () => {
    if (!conversationId || !messageId) {
      setError("Missing conversation or message information");
      return;
    }

    if (onGenerate) {
      onGenerate({
        mode: selectedFormat.toLowerCase() as 'audio' | 'video',
        length: selectedLength
      });
      onClose();
      return;
    }

    // Fallback to internal generation if no callback provided (legacy behavior)
    setIsInitiating(true);
    setError(null);

    try {
      // Start content generation
      const response = await contentAPI.createContent({
        conversation_id: conversationId,
        message_id: messageId,
        mode: selectedFormat.toLowerCase() as 'audio' | 'video',
        length: selectedLength, // Pass the selected length (e.g., "5 min")
      });

      setContentId(response.id);
      // Polling will start automatically via the hook
    } catch (error) {
      console.error("Failed to initiate meditation guide generation:", error);
      setError(error instanceof Error ? error.message : "Failed to start meditation guide generation");
    } finally {
      setIsInitiating(false);
    }
  };

  const handleDownload = async (downloadUrl?: string) => {
    const urlToDownload = downloadUrl || contentUrl;
    if (!urlToDownload) return;

    try {
      const response = await fetch(urlToDownload);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.download = `meditation-guide.${currentContentType === 'audio' ? 'mp3' : 'mp4'}`;
      link.href = url;
      link.click();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download meditation guide:", error);
    }
  };

  const handleViewGuide = (guide: ContentGeneration) => {
    if (guide.status === 'complete' && guide.content_url) {
      setFullScreen(true);
      setCurrentContentUrl(getFullStorageUrl(guide.content_url));
      setCurrentContentType(guide.content_type as 'audio' | 'video');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Determine if we're in a loading state
  const isLoading = isInitiating || (contentId && status !== 'complete' && status !== 'failed');

  // Full screen view with generated content
  const displayUrl = currentContentUrl || contentUrl;
  const FullScreenView = () => {
    if (!fullScreen || !displayUrl) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50">
        <div className="relative w-full h-full flex items-center justify-center">
          <div className="absolute top-4 right-4 flex gap-2">
            <Button
              onClick={() => handleDownload(displayUrl)}
              variant="ghost"
              size="sm"
              className="text-white rounded-full bg-black bg-opacity-20 hover:bg-opacity-30"
            >
              <Download className="w-6 h-6" />
            </Button>
            <Button
              onClick={() => {
                if (initialContent) {
                  onClose();
                } else {
                  setFullScreen(false);
                  setCurrentContentUrl(null);
                  setCurrentContentType(null);
                  setError(null);
                }
              }}
              variant="ghost"
              size="sm"
              className="text-white rounded-full bg-black bg-opacity-20 hover:bg-opacity-30"
            >
              ×
            </Button>
          </div>

          {currentContentType === 'video' ? (
            <video
              src={displayUrl}
              controls
              className="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
              preload="metadata"
            >
              Your browser does not support the video tag.
            </video>
          ) : (
            <div className="max-w-2xl w-full bg-gradient-to-br from-blue-400 to-purple-600 rounded-lg shadow-2xl p-8">
              <div className="text-white text-center">
                {/* <div className="text-6xl mb-6">🧘‍♀️</div> */}
                <p className="text-2xl mb-6">Guided Meditation</p>
                <audio
                  src={displayUrl}
                  controls
                  className="w-full"
                  preload="metadata"
                >
                  Your browser does not support the audio tag.
                </audio>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Loading animation component
  const LoadingAnimation = () => {
    const getLoadingMessage = () => {
      if (isInitiating) return "Starting generation...";
      if (status === 'pending') return "Preparing your meditation...";
      if (status === 'processing') return "Creating your guided session...";
      return "Creating your meditation guide...";
    };

    return (
      <div className="flex flex-col items-center justify-center py-12 ">
        <div className="relative">
          {/* Outer rotating circle */}
          <div className="w-16 h-16 border-4 border-orange-200 rounded-full animate-spin border-t-brand-button"></div>
          {/* Inner pulsing circle */}
          <div className="absolute inset-2 w-12 h-12 bg-gradient-to-br from-orange-300 to-brand-button rounded-full animate-pulse"></div>
          {/* Center dot */}
          <div className="absolute inset-6 w-4 h-4 bg-white rounded-full"></div>
        </div>
        <p className="mt-4 text-brand-button text-lg font-medium">{getLoadingMessage()}</p>
        <p className="mt-2 text-brand-body text-sm">This may take a few moments (Please don't close the tab)</p>
      </div>
    );
  };

  // Filter for completed meditation guides (audio and video)
  const completedGuides = existingContentGenerations
    .filter(guide =>
      (guide.content_type === 'audio' || guide.content_type === 'video') &&
      guide.status === 'complete' &&
      guide.content_url
    )
    .map(guide => ({
      ...guide,
      fullUrl: getFullStorageUrl(guide.content_url)
    }));

  const modalContent = (
    <div>
      {displayError ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-red-500"></div>
          {displayError}
        </div>
      ) : null}

      {/* Existing Guides Thumbnails */}
      {/* {!isLoading && completedGuides.length > 0 && !initialContent && (
        <div className="mb-8">
          <p className="text-brand-body mb-4 font-medium">Your Generated Guides</p>
          <div className="grid grid-cols-2 gap-4">
            {completedGuides.map((guide) => (
              <div
                key={guide.id}
                className="relative group cursor-pointer border border-orange-100 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
                onClick={() => handleViewGuide(guide)}
              >
                <div className={`h-24 flex items-center justify-center ${guide.content_type === 'video' ? 'bg-purple-50' : 'bg-blue-50'
                  }`}>
                  {guide.content_type === 'video' ? (
                    <Video className="w-8 h-8 text-purple-400" />
                  ) : (
                    <Volume2 className="w-8 h-8 text-blue-400" />
                  )}
                </div>
                <div className="p-3 bg-white">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">{formatDate(guide.created_at)}</span>
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 uppercase">
                      {guide.content_type}
                    </span>
                  </div>
                </div>
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                  <Eye className="w-8 h-8 text-gray-700 drop-shadow-sm" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )} */}

      {/* Loading Animation - Show below thumbnails when generating */}
      {isLoading && <LoadingAnimation />}

      {/* Generate New Guide Section - Only show when not loading */}
      {!isLoading && !initialContent && (
        <div>
          <div className="mb-6">
            <p className="text-brand-body mb-4">Choose the length of guidance</p>
            <div className="grid grid-cols-2 gap-3">
              {lengths.map((length) => {
                const enabled = isLengthEnabled(length);
                return (
                  <Button
                    key={length}
                    onClick={() => enabled && setSelectedLength(length)}
                    disabled={!enabled}
                    variant={selectedLength === length ? "default" : "outline"}
                    className={`rounded-full ${selectedLength === length
                      ? "bg-brand-button hover:bg-brand-button/90 text-white"
                      : "border-orange-200 hover:border-brand-button"
                      } ${!enabled ? "opacity-50 cursor-not-allowed hover:bg-transparent hover:text-gray-500 hover:border-gray-200" : ""}`}
                  >
                    {length}
                  </Button>
                );
              })}
            </div>
          </div>

          {/* Format picker — hidden when the user clicked a specific Audio/Video button */}
          {!initialMode && (
            <div className="mb-6">
              <p className="text-brand-body mb-4">Choose the format that you want</p>
              <div className="grid grid-cols-2 items-center gap-3">
                {formats.map((format) => {
                  const enabled = isFormatEnabled(format);
                  return (
                    <Button
                      key={format}
                      onClick={() => enabled && setSelectedFormat(format)}
                      disabled={!enabled}
                      variant={selectedFormat === format ? "default" : "outline"}
                      className={`rounded-full ${selectedFormat === format
                        ? "bg-brand-button hover:bg-brand-button/90 text-white"
                        : "border-orange-200 hover:border-brand-button"
                        } ${!enabled ? "opacity-50 cursor-not-allowed hover:bg-transparent hover:text-gray-500 hover:border-gray-200" : ""}`}
                    >
                      {format === "Audio" && <Volume2 className="w-3.5 h-3.5 mr-1.5" />}
                      {format === "Video" && <Video className="w-3.5 h-3.5 mr-1.5" />}
                      {format} {!enabled && "(Upgrade Plan)"}
                    </Button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="mb-6">
            <p className="text-brand-body text-sm">
              {initialMode === 'audio'
                ? "Create a personalized guided audio meditation based on your conversation."
                : initialMode === 'video'
                ? "Create a personalized meditation video with Ramana imagery based on your conversation."
                : `Create a personalized meditation guide based on your conversation. This will generate a ${selectedFormat.toLowerCase()} session that you can save and use for your practice.`}
            </p>
          </div>

          <div className="text-center">
            <Button
              onClick={handleGenerateGuide}
              disabled={!conversationId || !messageId}
              className="bg-brand-button hover:bg-brand-button/90 text-white px-8 py-3 rounded-full text-lg font-medium"
            >
              {initialMode === 'audio' && <Volume2 className="w-4 h-4 mr-2" />}
              {initialMode === 'video' && <Video className="w-4 h-4 mr-2" />}
              {initialMode === 'audio'
                ? "Generate Audio Guide"
                : initialMode === 'video'
                ? "Generate Video"
                : "Generate New Meditation Guide"}
            </Button>

            {!conversationId || !messageId ? (
              <p className="mt-4 text-sm text-gray-500">
                Please start a conversation first to generate a meditation guide.
              </p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );

  if (fullScreen) {
    return <FullScreenView />;
  }

  return (
    <BaseModal
      isOpen={isOpen}
      onClose={onClose}
      title={initialMode === 'audio' ? "Create Audio Guide" : initialMode === 'video' ? "Create Meditation Video" : "Create Meditation Guide"}
    >
      {modalContent}
    </BaseModal>
  );
};

export default InlineMeditationCreator;