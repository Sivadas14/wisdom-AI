import apiClient from './client';
import {
    AdminFeedbackResponse,
    AuthResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ContentGeneration,
    ContentGenerationRequest,
    ContentGenerationResponse,
    Conversation,
    ConversationDetailResponse,
    ConversationsListResponse,
    CreateConversationRequest,
    ListUsersResponse,
    LoginRequest,
    MessageFeedbackRequest,
    NewUserRequest,
    RefreshTokenRequest,
    SourceDocumentResponse,
    UpdateConversationTitleRequest,
    User,
    Plan,
    PlanPrices,
    UsageData,
    DashboardCount,
    PlanDistributionItem,
    RecentUserItem,
    UserProfile,
    AdminUserDetail,
    UpgradePreview,
    DowngradePreview,
    SubscriptionResponse,
    Order,
    OrdersListResponse,
    Addon,
    AddonSubscribeResponse,
    Notification,
} from './wire';


// Authentication APIs
export const authAPI = {
    register: async (data: NewUserRequest): Promise<AuthResponse> => {
        const response = await apiClient.post('/auth/register', data);
        const { access_token, refresh_token, user } = response.data;
        if (access_token) localStorage.setItem('accessToken', access_token);
        if (refresh_token) localStorage.setItem('refreshToken', refresh_token);
        return { access_token, refresh_token, user };
    },
    login: async (data: LoginRequest): Promise<AuthResponse> => {
        const response = await apiClient.post('/auth/login', data);
        const { access_token, refresh_token, user } = response.data;
        if (access_token) localStorage.setItem('accessToken', access_token);
        if (refresh_token) localStorage.setItem('refreshToken', refresh_token);
        return { access_token, refresh_token, user };
    },

    logout: async () => {
        await apiClient.post('/auth/logout');
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
    },

    getCurrentUser: async (): Promise<User> => {
        const response = await apiClient.get('/auth/me');
        return response.data;
    },

    refreshToken: async (data: RefreshTokenRequest): Promise<AuthResponse> => {
        const response = await apiClient.post('/auth/refresh', data);
        const { access_token, refresh_token, user } = response.data;
        if (access_token) localStorage.setItem('accessToken', access_token);
        return { access_token, refresh_token, user };
    },
};

