// SubscriptionScreen.tsx
import React, { useState, useEffect } from 'react';
import { ArrowLeft, CheckCircle, Loader2, Image as ImageIcon, Heart, MessageSquare } from 'lucide-react';
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { PwycModal } from './PwycModal';
import { FeatureListItem } from './FeatureListItem';
import { SimpleProgressBar } from './SimpleProgressBar';
import { paymentAPI, plansAPI, usageAPI, addonAPI } from "@/apis/api";
import { toast } from "sonner";
import { UpgradePreviewModal } from './UpgradePreviewModal';
import { UpgradePreview, Addon, SubscriptionResponse, Subscription } from '@/apis/wire';
import { SubscriptionHistory } from './SubscriptionHistory';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { INR_PRICES, isIndianUser } from './plansData';

interface UsageData {
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

interface LocalPlan {
    id: string | number;
    name: string;
    description: string;
    active: boolean;
    is_free: boolean;
    is_recommended?: boolean;
    plan_type: string;
    billing_cycle: string;
    chat_limit: string;
    card_limit: number;
    max_meditation_duration: number;
    is_audio?: boolean;
    is_video?: boolean;
    features: Array<{
        id: number;
        feature_text: string;
        plan_id: number;
    }>;
    prices: Array<{
        id: number;
        currency: string;
        price: number;
        plan_id: number;
    }>;
    polar_plan_id?: string;
}

export const SubscriptionScreen: React.FC = () => {
    const { user, userProfile } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [plans, setPlans] = useState<LocalPlan[]>([]);
    const [showPwycModal, setShowPwycModal] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);
    const [selectedMeditationDuration, setSelectedMeditationDuration] = useState<number>(5);
    const [usageData, setUsageData] = useState<UsageData | null>(null);
    const [loadingUsage, setLoadingUsage] = useState(true);
    const [loadingPlans, setLoadingPlans] = useState(true);
    const [upgradePreview, setUpgradePreview] = useState<UpgradePreview | null>(null);
    const [showUpgradeModal, setShowUpgradeModal] = useState(false);
    const [showCancelDialog, setShowCancelDialog] = useState(false);
    const [showRevokeDialog, setShowRevokeDialog] = useState(false);
    const [currentView, setCurrentView] = useState<'plans' | 'history'>('plans');
    const [addons, setAddons] = useState<Addon[]>([]);
    const [loadingAddons, setLoadingAddons] = useState(true);
    const [subscriptionDetails, setSubscriptionDetails] = useState<SubscriptionResponse | null>(null);
    const [billingCycle, setBillingCycle] = useState<'MONTHLY' | 'YEARLY'>('MONTHLY');

    // Fetch plans from API
    useEffect(() => {
        fetchPlans();
        fetchSubscriptionDetails();
    }, []);

    const fetchSubscriptionDetails = async () => {
        try {
            const data = await paymentAPI.getSubscription();
            setSubscriptionDetails(data);
        } catch (error) {
            console.error("Failed to fetch subscription details:", error);
        }
    };

    // Fetch usage data
    useEffect(() => {
        fetchUsageData();
    }, []);

    // Fetch addons
    useEffect(() => {
        fetchAddons();
    }, []);

    // Check for checkout redirect and sync subscription
    useEffect(() => {
        checkForCheckoutRedirect();
    }, [userProfile?.id, location.search]);

    const fetchPlans = async () => {
        try {
            setLoadingPlans(true);
            const fetchedPlans = await plansAPI.getPlans();
            // Filter only active plans
            const activePlans = fetchedPlans.filter((plan: any) => plan.active);
            setPlans(activePlans as LocalPlan[]);
        } catch (error) {
            console.error('Failed to fetch plans:', error);
            toast.error('Failed to load subscription plans');
        } finally {
            setLoadingPlans(false);
        }
    };

    const fetchAddons = async () => {
        try {
            setLoadingAddons(true);
            const fetchedAddons = await addonAPI.getAddons();
            setAddons(fetchedAddons);
        } catch (error) {
            console.error('Failed to fetch addons:', error);
            // toast.error('Failed to load add-ons'); // Non-critical
        } finally {
            setLoadingAddons(false);
        }
    };

    const fetchUsageData = async () => {
        try {
            setLoadingUsage(true);
            const data = await usageAPI.getUsage();
            setUsageData(data as UsageData);
        } catch (error) {
            console.error('Failed to fetch usage data:', error);
            toast.error('Failed to load usage data');
        } finally {
            setLoadingUsage(false);
        }
    };

