# Authentication Interfaces

import datetime
from tuneapi import tt
from enum import Enum
from typing import Optional


class FeatureCreate(tt.BM):
    id: int | None = None
    feature_text: str

class Feature(tt.BM):
    id: int
    feature_text: str

    class Config:
        from_attributes = True


class PlanFeatureCreateV1(tt.BM):
    id: int | None = None
    plan_id: int | None = None
    feature_id: int | None = None
    feature_text: str | None = None # For convenience, can provide text or ID

class PlanMappingRequestV1(tt.BM):
    plan_id: int
    feature_id: int        
    order: int = 0



class UserProfileIn(tt.BM):
    auth_user_id: str
    email_id: str
    phone_number: str | None = None
    name: str | None = None
    role: str 
    plan_type: str = "FREE" 
    country_code : str | None = None


# class PlanFeatureCreate(tt.BM):
#     plan_id: int
#     feature_text: str


# class PlanPriceCreate(tt.BM):
#     plan_id: int
#     currency: str        # e.g., "INR" or "USD"
#     price: float




class AddonUnitTypeEnum(str, Enum):
    CARDS = "CARDS"
    MINUTES = "MINUTES"


class AddonTypeIn(tt.BM):
    name: str
    description: Optional[str] = None

    unit_type: AddonUnitTypeEnum
    quantity: int = 1

    is_recommended: bool = True

    price_inr: Optional[float] = None
    price_usd: Optional[float] = None


class AddonTypeOut(AddonTypeIn):
    id: int

    class Config:
        from_attributes = True
    



class PlanFeatureCreate(tt.BM):
    id: int | None = None  # ✅ Optional: None for create, set for update
    feature_text: str
    order: int = 0


class PlanPriceCreate(tt.BM):
    id: int | None = None  # ✅ Optional: None for create, set for update
    currency: str
    price: float


class PlanCreate(tt.BM):
    name: str
    description: str
    active: bool
    is_recommended: bool
    chat_limit: str
    card_limit: int
    max_meditation_duration: int
    prices: list[PlanPriceCreate]
    plan_type: str
    is_free: bool
    is_audio: bool = False
    is_video: bool = False
    billing_cycle: str
    features: list[PlanFeatureCreate]

   
# User Management Interfaces
class User(tt.BM):
    id: str = tt.F("Unique user identifier")
    phone_number: str | None = tt.F("User's phone number", None)
    email_id: str | None = tt.F("User's email address", None)
    country_code: str | None = tt.F("User's country code", None)
    phone_verified: bool = tt.F("Whether user's phone number is verified")
    name: str | None = tt.F("User's display name")
    role: str = tt.F("User role: user or admin")
    plan_type: str = tt.F("User plan type: FREE, BASIC, PRO", "BASIC")
    created_at: datetime.datetime = tt.F("ISO timestamp of account creation")
    last_active: datetime.datetime = tt.F("ISO timestamp of last active")
    is_active: bool = tt.F("Whether user account is active", True)
    onboarding_seen: bool = tt.F("Whether user has seen the onboarding modal", False)


class NewUserRequest(tt.BM):
    phone_number: str = tt.F("Phone number in international format")
    name: str = tt.F("User's display name")


class LoginRequest(tt.BM):
    phone_number: str = tt.F("Phone number in international format")
    otp: str | None = tt.F("OTP code for verification, required on second call", None)


class AuthResponse(tt.BM):
    access_token: str = tt.F("JWT access token")
    refresh_token: str = tt.F("JWT refresh token for session renewal")
    user: User | None = tt.F("User profile information")


class RefreshTokenRequest(tt.BM):
    refresh_token: str = tt.F("Refresh token to generate new access token")


# Content Generation Interfaces


class ContentGenerationRequest(tt.BM):
    conversation_id: str = tt.F("ID of conversation context for content")
    message_id: str = tt.F("ID of message that triggered generation")
    mode: str = tt.F("Generation mode: audio, video, image")
    length: str | None = tt.F("Target duration for generation (e.g. '5 min')", None)


class ContentGenerationResponse(tt.BM):
    id: str = tt.F("Unique identifier for generated content")
    status: str = tt.F("Processing status: pending, processing, complete, failed")
    error_message: str | None = tt.F("Error message when status='failed'", None)


class ContentGeneration(tt.BM):
    id: str = tt.F("Unique content identifier")
    status: str = tt.F("Processing status: pending, processing, complete, failed")
    conversation_id: str = tt.F("ID of conversation context")
    message_id: str = tt.F("ID of message that triggered generation")
    content_type: str = tt.F("Content type: audio, video, image")
    content_url: str | None = tt.F("Presigned URL for generated content", None)
    created_at: datetime.datetime = tt.F("ISO timestamp of creation")
    transcript: str | None = tt.F("Full meditation script text")
    error_message: str | None = tt.F("Error message when status='failed'", None)


class ContentGenerationListResponse(tt.BM):
    ids: list[str] = tt.F("List of user's content IDs")


# Usage Tracking Interfaces


class UsageLimit(tt.BM):
    """Represents a usage limit with used and remaining amounts"""
    limit: str | int = tt.F("Total limit (number or 'Unlimited')")
    used: int = tt.F("Amount already used")
    remaining: str | int = tt.F("Amount remaining (number or 'Unlimited')")