// Chat APIs
export const chatAPI = {
    getConversations: async (): Promise<ConversationsListResponse> => {
        const response = await apiClient.get('/chat');
        return response.data;
    },
    createConversation: async (request: CreateConversationRequest): Promise<Conversation> => {
        const response = await apiClient.post('/chat', request);
        return response.data;
    },
    getConversation: async (id: string): Promise<ConversationDetailResponse> => {
        const response = await apiClient.get(`/chat/${id}`);
        return response.data;
    },
    chatCompletion: async (
        conversationId: string,
        request: ChatCompletionRequest,
        onChunk?: (chunk: string) => void
    ): Promise<ChatCompletionResponse> => {
        const { stream } = request;
        if (stream && onChunk) {
            // Use fetch for proper streaming support
            const response = await fetch(`${apiClient.defaults.baseURL}/chat/${conversationId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('accessToken')}`,
                },
                body: JSON.stringify(request),
            });

            if (!response.ok) {
                if (response.status === 403) {
                    console.error('❌ [chatAPI] Forbidden (403) during streaming. Logging out...');
                    localStorage.removeItem('accessToken');
                    localStorage.removeItem('refreshToken');
                    localStorage.removeItem('userProfile');
                    window.location.href = '/signin?error=deactivated';
                }
                if (response.status === 429 || response.status === 402) {
                    throw new Error('QUOTA_EXCEEDED');
                }
                const errorText = await response.text();
                // Also detect quota errors embedded in 500 error bodies
                if (errorText.includes('quota') || errorText.includes('limit') || errorText.includes('exceeded')) {
                    throw new Error('QUOTA_EXCEEDED');
                }
                throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
            }

            if (!response.body) {
                throw new Error('No response body available for streaming');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            let partialData = '';
            let parsedResponse: Partial<ChatCompletionResponse> = {
                message: '',
                message_id: '',
                questions: [],
                citations: [],
                title: undefined
            };
            let collectingQuestions = false;

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    partialData += chunk;

                    // Split by newlines to handle multiple chunks in one read
                    const lines = partialData.split('\n');
                    partialData = lines.pop() || ''; // Keep the last incomplete line

                    for (const line of lines) {
                        if (line.trim() === '') continue;
                        if (line === '[DONE]') continue;

                        try {
                            // Handle different chunk formats
                            let content = '';

                            // Parse OpenAI-style streaming chunk (data: {...})
                            if (line.startsWith('data: ')) {
                                const jsonStr = line.slice(6);
                                if (jsonStr.trim() === '[DONE]') continue;

                                const chunkData = JSON.parse(jsonStr);
                                content = chunkData.choices?.[0]?.delta?.content || '';
                            }
                            // Handle direct JSON streaming chunks
                            else if (line.startsWith('{') && line.includes('choices')) {
                                const chunkData = JSON.parse(line);
                                content = chunkData.choices?.[0]?.delta?.content || '';
                            }
                            // Handle plain text lines (for your custom format)
                            else {
                                content = line + (line.endsWith('\n') ? '' : '\n');
                            }

                            if (content !== '') {
                                // Handle special tags from your backend
                                // Handle message_id
                                if (content.includes('<message_id>') && content.includes('</message_id>')) {
                                    const match = content.match(/<message_id>(.*?)<\/message_id>/);
                                    if (match) {
                                        parsedResponse.message_id = match[1];
                                        content = content.replace(match[0], '');
                                    }
                                }

                                // Handle title
                                if (content.includes('<title>') && content.includes('</title>')) {
                                    const match = content.match(/<title>(.*?)<\/title>/);
                                    if (match) {
                                        parsedResponse.title = match[1];
                                        content = content.replace(match[0], '');
                                    }
                                }

                                // Handle questions tags
                                if (content.includes('<questions>')) {
                                    collectingQuestions = true;
                                    content = content.replace('<questions>', '');
                                }
                                if (content.includes('</questions>')) {
                                    collectingQuestions = false;
                                    content = content.replace('</questions>', '');
                                }

                                // Handle citations tags
                                if (content.includes('<citations>')) {
                                    content = content.replace('<citations>', '');
                                }
                                if (content.includes('</citations>')) {
                                    content = content.replace('</citations>', '');
                                }

                                // If content is empty after stripping tags, continue
                                if (content === '') continue;

                                // Process remaining content
                                if (collectingQuestions) {
                                    if (content.trim()) {
                                        if (!parsedResponse.questions) {
                                            parsedResponse.questions = [];
                                        }
                                        parsedResponse.questions.push(content.trim());
                                    }
                                } else if (content.trim().startsWith('{') && content.includes('"name"')) {
                                    // Citation JSON
                                    try {
                                        const citation = JSON.parse(content);
                                        parsedResponse.citations?.push(citation);
                                    } catch (e) {
                                        // Not valid JSON, treat as regular content
                                        parsedResponse.message += content;
                                        onChunk(parsedResponse.message);
                                    }
                                } else {
                                    // Regular message content - accumulate and call onChunk
                                    parsedResponse.message += content;
                                    onChunk(parsedResponse.message);
                                }
                            }
                        } catch (e) {
                            // If JSON parsing fails, treat as plain text content (preserving formatting)
                            if (collectingQuestions) {
                                if (line.trim()) {
                                    if (!parsedResponse.questions) {
                                        parsedResponse.questions = [];
                                    }
                                    parsedResponse.questions.push(line.trim());
                                }
                            } else {
                                parsedResponse.message += line + '\n';
                                onChunk(parsedResponse.message);
                            }
                        }
                    }
                }
            } catch (streamError) {
                console.error('Streaming error:', streamError);
                throw new Error(`Streaming failed: ${streamError instanceof Error ? streamError.message : 'Unknown error'}`);
            } finally {
                reader.releaseLock();
            }

            // Validate response has required fields
            if (!parsedResponse.message_id) {
                parsedResponse.message_id = `temp-${Date.now()}`;
            }
            if (!parsedResponse.message) {
                throw new Error('No message content received from stream');
            }

            return parsedResponse as ChatCompletionResponse;
        } else {
            const response = await apiClient.post(`/chat/${conversationId}`, request);
            return response.data;
        }
    },
    deleteConversation: async (id: string): Promise<void> => {
        await apiClient.delete(`/chat/${id}`);
    },
    updateConversationTitle: async (id: string, title: string): Promise<Conversation> => {
        const request: UpdateConversationTitleRequest = { title };
        const response = await apiClient.put(`/chat/${id}/title`, request);
        return response.data;
    },
    generateConversationTitle: async (id: string): Promise<Conversation> => {
        const response = await apiClient.post(`/chat/${id}/title`);
        return response.data;
    },
    submitFeedback: async (conversationId: string, feedback: MessageFeedbackRequest): Promise<void> => {
        await apiClient.post(`/chat/${conversationId}/feedback`, feedback);
    },
};

