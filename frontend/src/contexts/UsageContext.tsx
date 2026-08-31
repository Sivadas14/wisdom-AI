import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { usageAPI, paymentAPI } from '@/apis/api';
import { useAuth } from './AuthContext';
import { SubscriptionResponse } from '@/apis/wire';
import { PlansModal } from '@/components/billing/PlansModal';
import { AddonsModal } from '@/components/billing/AddonsModal';
import { CreditsModal } from '@/components/billing/CreditsModal';
import { toast } from 'sonner';

export interface UsageData {
    plan_name: string;
    plan_type: string;
    chat_tokens: {
        limit: string;
        used: number;
        remaining: number;
    };
    image_cards: {
        limit: number;
        used: number;
        remaining: number;
    };
    conversations: {
        limit: string | number;
        used: number;
        remaining: number | string;
    };
    meditation_duration: {
        limit: number;
        used: number;
        remaining: number;
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
    // Present only while the credit system is active. Their presence is how
    // the whole frontend knows which model is in force — no separate flag.
    credits_balance?: number | null;
    minutes_per_credit?: number | null;
}

export type FeatureType = 'chat' | 'image' | 'audio' | 'video' | 'meditation';

interface UsageContextType {
    usage: UsageData | null;
    loading: boolean;
    refreshUsage: () => Promise<void>;
    subscription: SubscriptionResponse | null;
    subscriptionLoading: boolean;
    refreshSubscription: () => Promise<void>;
    // Modal states and triggers
    showPlansModal: boolean;
    setShowPlansModal: (show: boolean) => void;
    showAddonsModal: boolean;
    setShowAddonsModal: (show: boolean) => void;
    addonsModalMode: 'default' | 'cards' | 'minutes';
    setAddonsModalMode: (mode: 'default' | 'cards' | 'minutes') => void;
    checkQuota: (feature: FeatureType) => boolean;
    // Credits
    creditsActive: boolean;
    showCreditsModal: boolean;
    openCreditsModal: (reason?: string) => void;
    setShowCreditsModal: (show: boolean) => void;
}

const UsageContext = createContext<UsageContextType | undefined>(undefined);

export const UsageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const { user, userProfile } = useAuth();
    const [usage, setUsage] = useState<UsageData | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
    const [subscriptionLoading, setSubscriptionLoading] = useState<boolean>(false);

    // Modal states
    const [showPlansModal, setShowPlansModal] = useState(false);
    const [showAddonsModal, setShowAddonsModal] = useState(false);
    const [addonsModalMode, setAddonsModalMode] = useState<'default' | 'cards' | 'minutes'>('default');
    const [showCreditsModal, setShowCreditsModal] = useState(false);
    const [creditsReason, setCreditsReason] = useState<string | null>(null);

    // The backend advertises the credit model by populating credits_balance in
    // /api/usage. Nothing else has to be configured client-side.
    const creditsActive = usage?.credits_balance !== null && usage?.credits_balance !== undefined;

    const openCreditsModal = (reason?: string) => {
        setCreditsReason(reason ?? null);
        setShowCreditsModal(true);
    };