class UserUsageResponse(tt.BM):
    """Complete usage statistics for a user"""
    plan_name: str = tt.F("Name of the user's current plan")
    plan_type: str = tt.F("Type of plan: FREE, BASIC, PRO")
    chat_tokens: UsageLimit = tt.F("Chat token usage statistics")
    image_cards: UsageLimit = tt.F("Image generation card usage statistics")
    conversations: UsageLimit =tt.F("converstation limit")
    meditation_duration: UsageLimit = tt.F("Audio/Video meditation duration in seconds")
    addon_cards: UsageLimit | None = tt.F("Addon card usage statistics", None)
    addon_minutes: UsageLimit | None = tt.F("Addon minutes usage statistics", None)
    audio_enabled: bool = tt.F("Whether audio generation is enabled")
    video_enabled: bool = tt.F("Whether video generation is enabled")



# Speech Processing Interfaces


class TranscriptionResponse(tt.BM):
    text: str = tt.F("Transcribed text from audio input")


class TTSRequest(tt.BM):
    text: str = tt.F("Text to convert to speech")


# Chat & Conversation Interfaces
class CitationInfo(tt.BM):
    name: str = tt.F("Name of the cited document")
    url: str = tt.F("URL to view the cited document")


class FollowUpQuestions(tt.BM):
    questions: list[str] = tt.F("Follow up questions")


class Message(tt.BM):
    id: str = tt.F("Unique message identifier")
    role: str = tt.F("Message role: user, assistant")
    created_at: datetime.datetime = tt.F("ISO timestamp of message creation")
    content: str = tt.F("Message content text")
    citations: list[CitationInfo] | None = tt.F(
        "List of citations for this message", None
    )
    follow_up_questions: FollowUpQuestions | None = tt.F("Follow up questions", None)


class CreateConversationRequest(tt.BM):
    messages: list[Message] | None = tt.F("Messages to start the conversation", None)


class ChatCompletionRequest(tt.BM):
    message: str = tt.F("Message to send to the model")
    stream: bool = tt.F("Whether to stream the response")
    mock: bool = tt.F("Whether to use a mock response", False)


class ChatCompletionResponse(tt.BM):
    message: str = tt.F("Message to send to the model")
    message_id: str = tt.F("ID of the message that was sent")
    questions: list[str] | None = tt.F("Follow up questions")
    citations: list[CitationInfo] | None = tt.F("List of citations for this message")
    title: str | None = tt.F("Auto-generated or custom conversation title", None)


class ContemplationCardContent(tt.BM):
    """Structured response for contemplation card generation"""
    image_prompt: str = tt.F("A peaceful, contemplative image prompt (1 sentence)")
    quote: str = tt.F("A short, meaningful contemplative quote (1-2 sentences)")


class Conversation(tt.BM):
    id: str = tt.F("Unique conversation identifier")
    user_id: str = tt.F("ID of the user who owns this conversation")
    title: str | None = tt.F("Auto-generated or custom conversation title")
    created_at: datetime.datetime = tt.F("ISO timestamp of conversation creation")


class ConversationsListResponse(tt.BM):
    conversations: list[Conversation] = tt.F("List of user conversations")


class ConversationDetailResponse(tt.BM):
    conversation: Conversation = tt.F("Conversation metadata")
    messages: list[Message] = tt.F("All messages in the conversation")
    content_generations: list[ContentGeneration] | None = tt.F(
        "Content generations for this conversation", None
    )


class UpdateConversationTitleRequest(tt.BM):
    title: str = tt.F("New title for the conversation")


class MessageFeedbackRequest(tt.BM):
    message_id: str = tt.F("ID of the message to provide feedback for")
    type: str = tt.F("Feedback type: positive, negative")
    comment: str | None = tt.F("Optional feedback comment")


# Admin Interfaces


class UserListItem(User):
    subscription_status: str | None = tt.F("User's subscription status", None)

class UserWithUsage(UserListItem):
    quota_details: UserUsageResponse | None = tt.F("Comprehensive quota details", None)
    usage_stats: dict = tt.F("Usage statistics")


class ListUsersResponse(tt.BM):
    users: list[UserListItem] = tt.F("List of all users")
    total_count: int = tt.F("Total number of users matching the filter")


class SourceDocument(tt.BM):
    id: str = tt.F("Unique document identifier")
    filename: str = tt.F("Original filename")
    file_size_bytes: int = tt.F("File size in bytes")
    active: bool = tt.F("Whether document is active for RAG")
    status: str = tt.F("Processing status: processing, completed, failed")
    created_at: datetime.datetime = tt.F("Upload timestamp")


class SourceDocumentsResponse(tt.BM):
    files: list[SourceDocument] = tt.F("List of uploaded documents")


class UserFeedback(tt.BM):
    user_id: str = tt.F("ID of user who gave feedback")
    message_id: str = tt.F("ID of message being rated")
    type: str = tt.F("Feedback type: positive, negative")
    comment: str | None = tt.F("Feedback comment")
    created_at: datetime.datetime = tt.F("Feedback timestamp")


class AdminFeedbackResponse(tt.BM):
    feedback: list[UserFeedback] = tt.F("List of user feedback")


# API Response Wrappers


class SuccessResponse(tt.BM):
    success: bool = tt.F("Whether the operation succeeded", True)
    message: str | None = tt.F("Optional success message")
    data: dict | None = tt.F("Response data", None)


class _ErrorResponse(tt.BM):
    success: bool = tt.F("Whether the operation succeeded", False)
    code: str = tt.F("Error code identifier")
    message: str = tt.F("Human readable error message")
    details: dict | None = tt.F("Additional error details")


def Error(code: str, message: str, details: dict | None = None) -> _ErrorResponse:
    return _ErrorResponse(code=code, message=message, details=details)