// Content Generation APIs
export const contentAPI = {
    createContent: async (request: ContentGenerationRequest): Promise<ContentGenerationResponse> => {
        const response = await apiClient.post('/content', request);
        return response.data;
    },
    getContent: async (contentId: string): Promise<ContentGeneration> => {
        const response = await apiClient.get(`/content/${contentId}`);
        return response.data;
    },
    getImages: async (page = 1, limit = 10): Promise<ContentGeneration[]> => {
        const response = await apiClient.get(`/content/images?page=${page}&limit=${limit}`);
        return response.data;
    },
    getMedia: async (page = 1, limit = 10): Promise<ContentGeneration[]> => {
        const response = await apiClient.get(`/content/media?page=${page}&limit=${limit}`);
        return response.data;
    }
};

// Admin APIs
export const adminAPI = {
    listUsers: async (limit = 10, skip = 0): Promise<ListUsersResponse> => {
        const response = await apiClient.get('/admin/users', {
            params: { limit, skip }
        });
        return response.data;
    },
    getUserDetail: async (userId: string): Promise<AdminUserDetail> => {
        const response = await apiClient.get(`/admin/users/${userId}`);
        return response.data;
    },
    deleteUser: async (userId: string): Promise<void> => {
        await apiClient.delete(`/admin/users/${userId}`);
    },
    toggleUserActive: async (userId: string): Promise<{ success: boolean; message: string; data: { is_active: boolean } }> => {
        const response = await apiClient.patch(`/admin/users/${userId}/toggle-active`);
        return response.data;
    },
    deleteContent: async (contentId: string): Promise<void> => {
        await apiClient.delete(`/admin/content/${contentId}`);
    },
    getFeedback: async (): Promise<AdminFeedbackResponse> => {
        const response = await apiClient.get('/admin/feedback');
        return response.data;
    },
    listSourceData: async (): Promise<SourceDocumentResponse> => {
        const response = await apiClient.get('/admin/source-data/list');
        return response.data;
    },
    getAllProfiles: async (): Promise<UserProfile[]> => {
        const response = await apiClient.get('/profiles/'); // based on user request "profiles/"
        return response.data;
    },
};
// Add this to your existing API file
export const usageAPI = {
    getUsage: async (): Promise<UsageData> => {
        const response = await apiClient.get('/usage');
        return response.data;
    }
};

export const addonAPI = {
    getAddons: async (): Promise<Addon[]> => {
        const response = await apiClient.get('/addon/');
        return response.data;
    }
};

