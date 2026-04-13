import { useQuery } from '@tanstack/react-query';
import { usageAPI, addonAPI, plansAPI } from '@/apis/api';
import { Addon, Plan } from '@/apis/wire';
import { useAuth } from '@/contexts/AuthContext';

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
    meditation_duration: {
        limit: number;
        used: number;
        remaining: number;
    };
    conversations: {
        limit: string | number;
        used: number;
        remaining: string | number;
    };
    addon_cards: {
        limit: number;
        used: number;
        remaining: number;
    };
    addon_minutes: {
        limit: number;
        used: number;
        remaining: number;
    };
    audio_enabled: boolean;
    video_enabled: boolean;
}

export const useUsageQuery = () => {
    const { user } = useAuth();
    return useQuery({
        queryKey: ['billing-usage', user?.id],
        queryFn: async () => {
            const data = await usageAPI.getUsage();
            return data as UsageData;
        },
        enabled: !!user,
        staleTime: 0,              // Always refetch — usage must be current
        gcTime: 1000 * 60 * 5,    // Keep in cache 5 min (but always re-validate)
    });
};

export const useAddonsQuery = () => {
    const { user } = useAuth();
    return useQuery({
        queryKey: ['billing-addons'],
        queryFn: async () => {
            return await addonAPI.getAddons();
        },
        enabled: !!user,
        staleTime: 1000 * 60 * 10, // 10 minutes
        gcTime: 1000 * 60 * 60, // 1 hour
    });
};

export const usePlansQuery = () => {
    const { user } = useAuth();
    return useQuery({
        queryKey: ['billing-plans'],
        queryFn: async () => {
            return await plansAPI.getPlans();
        },
        enabled: !!user,
        staleTime: 1000 * 60 * 60, // 1 hour
        gcTime: 1000 * 60 * 60 * 24, // 24 hours
    });
};
