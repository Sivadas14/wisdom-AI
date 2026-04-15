// User Management Interfaces
export interface User {
    id: string;
    phone_number: string;
    phone_verified: boolean;
    name: string | null;
    role: string; // "user" or "admin"
    created_at: string; // ISO timestamp
    last_active: string; // ISO timestamp
}

export interface UserProfile {
    id: string;
    phone_number: string;
    email_id: string;
    country_code?: string;
    phone_verified?: boolean;
    name: string;
    role: string;
    plan_type: string;
    created_at: string;
    last_active?: string;
    last_active_at?: string;
    subscription_status: string;
    // Keeping for compatibility if needed elsewhere
    auth_user_id?: string;
    polar_customer_id?: string | null;
    updated_at?: string;
    is_active?: boolean;
}

export interface NewUserRequest {
    phone_number: string;
    name: string;
}

export interface LoginRequest {
    phone_number: string;
    otp?: string | null;
}

export interface AuthResponse {
    access_token: string;
    refresh_token: string;
    user: User | null;
}

export interface RefreshTokenRequest {
    refresh_token: string;
}

// Content Generation Interfaces
export interface ContentGenerationRequest {
    conversation_id: string;
    message_id: string;
    mode: 'audio' | 'video' | 'image';
    length?: string;
}

export interface ContentGenerationResponse {
    id: string;
    status: 'pending' | 'processing' | 'complete' | 'failed';
    error_message?: string | null;
}

export interface ContentGeneration {
    id: string;
    status: 'pending' | 'processing' | 'complete' | 'failed';
    conversation_id: string;
    message_id: string;
    content_type: 'audio' | 'video' | 'image';
    created_at: string; // ISO timestamp
    content_url: string | null;
    transcript?: string | null;
    error_message?: string | null;
}

export interface ContentGenerationListResponse {
    ids: string[];
}

// Speech Processing Interfaces
export interface TranscriptionResponse {
    text: string;
}

export interface TTSRequest {
    text: string;
}

// Chat & Conversation Interfaces
export interface CitationInfo {
    name: string;
    url: string;
}

export interface FollowUpQuestions {
    questions: string[];
}

export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'User' | 'Assistant';
    created_at: string; // ISO timestamp
    content: string;
    citations?: CitationInfo[] | null;
    follow_up_questions?: FollowUpQuestions | null;
}

export interface CreateConversationRequest {
    messages?: Message[] | null;
}

export interface ChatCompletionRequest {
    message: string;
    stream: boolean;
    mock?: boolean;
}

export interface ChatCompletionResponse {
    message: string;
    message_id: string;
    questions?: string[] | null;
    citations?: CitationInfo[] | null;
    title?: string | null;
}

export interface Conversation {
    id: string;
    user_id: string;
    title: string | null;
    created_at: string; // ISO timestamp
}

export interface ConversationsListResponse {
    conversations: Conversation[];
}

export interface ConversationDetailResponse {
    conversation: Conversation;
    messages: Message[];
    content_generations: ContentGeneration[];
}

export interface UpdateConversationTitleRequest {
    title: string;
}

export interface MessageFeedbackRequest {
    message_id: string;
    type: 'positive' | 'negative';
    comment?: string | null;
}

// Admin Interfaces
export interface UserWithUsage extends User {
    usage_stats: Record<string, any>;
}

export interface ListUsersResponse {
    users: UserProfile[];
    total_count: number;
}

export interface AdminUserDetail extends UserProfile {
    quota_details: UsageData;
    usage_stats: {
        conversations: number;
        content_generations: {
            total: number;
            video: number;
            audio: number;
            image: number;
        };
    };
}

export interface SourceDocument {
    id: string;
    filename: string;
    file_size_bytes: number;
    active: boolean;
    status: 'processing' | 'completed' | 'failed';
    created_at: string; // ISO timestamp
}

export interface SourceDocumentResponse {
    files: SourceDocument[];
}

export interface UserFeedback {
    user_id: string;
    message_id: string;
    type: 'positive' | 'negative';
    comment?: string | null;
    created_at: string; // ISO timestamp
}

export interface AdminFeedbackResponse {
    feedback: UserFeedback[];
}


// These types are still used in the frontend but are not in wire.py
// They should probably be added to wire.py and generated from there in the future.

export interface UserPreferences {
    theme: 'light' | 'dark';
    notifications: boolean;
    meditationLength: number;
    preferredFormat: 'audio' | 'video';
}

export interface AIModel {
    id: string;
    name: string;
    enabled: boolean;
    provider: string;
    capabilities: string[];
}

export interface FileInfo {
    id: string;
    name: string;
    type: string;
    size: string;
    uploadDate: string;
    url?: string;
}

export interface MeditationRequest {
    length: number; // in minutes
    format: 'audio' | 'video';
    topic?: string;
    style?: string;
}