export const paymentAPI = {
    createCheckoutSession: async (
        polarPlanId: string,
        userId: string,
        redirect_url?: string,
        // cancelUrl?: string
    ) => {
        // Matches CURL: /api/subscriptions/checkout?polar_product_id=...&user_id=...&redirect_url=...
        let url = `/subscriptions/checkout?polar_product_id=${polarPlanId}&user_id=${userId}`;
        if (redirect_url) {
            url += `&redirect_url=${encodeURIComponent(redirect_url)}`;
        }
        const response = await apiClient.post(url);
        return response.data;
    },

    createRazorpayCheckoutSession: async (
        planId: number,
        userId: string,
        redirect_url?: string,
    ) => {
        // Calls /api/subscriptions/razorpay-checkout?plan_id=...&user_id=...
        let url = `/subscriptions/razorpay-checkout?plan_id=${planId}&user_id=${userId}`;
        if (redirect_url) {
            url += `&redirect_url=${encodeURIComponent(redirect_url)}`;
        }
        const response = await apiClient.post(url);
        return response.data;
    },

    syncSubscription: async (userId: string): Promise<any> => {
        // Matches CURL: GET /api/subscriptions/sync?user_id=...
        const response = await apiClient.get(`/subscriptions/sync?user_id=${encodeURIComponent(userId)}`);
        return response.data;
    },

    getUpgradePreview: async (polarProductId: string, userId: string): Promise<UpgradePreview> => {
        // Matches user provided URL: /api/subscriptions/upgrade/previews?polar_product_id=...&user_id=...
        const response = await apiClient.get(`/subscriptions/upgrade/previews?polar_product_id=${polarProductId}&user_id=${userId}`);
        return response.data.data;
    },

    getSubscription: async (): Promise<SubscriptionResponse> => {
        const response = await apiClient.get('/subscriptions/me');
        return response.data;
    },

    upgradeSubscription: async (userId: string, newPolarPlanId: string): Promise<any> => {
        // Matches POST /api/subscriptions/upgrades
        // /v1/subscriptions/upgrade
        const response = await apiClient.post('/subscriptions/upgrade', {
            user_id: userId,
            new_polar_plan_id: newPolarPlanId
        });
        return response.data;
    },

    cancelSubscription: async (userId: string, subscriptionId: string): Promise<any> => {
        // Matches POST /api/subscriptions/cancel
        const response = await apiClient.post('/subscriptions/cancel', {
            user_id: userId,
            subscription_id: subscriptionId
        });
        return response.data;
    },

    revokeSubscription: async (userId: string): Promise<any> => {
        // Matches POST /api/subscriptions/revoke
        const response = await apiClient.post('/subscriptions/revoke', {
            user_id: userId
        });
        return response.data;
    },

    subscribeAddon: async (addonId: number, userId: string, successUrl: string): Promise<AddonSubscribeResponse> => {
        // Matches POST /api/pollor/subscribe?addon_id=...&user_id=...&redirect_url=...
        const response = await apiClient.post(`/pollor/subscribe?addon_id=${addonId}&user_id=${userId}&redirect_url=${encodeURIComponent(successUrl)}`);
        return response.data;
    },

    getDowngradePreview: async (polarProductId: string, userId: string): Promise<DowngradePreview> => {
        // Matches GET /api/subscriptions/downgrade/preview?polar_product_id=...&user_id=...
        const response = await apiClient.get(`/subscriptions/downgrade/preview?polar_product_id=${polarProductId}&user_id=${userId}`);
        return response.data.data;
    },

    downgradeSubscription: async (polarProductId: string, userId: string): Promise<any> => {
        // Matches POST /api/subscriptions/downgrade/checkout
        const response = await apiClient.post('/subscriptions/downgrade/checkout', {
            polar_product_id: polarProductId,
            user_id: userId
        });
        return response.data;
    }
};

export const notificationAPI = {
    getNotificationBar: async (id?: number | string): Promise<Notification | Notification[]> => {
        const url = id ? `/notification-bar/${id}` : '/notification-bar/';
        const response = await apiClient.get(url);
        return response.data;
    },
    createNotification: async (data: Partial<Notification>): Promise<Notification> => {
        const response = await apiClient.post('/notification-bar/', data);
        return response.data;
    },
    updateNotification: async (id: number | string, data: Partial<Notification>): Promise<Notification> => {
        const response = await apiClient.put(`/notification-bar/${id}`, data);
        return response.data;
    },
    deleteNotification: async (id: number | string): Promise<void> => {
        await apiClient.delete(`/notification-bar/${id}`);
    }
};