    const checkForCheckoutRedirect = async () => {
        // Check URL parameters for checkout success
        const urlParams = new URLSearchParams(location.search);
        const checkoutSuccess = urlParams.get('checkout_success');
        const checkoutCancelled = urlParams.get('checkout_cancelled');
        const sessionId = urlParams.get('session_id');
        const customerSessionToken = urlParams.get('customer_session_token');

        // Handle cancelled checkout
        if (checkoutCancelled === 'true') {
            toast.info("Checkout was cancelled");
            // Clear URL parameters
            navigate(location.pathname, { replace: true });
            return;
        }

        // Handle successful checkout
        if ((checkoutSuccess === 'true' || sessionId || customerSessionToken) && userProfile?.id) {
            try {
                // Show loading
                setIsSyncing(true);
                toast.info("Processing your subscription update...");

                // Wait for backend webhook to process
                await new Promise(resolve => setTimeout(resolve, 3000));

                // Sync subscription with retry
                await syncSubscription(userProfile.id);

                // Clear URL parameters
                const newUrl = window.location.pathname;
                window.history.replaceState({}, document.title, newUrl);

                toast.success("Subscription updated successfully!");

            } catch (error) {
                console.error("Failed to sync after checkout:", error);
                toast.error("Failed to sync subscription. Please refresh the page.");
            } finally {
                setIsSyncing(false);
            }
        }
    };

    const syncSubscription = async (userId: string) => {
        try {
            // Check if sync endpoint exists
            if (paymentAPI.syncSubscription) {
                await paymentAPI.syncSubscription(userId);
            }

            // Refresh usage data
            await fetchUsageData();

            // Refresh plans
            await fetchPlans();

        } catch (error) {
            console.error("Subscription sync failed:", error);
            throw error;
        }
    };

    // Get the current plan based on usage data or subscription
    const getCurrentPlanDetails = () => {
        // Priority 1: Use subscription details from API
        if (subscriptionDetails?.plan) {
            const apiPlan = plans.find(p => String(p.id) === String(subscriptionDetails.plan!.id));
            if (apiPlan) return apiPlan;
            // If local plan not found but we have subscription plan data, return it (mapped to LocalPlan structure if needed, or just partial)
            // For now, let's assume local plans are synced.
        }

        if (!usageData || plans.length === 0) return null;

        // Try to find plan by name from usage data
        let currentPlan = plans.find(p =>
            p.name.toLowerCase() === usageData.plan_name.toLowerCase()
        );

        // If not found by name, try to find by type and features
        if (!currentPlan) {
            currentPlan = plans.find(p =>
                p.plan_type === usageData.plan_type &&
                p.is_free === (usageData.plan_type === 'FREE')
            );
        }

        // If still not found, return the free plan
        if (!currentPlan) {
            currentPlan = plans.find(p => p.is_free);
        }

        return currentPlan;
    };

    // Filter plans based on selected billing cycle
    const getFilteredPlans = () => {
        const freePlan = plans.find(p => p.is_free);
        const paidPlans = plans.filter(p => !p.is_free && p.billing_cycle === billingCycle);

        // Sort paid plans: BASIC first then PRO (to match the requested order: FREE, BASIC, PRO)
        const sortedPaid = [...paidPlans].sort((a, b) => {
            if (a.plan_type === 'BASIC' && b.plan_type === 'PRO') return -1;
            if (a.plan_type === 'PRO' && b.plan_type === 'BASIC') return 1;
            return 0;
        });

        return { freePlan, paidPlans: sortedPaid };
    };

    const currentPlanDetails = getCurrentPlanDetails();
    const { freePlan, paidPlans } = getFilteredPlans();
    const currentPlanId = currentPlanDetails?.id;

    // Detect Indian users by country code or phone number prefix
    const indiaUser = isIndianUser(userProfile?.country_code, userProfile?.phone_number);
    const currencySymbol = indiaUser ? '₹' : '$';

    // Helper to get price for current currency
    const getPlanPrice = (plan: LocalPlan): number => {
        if (indiaUser) {
            const inrKey = `${plan.name}-${plan.billing_cycle}`;
            return INR_PRICES[inrKey]?.price ?? 0;
        }
        const priceObj = plan.prices.find(p => p.currency === 'USD');
        return priceObj ? priceObj.price : 0;
    };

    // Helper to get formatted price display (e.g. "₹2,699" or "$39.99")
    const getPlanPriceDisplay = (plan: LocalPlan): string => {
        if (indiaUser) {
            const inrKey = `${plan.name}-${plan.billing_cycle}`;
            return INR_PRICES[inrKey]?.display ?? '—';
        }
        const priceObj = plan.prices.find(p => p.currency === 'USD');
        return priceObj ? `$${priceObj.price}` : '—';
    };

    // For yearly plans, per-month equivalent label
    const getPerMonthLabel = (plan: LocalPlan): string | null => {
        if (plan.billing_cycle !== 'YEARLY') return null;
        if (indiaUser) {
            const inrKey = `${plan.name}-${plan.billing_cycle}`;
            return INR_PRICES[inrKey]?.perMonth ?? null;
        }
        const priceObj = plan.prices.find(p => p.currency === 'USD');
        return priceObj ? `$${(priceObj.price / 12).toFixed(2)}/mo` : null;
    };