    const fetchUsage = async () => {
        if (!user) {
            setUsage(null);
            setLoading(false);
            return;
        }

        try {
            const data = await usageAPI.getUsage();
            setUsage(data as UsageData);
        } catch (error) {
            console.error('Failed to fetch usage data:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchSubscription = async () => {
        if (!user) {
            setSubscription(null);
            return;
        }
        setSubscriptionLoading(true);
        try {
            const data = await paymentAPI.getSubscription();
            setSubscription(data);
        } catch (error) {
            console.error('Failed to fetch subscription:', error);
        } finally {
            setSubscriptionLoading(false);
        }
    };

    useEffect(() => {
        if (user) {
            // Set loading=true and clear stale usage BEFORE fetching.
            // This ensures usageLoading=true during the in-flight window so
            // Chat.tsx's isFree guard (usageLoading ? true : ...) fires and
            // renders the FREE welcome screen instead of the wrong paid screen.
            setLoading(true);
            setUsage(null);
            console.log('🔵 [UsageContext] User ready, fetching usage and subscription...');
            fetchUsage();
            fetchSubscription();
        } else {
            setUsage(null);
            setSubscription(null);
            setLoading(false);
        }
    }, [user]);

    // Proactive nudge: if a FREE user has exhausted their chat quota when the app
    // loads, automatically open the Plans modal. Fires at most once per browser session.
    useEffect(() => {
        if (!usage || loading) return;
        if (usage.plan_type !== 'FREE') return;
        // Under credits there is no chat quota, so there is nothing to nudge
        // anyone to buy. The proactive paywall belongs to the old model only.
        if (creditsActive) return;

        const nudgeKey = 'quota_nudge_shown';
        if (sessionStorage.getItem(nudgeKey)) return;

        const chatRemaining = usage.conversations.remaining;
        const chatExhausted = typeof chatRemaining === 'number' && chatRemaining <= 0;
        if (chatExhausted) {
            sessionStorage.setItem(nudgeKey, '1');
            // Small delay so the page has time to render before the modal appears
            setTimeout(() => setShowPlansModal(true), 800);
        }
    }, [usage, loading]);

    const refreshUsage = async () => {
        // Just fetch without setting loading to true to avoid UI flickering if not needed
        // but keeping it for consistency if requested
        await fetchUsage();
    };

    const refreshSubscription = async () => {
        await fetchSubscription();
    };

    // Treat "Unlimited" (string, from Seeker/Devotee plans) as having remaining quota.
    // The backend returns remaining as either a number OR the string "Unlimited";
    // a naive `remaining > 0` check incorrectly returns false for the string case
    // and triggered the "limit exceeded" modal for Seeker users with unlimited cards.
    const hasRemaining = (remaining: number | string | undefined | null): boolean => {
        if (typeof remaining === "string") {
            // Any non-empty string (e.g. "Unlimited") means no numeric cap.
            return remaining.length > 0;
        }
        if (typeof remaining === "number") {
            return remaining > 0;
        }
        return false;
    };

    const checkQuota = (feature: FeatureType): boolean => {
        if (!usage) return false;

        // ── Credit model ────────────────────────────────────────────────────
        // Chat and cards are free without limit. Audio and video are a
        // question of affording them; the precise cost depends on the length
        // chosen, so the fine-grained check lives next to the Generate button
        // and this coarse gate only catches an empty wallet early.
        if (creditsActive) {
            if (feature === 'chat' || feature === 'image') return true;
            if (feature === 'audio' || feature === 'video') {
                if ((usage.credits_balance ?? 0) >= 1) return true;
                openCreditsModal(
                    `Personalised ${feature} uses credits, and your balance is 0.`
                );
                return false;
            }
            return true;
        }

        switch (feature) {
            case 'chat': {
                const canChat = hasRemaining(usage.conversations.remaining);
                if (!canChat) {
                    toast.error("Conversation limit reached.");
                    setShowPlansModal(true);
                    return false;
                }
                return true;
            }
            case 'image': {
                const hasCards =
                    hasRemaining(usage.image_cards.remaining) ||
                    hasRemaining(usage.addon_cards?.remaining);
                if (!hasCards) {
                    setAddonsModalMode('cards');
                    setShowAddonsModal(true);
                    return false;
                }
                return true;
            }
            case 'audio': {
                if (!usage.audio_enabled) {
                    toast.error("Audio generation not enabled in your plan.");
                    setShowPlansModal(true);
                    return false;
                }
                // Check meditation_duration OR addon_minutes
                const hasMinutes =
                    hasRemaining(usage.meditation_duration.remaining) ||
                    hasRemaining(usage.addon_minutes?.remaining);
                if (!hasMinutes) {
                    setAddonsModalMode('minutes');
                    setShowAddonsModal(true);
                    return false;
                }
                return true;
            }
            case 'video': {
                if (!usage.video_enabled) {
                    toast.error("Video generation not enabled in your plan.");
                    setShowPlansModal(true);
                    return false;
                }
                const hasMinutes =
                    hasRemaining(usage.meditation_duration.remaining) ||
                    hasRemaining(usage.addon_minutes?.remaining);
                if (!hasMinutes) {
                    setAddonsModalMode('minutes');
                    setShowAddonsModal(true);
                    return false;
                }
                return true;
            }
            default:
                return true;
        }
    };

    return (
        <UsageContext.Provider value={{
            usage,
            loading,
            refreshUsage,
            subscription,
            subscriptionLoading,
            refreshSubscription,
            showPlansModal,
            setShowPlansModal,
            showAddonsModal,
            setShowAddonsModal,
            addonsModalMode,
            setAddonsModalMode,
            checkQuota,
            creditsActive,
            showCreditsModal,
            openCreditsModal,
            setShowCreditsModal
        }}>
            {children}
            <PlansModal
                isOpen={showPlansModal}
                onClose={() => setShowPlansModal(false)}
                onSuccess={() => {
                    refreshUsage();
                    refreshSubscription();
                }}
                subscription={subscription}
            />
            <CreditsModal
                open={showCreditsModal}
                onClose={() => setShowCreditsModal(false)}
                onPurchased={() => refreshUsage()}
                reason={creditsReason}
            />
            <AddonsModal
                isOpen={showAddonsModal}
                onClose={() => setShowAddonsModal(false)}
                onSuccess={() => {
                    refreshUsage();
                }}
                type={addonsModalMode}
            />
        </UsageContext.Provider>
    );
};

export const useUsage = () => {
    const context = useContext(UsageContext);
    if (context === undefined) {
        throw new Error('useUsage must be used within a UsageProvider');
    }
    return context;
};