export interface MeditationResponse {
    id: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress?: number;
    downloadUrl?: string;
    duration?: number;
    format: 'audio' | 'video';
}

export interface ContemplationCard {
    id: string;
    quote: string;
    background: string;
    downloadUrl?: string;
}

export interface Feedback {
    messageId: string;
    rating: 'thumbs_up' | 'thumbs_down';
    comment?: string;
}

// Plan Interfaces
export interface PlanPrice {
    id?: number;
    plan_id: number;
    billing_cycle: string; // 'monthly' | 'yearly'
    currency: string; // 'INR' | 'USD'
    price: number;
}


// Frontend-friendly Plan interface (transformed from backend response)
export interface PlanPrices {
    monthly: {
        INR: number;
        USD: number;
    };
    yearly: {
        INR: number;
        USD: number;
    };
}

export interface PlanLimits {
    chat: string;
    cards: number;
    meditations: number;
    maxMeditationDuration: number;
}

// Update your Plan interface
export interface Plan {
    id: string | number;
    name: string;
    description: string;
    active: boolean;
    is_recommended?: boolean;
    is_free: boolean;
    billing_cycle: string; // 'MONTHLY' | 'YEARLY' | 'FREE'
    plan_type: string;
    chat_limit: string;
    card_limit: number;
    max_meditation_duration: number;
    prices: Price[];
    is_video: boolean;
    features: PlanFeature[];
    polar_plan_id?: string;
}

export interface UsageData {
    plan_name: string;
    plan_type: string;
    chat_tokens: {
        limit: string;
        used: number;
        remaining: number;
    };
    image_cards: {
        limit: number | string;
        used: number;
        remaining: number | string;
    };
    conversations: {
        limit: string | number;
        used: number;
        remaining: number | string;
    };
    meditation_duration: {
        limit: number | string;
        used: number;
        remaining: number | string;
    };
    addon_cards?: {
        limit: number;
        used: number;
        remaining: number;
    };
    addon_minutes?: {
        limit: number;
        used: number;
        remaining: number;
    };
    audio_enabled: boolean;
    video_enabled: boolean;
}
export interface PlanFeature {
    id: number;
    feature_text: string;
    plan_id: number;
}

export interface Price {
    id: number;
    price: number;
    currency: string;
    plan_id: number;
}

// Remove or update PlanLimits interface since we're using direct fields

// Dashboard interfaces
export interface DashboardRevenueSummary {
    this_month: number;
    last_month: number;
    month_over_month_pct: number;
}

export interface DashboardCount {
    total_users: number;
    active_subscriptions: number;
    total_revenue: DashboardRevenueSummary;
    active_sessions_last_hour: number;
}

export interface PlanDistributionItem {
    plan_type: string;
    count: number;
    pct: number; // percentage
}

export interface RecentUserItem {
    id: string;
    name: string;
    email: string;
    plan_type: string;
    created_at: string; // ISO timestamp
}

export interface UpgradePreview {
    current_plan: string;
    new_plan: string;
    current_monthly_price: number;
    new_monthly_price: number;
    monthly_price_difference: number;
    proration_applicable: boolean;
    prorated_amount: number;
    days_remaining: number;
    daily_rate_difference: number;
    next_full_billing: string;
    breakdown: Array<{
        description: string;
        amount: number;
        is_total?: boolean;
    }>;
}
export interface DowngradePreview {
    can_downgrade: boolean;
    proration_applicable: boolean;
    current_plan: string;
    new_plan: string;
    current_price: number;
    new_price: number;
    price_difference: number;
    unused_credit: number;
    new_plan_prorated_charge: number;
    net_amount: number;
    credit_or_charge_description: string;
    will_receive_credit: boolean;
    days_remaining: number;
    next_billing_date: string;
    next_full_billing_amount: number;
}

export interface Order {
    id: string;
    invoice_number: string;
    status: string;
    total_amount: number;
    currency: string;
    created_at: string;
    billing_name: string;
    product?: {
        name: string;
    };
}

export interface OrdersListResponse {
    items: Order[];
    pagination: {
        total_count: number;
        max_page: number;
    };
}

export interface Addon {
    id: number;
    name: string;
    description: string;
    unit_type: string;
    quantity: number;
    is_recommended: boolean;
    price_inr: number;
    price_usd: number;
}

export interface AddonSubscribeResponse {
    success: boolean;
    checkout_url: string;
    message: string;
}

export interface Subscription {
    id: string;
    user_id: string;
    plan_id: string;
    polar_subscription_id: string;
    status: 'active' | 'canceled' | 'past_due' | 'incomplete';
    current_period_start: string;
    current_period_end: string;
    cancel_at_period_end: boolean;
    canceled_at: string | null;
    ended_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface SubscriptionResponse {
    subscription: Subscription | null;
    plan: Plan | null;
}

export interface Notification {
    id: number;
    message: string;
    created_at: string;
}