    // Add-on pricing logic
    const getCardPrice = () => {
        if (!currentPlanDetails) return 2.5;
        if (currentPlanDetails.is_free) return 2.5;
        if (currentPlanDetails.plan_type === 'BASIC') return 1.5;
        return 1.0; // PRO plan
    };

    const getMeditationPrice = (duration: number) => {
        if (!currentPlanDetails) return 5;
        if (currentPlanDetails.is_free) {
            if (duration <= 5) return 5;
            if (duration <= 10) return 7;
            if (duration <= 15) return 9;
            return 10;
        }
        if (currentPlanDetails.plan_type === 'BASIC') {
            if (duration <= 5) return 3;
            if (duration <= 10) return 5;
            if (duration <= 15) return 7;
            return 8;
        }
        // PRO plan
        if (duration <= 5) return 2;
        if (duration <= 10) return 3;
        if (duration <= 15) return 4;
        return 5;
    };

    const currentCardPrice = getCardPrice();
    const currentMeditationPrice = getMeditationPrice(selectedMeditationDuration);

    // Determine the type of action for a target plan relative to current plan
    const getPlanActionType = (plan: LocalPlan): 'CURRENT' | 'UPGRADE' | 'DOWNGRADE' | 'SWITCH_CYCLE' | 'RENEW' => {
        if (!currentPlanDetails) return 'UPGRADE'; // Treat as upgrade/subscribe if no current plan

        if (currentPlanDetails.id === plan.id) {
            // If subscription is cancelling, show RENEW option
            if (subscriptionDetails?.subscription?.cancel_at_period_end || subscriptionDetails?.subscription?.status === 'canceled') {
                return 'RENEW';
            }
            return 'CURRENT';
        }

        const getTier = (p: LocalPlan) => {
            if (p.is_free) return 0;
            if (p.plan_type === 'BASIC') return 1;
            if (p.plan_type === 'PRO') return 2;
            return 0;
        };

        const currentTier = getTier(currentPlanDetails);
        const targetTier = getTier(plan);

        if (targetTier > currentTier) return 'UPGRADE';
        if (targetTier < currentTier) return 'DOWNGRADE';

        // Same tier, different billing cycle
        if (currentPlanDetails.billing_cycle !== plan.billing_cycle) {
            return 'SWITCH_CYCLE';
        }

        return 'CURRENT';
    };

    const handleUpgradeClick = async (planId: string | number) => {
        setIsProcessing(true);
        try {
            const plan = plans.find(p => String(p.id) === String(planId));

            if (!plan) {
                toast.error("Plan not found");
                return;
            }

            const actionType = getPlanActionType(plan);
            if (actionType === 'DOWNGRADE' || actionType === 'SWITCH_CYCLE') {
                toast.error("Please contact support to change your plan.");
                return;
            }

            const userId = userProfile?.id;
            if (!userId) {
                toast.error("Unable to identify user");
                return;
            }

            // ── Indian users → Razorpay ──────────────────────────────────────
            if (indiaUser && !plan.is_free) {
                const successUrl = window.location.href;
                const response = await paymentAPI.createRazorpayCheckoutSession(
                    Number(plan.id),
                    userId,
                    successUrl,
                );
                const checkoutUrl = response?.data?.checkout_url || response?.checkout_url;
                if (checkoutUrl) {
                    window.location.href = checkoutUrl;
                } else {
                    toast.error("Failed to start Razorpay payment session");
                }
                return;
            }
            // ── Global users → Polar ─────────────────────────────────────────

            if (!plan.polar_plan_id) {
                toast.error("This plan is not available for subscription");
                return;
            }
            console.log("fsfsd", actionType);

            // If it's an upgrade, show the preview modal
            if (actionType === 'UPGRADE' && !currentPlanDetails?.is_free) {
                try {
                    const preview = await paymentAPI.getUpgradePreview(plan.polar_plan_id, userId);
                    setUpgradePreview(preview);
                    setShowUpgradeModal(true);
                    return; // Wait for user confirmation in modal
                } catch (error) {
                    console.error("Failed to fetch upgrade preview:", error);
                    toast.error("Failed to calculate upgrade preview. Proceeding to checkout...");
                }
            }

            // For new subscriptions (from free) or if preview failed, go directly to checkout
            await proceedToCheckout(plan.polar_plan_id, userId);

        } catch (error: any) {
            console.error("Subscription error:", error);
            handleSubError(error);
        } finally {
            setIsProcessing(false);
        }
    };

