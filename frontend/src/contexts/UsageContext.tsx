import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { usageAPI, paymentAPI } from '@/apis/api';
import { useAuth } from './AuthContext';
import { SubscriptionResponse } from '@/apis/wire';
import { PlansModal } from '@/components/billing/PlansModal';
import { AddonsModal } from '@/components/billing/AddonsModal';
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
            // Fetch as soon as user is authenticated — don't wait for profile.
            // This ensures usage shows immediately on registration and login.
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
            checkQuota
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