// Dashboard APIs
export const dashboardAPI = {
    getCount: async (): Promise<DashboardCount> => {
        const response = await apiClient.get('/dashboard/count');
        return response.data;
    },
    getPlanDistribution: async (): Promise<PlanDistributionItem[]> => {
        const response = await apiClient.get('/dashboard/plan_distribution');
        return response.data;
    },
    getRecentUsers: async (limit = 10, days = 7): Promise<RecentUserItem[]> => {
        const response = await apiClient.get(`/dashboard/recent_users?limit=${limit}&days=${days}`);
        return response.data;
    },
    getRecentTransactions: async (limit = 10, days = 7): Promise<any[]> => {
        const response = await apiClient.get(`/dashboard/recent_transactions?limit=${limit}&days=${days}`);
        return response.data;
    },
    getUsersAtLimit: async (): Promise<{ users_at_limit: number; total_free_users: number; pct: number; chat_limit: number }> => {
        const response = await apiClient.get('/dashboard/users_at_limit');
        return response.data;
    },
    getSignupsTrend: async (days = 30): Promise<{ date: string; signups: number }[]> => {
        const response = await apiClient.get(`/dashboard/signups_trend?days=${days}`);
        return response.data;
    },
};

// Plan APIs
export const plansAPI = {
    getPlans: async (): Promise<Plan[]> => {
        const response = await apiClient.get('/plans/');
        return response.data;
    },

    getPlan: async (planId: number): Promise<Plan> => {
        const response = await apiClient.get(`/plans/${planId}`);
        return response.data;
    },

    createPlan: async (plan: Plan): Promise<Plan> => {
        const response = await apiClient.post('/plans/', plan);
        return response.data;
    },

    updatePlan: async (plan: Plan): Promise<Plan> => {
        const response = await apiClient.put(`/plans/${plan.id}`, plan);
        return response.data;
    },

    deletePlan: async (planId: number): Promise<void> => {
        await apiClient.delete(`/plans/${planId}`);
    }
};

export const ordersAPI = {
    getOrdersAdmin: async (page = 1, limit = 1): Promise<OrdersListResponse> => {
        const response = await apiClient.get(`/orders/?page=${page}&limit=${limit}`);
        return response.data;
    },
    getOrders: async (page = 1, limit = 10): Promise<OrdersListResponse> => {
        const response = await apiClient.get(`/orders/me?page=${page}&limit=${limit}`);
        return response.data;
    },
    downloadInvoice: async (orderId: string): Promise<{ url: string }> => {
        const response = await apiClient.get(`/orders/${orderId}/invoice`);
        return response.data;
    }
};

export const profileAPI = {
    markOnboardingSeen: async (): Promise<void> => {
        await apiClient.patch('/profiles/me/onboarding-seen');
    },
};

export interface RamanaImageItem {
    id: string;
    filename: string;
    description: string | null;
    active: boolean;
    storage_path: string;
    preview_url: string;
    created_at: string | null;
}

export const ramanaImagesAPI = {
    list: async (): Promise<{ images: RamanaImageItem[]; total: number; active: number }> => {
        const res = await apiClient.get('/admin/ramana-images');
        return res.data;
    },
    upload: async (files: File[], description?: string): Promise<{ uploaded: { id: string; filename: string }[]; errors: string[] }> => {
        const form = new FormData();
        files.forEach(f => form.append('files', f));
        if (description) form.append('description', description);
        // Setting Content-Type to undefined removes the default 'application/json' so the
        // browser can set multipart/form-data with the correct boundary automatically.
        const res = await apiClient.post('/admin/ramana-images', form, {
            headers: { 'Content-Type': undefined },
        });
        return res.data;
    },
    toggle: async (id: string): Promise<{ id: string; active: boolean }> => {
        const res = await apiClient.patch(`/admin/ramana-images/${id}/toggle`);
        return res.data;
    },
    delete: async (id: string): Promise<void> => {
        await apiClient.delete(`/admin/ramana-images/${id}`);
    },
};

// Export all APIs
export default {
    auth: authAPI,
    chat: chatAPI,
    content: contentAPI,
    admin: adminAPI,
    payment: paymentAPI,
    dashboard: dashboardAPI,
    plans: plansAPI,
    orders: ordersAPI,
    addon: addonAPI,
    notification: notificationAPI,
};