    const proceedToCheckout = async (polarPlanId: string, userId: string) => {
        const successUrl = window.location.href;
        const response = await paymentAPI.createCheckoutSession(
            polarPlanId,
            userId,
            successUrl
        );

        const checkoutUrl = response?.data?.checkout_url || response?.checkout_url || response?.url;

        if (checkoutUrl) {
            window.location.href = checkoutUrl;
        } else {
            toast.error("Failed to start payment session");
        }
    };

    const handleConfirmUpgrade = async () => {
        if (!upgradePreview || !userProfile?.id) return;

        setIsProcessing(true);
        try {
            // Find the target plan to get its polar_plan_id
            const targetPlan = plans.find(p => p.name === upgradePreview.new_plan);
            if (!targetPlan?.polar_plan_id) {
                toast.error("Target plan not found");
                return;
            }

            // Use immediate upgrade patch API
            await paymentAPI.upgradeSubscription(userProfile.id, targetPlan.polar_plan_id);

            setShowUpgradeModal(false);
            toast.success(`Successfully upgraded to ${targetPlan.name}!`);

            // Refresh usage and plans
            await syncSubscription(userProfile.id);
        } catch (error: any) {
            console.error("Upgrade confirmation error:", error);
            handleSubError(error);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleCancelSubscription = async () => {
        if (!userProfile?.id) return;
        setShowCancelDialog(true);
    };

    const confirmCancelSubscription = async () => {
        if (!userProfile?.id) return;
        setShowCancelDialog(false);
        setIsProcessing(true);
        try {
            const subId = subscriptionDetails?.subscription?.id || subscriptionDetails?.subscription?.polar_subscription_id;
            if (!subId) {
                toast.error("No active subscription found to cancel");
                return;
            }
            await paymentAPI.cancelSubscription(userProfile.id, subId);
            toast.success("Subscription cancelled successfully.");
            await syncSubscription(userProfile.id);
        } catch (error: any) {
            console.error("Cancellation error:", error);
            handleSubError(error);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleRevokeSubscription = async () => {
        if (!userProfile?.id) return;
        setShowRevokeDialog(true);
    };

    const confirmRevokeSubscription = async () => {
        if (!userProfile?.id) return;
        setShowRevokeDialog(false);
        setIsProcessing(true);
        try {
            await paymentAPI.revokeSubscription(userProfile.id);
            toast.success("Subscription revoked immediately.");
            await syncSubscription(userProfile.id);
        } catch (error: any) {
            console.error("Revocation error:", error);
            handleSubError(error);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleSubError = (error: any) => {
        if (error.response?.status === 401) {
            toast.error("Please log in to continue");
        } else if (error.response?.status === 400) {
            toast.error(error.response.data?.message || "Invalid request");
        } else {
            toast.error("Failed to process subscription request");
        }
    };

    const handleAddOnClick = async (type: string, quantity: number, duration?: number, addonId?: number) => {
        if (!userProfile?.id) {
            toast.error("Please log in to purchase add-ons");
            return;
        }

        setIsProcessing(true);
        try {
            let targetAddonId = addonId;

            // If no explicit addonId, try to find it based on type and duration
            if (!targetAddonId) {
                if (type === 'card') {
                    const cardAddon = addons.find(a => a.unit_type === 'CARDS');
                    if (cardAddon) targetAddonId = cardAddon.id;
                } else if (type === 'meditation' && duration) {
                    const meditationAddon = addons.find(a => a.unit_type === 'MINUTES' && a.quantity === duration);
                    if (meditationAddon) targetAddonId = meditationAddon.id;
                }
            }

            if (!targetAddonId) {
                toast.error("Add-on not found");
                return;
            }

            const successUrl = window.location.href;
            const response = await paymentAPI.subscribeAddon(targetAddonId, userProfile.id, successUrl);
            if (response.success && response.checkout_url) {
                window.location.href = response.checkout_url;
            } else {
                toast.error(response.message || "Failed to initiate add-on purchase");
            }
        } catch (error) {
            console.error("Add-on purchase error:", error);
            toast.error("Failed to process add-on request");
        } finally {
            setIsProcessing(false);
        }
    };

    const getRenewalDateText = () => {
        if (subscriptionDetails?.subscription) {
            const sub = subscriptionDetails.subscription;
            const date = new Date(sub.current_period_end).toLocaleDateString();

            if (sub.status === 'canceled' || sub.cancel_at_period_end) {
                return `Ends on ${date}`;
            }
            return `Renews on ${date}`;
        }

        if (currentPlanDetails?.is_free) return "Resources are available via add-ons.";
        return "Quota resets on next billing cycle";
    };

    const handleBackClick = () => {
        if (currentView === 'history') {
            setCurrentView('plans');
        } else {
            navigate(-1);
        }
    };

    if (loadingUsage || loadingPlans) {
        return (
            <div className="min-h-screen bg-[#F5F0EC] flex flex-col items-center justify-center">
                <Loader2 className="w-12 h-12 animate-spin text-[#472b20] mb-4" />
                <p className="text-[#472b20]/60 font-light">Loading subscription data...</p>
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto bg-[#F5F0EC] p-4 sm:p-6 lg:p-8 flex flex-col">
            {showPwycModal && user && (
                <PwycModal
                    userEmail={user.email || ''}
                    userName={userProfile?.name || 'User'}
                    hasPendingApplication={false}
                    onClose={() => setShowPwycModal(false)}
                />
            )}

            <header className="max-w-6xl mx-auto flex items-center justify-between w-full mb-8">
                <Button variant="ghost" size="icon" onClick={handleBackClick} className="rounded-full hover:bg-[#ECE5DF]">
                    <ArrowLeft className="w-6 h-6 text-[#472b20]" />
                </Button>
                {currentView === 'plans' && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentView('history')}
                        className="text-[#472b20] border-[#ECE5DF] hover:bg-[#ECE5DF] font-medium "
                    >
                        View Payment History
                    </Button>
                )}
            </header>

            <main className="flex-grow flex flex-col items-center pt-4 w-full">
                {currentView === 'history' ? (
                    <SubscriptionHistory onBack={() => setCurrentView('plans')} />
                ) : (
                    <>
                        {/* Current Usage Section */}
                        <div className="w-full max-w-6xl mb-12 bg-white/60 backdrop-blur-sm p-6 rounded-2xl shadow-sm border border-[#ECE5DF]">
                            <div className="flex justify-between items-start mb-6">
                                <h2 className="text-2xl  font-bold text-[#472b20]">Current Usage & Plan</h2>
                                {isSyncing && (
                                    <div className="flex items-center gap-2 text-[#472b20]/60">
                                        <Loader2 className="w-4 h-4 animate-spin text-[#472b20]" />
                                        <span className="text-sm font-light">Syncing subscription...</span>
                                    </div>
                                )}
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div>
                                    <div className="flex items-center gap-3 mb-4">
                                        <div className={`w-3 h-3 rounded-full ${currentPlanDetails?.is_free ? 'bg-green-500' : 'bg-[#472b20]'}`} />
                                        <p className="text-sm text-[#472b20]/60 font-light">Active Plan</p>
                                    </div>
                                    <p className="text-xl  font-bold text-[#472b20] capitalize">
                                        {currentPlanDetails?.name || usageData?.plan_name || 'Free'}
                                    </p>
                                    <p className="text-sm text-[#472b20]/40 mt-2 font-light">{getRenewalDateText()}</p>

                                    {/* Media Access */}
                                    {usageData && (
                                        <div className="mt-6">
                                            <p className="text-sm text-[#472b20]/60 mb-2 font-light">Media Access</p>
                                            <div className="flex gap-4">
                                                <div className={`flex items-center gap-2 ${usageData.audio_enabled ? 'text-[#472b20]' : 'text-[#472b20]/30'}`}>
                                                    <CheckCircle className="w-4 h-4" />
                                                    <span className="text-sm font-medium">Audio</span>
                                                </div>
                                                <div className={`flex items-center gap-2 ${usageData.video_enabled ? 'text-[#472b20]' : 'text-[#472b20]/30'}`}>
                                                    <CheckCircle className="w-4 h-4" />
                                                    <span className="text-sm font-medium">Video</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Cancellation & Revocation Buttons */}
                                    {currentPlanDetails && !currentPlanDetails.is_free &&
                                        subscriptionDetails?.subscription?.status === 'active' &&
                                        !subscriptionDetails?.subscription?.cancel_at_period_end && (
                                            <div className="mt-8 flex flex-col gap-3">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={handleCancelSubscription}
                                                    disabled={isProcessing}
                                                    className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600 font-medium  w-fit"
                                                >
                                                    {isProcessing ? (
                                                        <>
                                                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                                            Processing...
                                                        </>
                                                    ) : (
                                                        "Cancel Subscription"
                                                    )}
                                                </Button>
                                                <p className="text-[10px] text-[#472b20]/40 font-light">
                                                    Note: Cancellation takes effect at the end of the cycle.
                                                </p>
                                            </div>
                                        )}
                                </div>

                                <div className="space-y-6">
                                    <div>
                                        {usageData && (
                                            <>
                                                <p className=" font-semibold text-[#472b20] mb-3 text-base">Conversation Quota</p>
                                                <div className="space-y-4 pl-4 border-l-2 border-[#ECE5DF] mb-6">
                                                    <SimpleProgressBar
                                                        label="Conversations"
                                                        icon={<MessageSquare className="w-4 h-4 text-[#472b20]/60" />}
                                                        used={usageData.conversations.used}
                                                        total={usageData.conversations.limit}
                                                        colorClass="bg-[#472b20]"
                                                    />
                                                </div>

                                                <p className=" font-semibold text-[#472b20] mb-3 text-base">Monthly Quota</p>
                                                <div className="space-y-4 pl-4 border-l-2 border-[#ECE5DF]">
                                                    <SimpleProgressBar
                                                        label="Contemplation Cards"
                                                        icon={<ImageIcon className="w-4 h-4 text-[#472b20]/60" />}
                                                        used={usageData.image_cards.used}
                                                        total={usageData.image_cards.limit}
                                                        colorClass="bg-[#472b20]"
                                                    />

                                                    <SimpleProgressBar
                                                        label="Meditation Minutes"
                                                        icon={<Heart className="w-4 h-4 text-[#472b20]/60" />}
                                                        used={usageData.meditation_duration.used}
                                                        total={usageData.meditation_duration.limit}
                                                        colorClass="bg-[#472b20]"
                                                    />
                                                </div>
                                            </>
                                        )}
                                        <p className=" font-semibold text-[#472b20] my-3 text-base">Add-on Quota</p>

                                        <div className="space-y-4 pl-4 border-l-2 border-[#ECE5DF]">
                                            {usageData && (
                                                <>


                                                    {(usageData.addon_cards?.limit > 0 || usageData.addon_cards?.used > 0) && (
                                                        <SimpleProgressBar
                                                            label="Add-on Cards"
                                                            icon={<ImageIcon className="w-4 h-4 text-teal-500" />}
                                                            used={usageData.addon_cards.used}
                                                            total={usageData.addon_cards.limit}
                                                            colorClass="bg-teal-500"
                                                        />
                                                    )}

                                                    {(usageData.addon_minutes?.limit > 0 || usageData.addon_minutes?.used > 0) && (
                                                        <SimpleProgressBar
                                                            label="Add-on Meditations"
                                                            icon={<Heart className="w-4 h-4 text-red-500" />}
                                                            used={usageData.addon_minutes.used}
                                                            total={usageData.addon_minutes.limit}
                                                            colorClass="bg-red-500"
                                                        />
                                                    )}
                                                </>
                                            )}
                                        </div>
                                        {currentPlanDetails?.is_free && (
                                            <p className="text-sm text-[#472b20]/60 mt-4 font-light italic">
                                                Free plan has limited quota. Purchase add-ons for more or upgrade to a paid plan.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Plans Header */}
                        <div className="text-center mb-4">
                            <h1 className="text-4xl font-heading font-bold text-[#472b20]">Plans & Pricing</h1>
                            <p className="text-[#472b20]/60 mt-2 max-w-xl mx-auto font-light">
                                Subscriptions reset monthly. Prices are indicative.
                            </p>
                            {indiaUser && (
                                <div className="mt-3 inline-flex items-center gap-2 bg-orange-50 border border-orange-200 text-orange-700 text-sm font-medium px-4 py-1.5 rounded-full">
                                    🇮🇳 Prices shown in INR — 20% India discount applied
                                </div>
                            )}
                        </div>

                        {/* Billing Toggle (Pill) */}
                        <div className="flex justify-center mb-12">
                            <div className="bg-[#ECE5DF] p-1 rounded-full flex items-center shadow-inner">
                                <button
                                    onClick={() => setBillingCycle('MONTHLY')}
                                    className={`px-6 py-2 rounded-full text-sm font-semibold transition-all duration-300 ${billingCycle === 'MONTHLY' ? 'bg-white text-[#472b20] shadow-sm' : 'text-[#472b20]/40'}`}
                                >
                                    Monthly
                                </button>
                                <button
                                    onClick={() => setBillingCycle('YEARLY')}
                                    className={`px-6 py-2 rounded-full text-sm font-semibold transition-all duration-300 ${billingCycle === 'YEARLY' ? 'bg-white text-[#472b20] shadow-sm' : 'text-[#472b20]/40'}`}
                                >
                                    Yearly
                                </button>
                            </div>
                        </div>

                        {/* Plans Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-6xl mb-16">
                            {/* Free Plan */}
                            {freePlan && (
                                <div
                                    className={`p-8 rounded-[2rem] border-2 flex flex-col bg-white ${currentPlanDetails?.id === freePlan.id
                                        ? 'border-[#D05E2D] shadow-lg'
                                        : 'border-transparent shadow-sm'
                                        }`}
                                >
                                    <h2 className="text-2xl font-heading font-bold text-[#472b20] mb-2">{freePlan.name}</h2>
                                    <div className="my-2">
                                        <span className="text-5xl font-heading font-bold text-[#472b20]">Free</span>
                                    </div>
                                    <ul className="space-y-4 mb-8 flex-grow">
                                        {freePlan.features.map((feature, index) => (
                                            <FeatureListItem key={feature.id || index} text={feature.feature_text} isPremium={false} />
                                        ))}
                                    </ul>
                                    {currentPlanDetails?.id === freePlan.id ? (
                                        <div className="w-full py-4 text-center bg-[#FDF4EF] text-[#D05E2D] font-bold rounded-xl mt-auto">
                                            Your Current Plan
                                        </div>
                                    ) : (
                                        <div className="mt-auto"></div>
                                    )}
                                    <div className="mt-4 border-t border-[#ECE5DF] pt-4 text-center">
                                        <p className="text-xs text-[#472b20]/60 mb-1 font-light italic">Facing financial hardship?</p>
                                        <button onClick={() => setShowPwycModal(true)} className="text-[#472b20] text-sm font-semibold hover:underline">
                                            Apply for 'Pay What You Can' Access
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Paid Plans (Pro, Basic) */}
                            {paidPlans.map(plan => {
                                const price = getPlanPrice(plan);
                                const actionType = getPlanActionType(plan);
                                const isCurrent = actionType === 'CURRENT';

                                let buttonContent = isCurrent ? "Your Current Plan" : "Subscribe";
                                let buttonClass = "";

                                if (isCurrent) {
                                    buttonClass = "bg-[#FDF4EF] text-[#D05E2D] hover:bg-[#FDF4EF]";
                                } else if (actionType === 'RENEW') {
                                    buttonContent = "Renew Subscription";
                                    buttonClass = "bg-[#D05E2D] text-white hover:bg-[#B85228]";
                                } else if (actionType === 'SWITCH_CYCLE') {
                                    buttonContent = `Update to ${plan.billing_cycle.toLowerCase()}`;
                                    buttonClass = "bg-[#D05E2D] text-white hover:bg-[#B85228]";
                                } else if (actionType === 'DOWNGRADE') {
                                    buttonContent = `Downgrade to ${plan.name}`;
                                    buttonClass = "bg-gray-50 text-gray-400 hover:bg-gray-100";
                                } else {
                                    buttonContent = actionType === 'UPGRADE' ? `Upgrade to ${plan.name}` : `Subscribe to ${plan.name}`;
                                    buttonClass = "bg-[#D05E2D] text-white hover:bg-[#B85228]";
                                }

                                return (
                                    <div
                                        key={plan.id}
                                        className={`p-8 rounded-xl border-2 flex flex-col bg-white ${isCurrent
                                            ? 'border-[#D05E2D] shadow-lg'
                                            : 'border-transparent shadow-sm'
                                            } relative`}
                                    >
                                        <h2 className="text-2xl font-heading font-bold text-[#472b20] mb-2">{plan.name}</h2>
                                        <div className="my-2">
                                            <span className="text-5xl font-heading font-bold text-[#472b20]">
                                                {getPlanPriceDisplay(plan)}
                                            </span>
                                            <span className="text-[#472b20]/60 font-light">
                                                /{plan.billing_cycle.toLowerCase() === 'monthly' ? 'month' : 'year'}
                                            </span>
                                            {getPerMonthLabel(plan) && (
                                                <p className="text-xs text-[#472b20]/50 mt-1 font-light">
                                                    ≈ {getPerMonthLabel(plan)} billed annually
                                                </p>
                                            )}
                                        </div>
                                        <ul className="space-y-4 mb-8 flex-grow">
                                            {plan.features.map((feature, index) => (
                                                <FeatureListItem
                                                    key={feature.id || index}
                                                    text={feature.feature_text}
                                                    isPremium={true}
                                                />
                                            ))}
                                        </ul>
                                        <Button
                                            onClick={() => handleUpgradeClick(plan.id)}
                                            disabled={(isProcessing || actionType === 'DOWNGRADE') && !isCurrent}
                                            className={`w-full py-7 rounded-xl font-bold shadow-none transition-colors border-none ${buttonClass} mt-auto shadow-sm`}
                                        >
                                            {isProcessing && !isCurrent ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : buttonContent}
                                        </Button>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Add-ons Section */}
                        <div className="w-full max-w-6xl">
                            <div className="text-center mb-8">
                                <h2 className="text-3xl font-bold text-gray-900">Add-ons (Pay As You Go)</h2>
                                <p className="text-gray-500 mt-2">Reached your limit or on the free plan? Purchase one-time credits.</p>
                            </div>

                            {loadingAddons ? (
                                <div className="flex justify-center p-12">
                                    <Loader2 className="w-8 h-8 animate-spin text-orange-600" />
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                                    {/* Card Add-on */}
                                    {addons.filter(a => a.unit_type === 'CARDS').map(addon => (
                                        <div key={addon.id} className="w-full text-center p-8 bg-white/60 backdrop-blur-sm rounded-2xl shadow-sm border border-[#ECE5DF] hover:border-[#472b20]/30 transition-all duration-300 flex flex-col">
                                            <div className="flex justify-center mb-4">
                                                <div className="w-16 h-16 bg-[#F5F0EC] rounded-full flex items-center justify-center">
                                                    <ImageIcon className="w-8 h-8 text-[#472b20]" />
                                                </div>
                                            </div>
                                            <h3 className="text-xl  font-semibold text-[#472b20]">{addon.name}</h3>
                                            <p className="text-4xl  font-bold my-4 text-[#472b20]">{currencySymbol}{addon.price_usd}</p>
                                            <p className="text-[#472b20]/60 text-sm flex-grow mb-6 font-light">{addon.description}<br />Single-use credit per card.</p>
                                            <Button
                                                onClick={() => handleAddOnClick('card', 1, undefined, addon.id)}
                                                disabled={isProcessing}
                                                className="w-full bg-[#472b20] hover:bg-[#5d3a2c] text-white py-6 rounded-xl  font-semibold mt-auto shadow-md"
                                            >
                                                {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : `Purchase ${addon.name}`}
                                            </Button>
                                        </div>
                                    ))}

                                    {/* Meditation Add-on with Duration Selector */}
                                    {addons.some(a => a.unit_type === 'MINUTES') && (
                                        <div key="meditation-addon" className="w-full text-center p-8 bg-white/60 backdrop-blur-sm rounded-2xl shadow-sm border border-[#ECE5DF] hover:border-[#472b20]/30 transition-all duration-300 flex flex-col">
                                            <div className="flex justify-center mb-4">
                                                <div className="w-16 h-16 bg-[#F5F0EC] rounded-full flex items-center justify-center">
                                                    <Heart className="w-8 h-8 text-[#472b20]" />
                                                </div>
                                            </div>
                                            <h3 className="text-xl  font-semibold text-[#472b20]">Guided Meditation</h3>

                                            <div className="mb-4">
                                                <label className="block text-sm  font-medium text-[#472b20]/80 mb-2">Select Duration</label>
                                                <div className="flex justify-center gap-2">
                                                    {addons
                                                        .filter(a => a.unit_type === 'MINUTES')
                                                        .sort((a, b) => a.quantity - b.quantity)
                                                        .map(addon => (
                                                            <button
                                                                key={addon.id}
                                                                onClick={() => setSelectedMeditationDuration(addon.quantity)}
                                                                className={`px-3 py-1 text-sm rounded-lg border  transition-colors ${selectedMeditationDuration === addon.quantity ? 'bg-[#472b20] text-white border-[#472b20]' : 'bg-white text-[#472b20]/60 border-[#ECE5DF] hover:border-[#472b20]/30'}`}
                                                            >
                                                                {addon.quantity} min
                                                            </button>
                                                        ))}
                                                </div>
                                            </div>

                                            {(() => {
                                                const selectedAddon = addons.find(a => a.unit_type === 'MINUTES' && a.quantity === selectedMeditationDuration) || addons.find(a => a.unit_type === 'MINUTES');
                                                if (!selectedAddon) return null;

                                                return (
                                                    <>
                                                        <p className="text-4xl  font-bold my-4 text-[#472b20]">{currencySymbol}{selectedAddon.price_usd}</p>
                                                        <p className="text-[#472b20]/60 text-sm flex-grow mb-6 font-light">{selectedAddon.description}<br />Single-use meditation credit.</p>
                                                        <Button
                                                            onClick={() => handleAddOnClick('meditation', 1, selectedAddon.quantity, selectedAddon.id)}
                                                            disabled={isProcessing}
                                                            className="w-full bg-[#472b20] hover:bg-[#5d3a2c] text-white py-6 rounded-xl  font-semibold mt-auto shadow-md"
                                                        >
                                                            {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : `Purchase ${selectedAddon.name}`}
                                                        </Button>
                                                    </>
                                                );
                                            })()}
                                        </div>
                                    )}

                                </div>
                            )}
                        </div>
                    </>
                )}
            </main>

            {showUpgradeModal && upgradePreview && (
                <UpgradePreviewModal
                    preview={upgradePreview}
                    isProcessing={isProcessing}
                    onConfirm={handleConfirmUpgrade}
                    onClose={() => setShowUpgradeModal(false)}
                />
            )}

            {/* Confirmation Dialogs */}
            <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Cancel Subscription?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to cancel your subscription? You will lose access to premium features at the end of your current billing cycle.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmCancelSubscription} className="bg-red-600 hover:bg-red-700">
                            Confirm Cancellation
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={showRevokeDialog} onOpenChange={setShowRevokeDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle className="text-red-600">Revoke Subscription Immediately?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will immediately terminate your access to all premium features. This action cannot be undone.
                            Only use this if you want to stop service right now.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Wait, Go Back</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmRevokeSubscription} className="bg-red-600 hover:bg-red-700">
                            Revoke Immediately
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
};
