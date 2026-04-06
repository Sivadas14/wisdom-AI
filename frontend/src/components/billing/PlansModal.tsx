import React, { useState, useEffect } from 'react';
import { X, Loader2, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { plansAPI, paymentAPI, usageAPI } from '@/apis/api';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { FeatureListItem } from '../subscription/FeatureListItem';
import { UpgradePreviewModal } from '../subscription/UpgradePreviewModal';
import { DowngradePreviewModal } from '../subscription/DowngradePreviewModal';
import { UpgradePreview, DowngradePreview } from '@/apis/wire';
import { useUsageQuery, usePlansQuery, UsageData } from '@/hooks/useBillingData';

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
    is_video: boolean;
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


import { SubscriptionResponse } from '@/apis/wire';

interface PlansModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: () => void;
    subscription?: SubscriptionResponse | null;
}

// Helper Component for Plan Cards
const PlanCard: React.FC<{
    plan: LocalPlan;
    isCurrent: boolean;
    actionType: string;
    onAction: () => void;
    isProcessing: boolean;
    currencySymbol: string;
    price: number;
}> = ({ plan, isCurrent, actionType, onAction, isProcessing, currencySymbol, price }) => {
    let buttonText = 'Subscribe';
    let buttonClass = 'bg-orange-600 hover:bg-orange-700 text-white';

    switch (actionType) {
        case 'UPGRADE':
            buttonText = `Upgrade to ${plan.name}`;
            break;
        case 'RENEW':
            buttonText = 'Renew Subscription';
            break;
        case 'DOWNGRADE':
            buttonText = `Downgrade to ${plan.name}`;
            buttonClass = 'bg-[#ECE5DF] text-[#472b20] hover:bg-[#DED2C8]';
            break;
        case 'SWITCH_CYCLE':
            buttonText = `Switch Cycle`;
            buttonClass = 'bg-gray-100 text-gray-400 cursor-not-allowed';
            break;
        default:
            buttonText = 'Current Plan';
    }

    return (
        <div
            className={`p-6 rounded-2xl border-2 flex flex-col ${isCurrent
                ? 'border-orange-500 bg-white shadow-md'
                : 'bg-white border-gray-200'
                } relative`}
        >
            {plan.is_recommended && (
                <div className="absolute top-0 right-0 transform translate-x-2 -translate-y-2">
                    <span className="bg-orange-500 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide">
                        Recommended
                    </span>
                </div>
            )}
            <h2 className="text-2xl font-bold text-gray-900">{plan.name}</h2>
            <div className="my-4">
                <span className="text-4xl font-bold text-gray-900">
                    {currencySymbol}
                    {price.toLocaleString()}
                </span>
                <span className="text-gray-500">
                    /{plan.billing_cycle.toLowerCase() === 'monthly' ? 'month' : 'year'}
                </span>
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
            {isCurrent ? (
                <div className="text-center p-2 bg-orange-50 text-orange-700 font-semibold rounded-md mt-auto">
                    Your Current Plan
                </div>
            ) : (
                <Button
                    onClick={onAction}
                    disabled={
                        isProcessing ||
                        actionType === 'SWITCH_CYCLE'
                    }
                    className={`w-full py-6 rounded-xl font-semibold  mt-auto ${buttonClass}`}
                >
                    {isProcessing ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            Processing...
                        </>
                    ) : (
                        buttonText
                    )}
                </Button>
            )}
        </div>
    );
};

export const PlansModal: React.FC<PlansModalProps> = ({ isOpen, onClose, onSuccess, subscription }) => {
    const { userProfile } = useAuth();
    const { data: usageData, isLoading: usageLoading } = useUsageQuery();
    const { data: fetchedPlans, isLoading: plansLoading } = usePlansQuery();

    const [billingCycle, setBillingCycle] = useState<'MONTHLY' | 'YEARLY'>('MONTHLY');

    // Filter active plans from the cached data
    const plans = (fetchedPlans || []).filter((plan: LocalPlan) => plan.active);

    const [isProcessing, setIsProcessing] = useState(false);
    const [upgradePreview, setUpgradePreview] = useState<UpgradePreview | null>(null);
    const [showUpgradeModal, setShowUpgradeModal] = useState(false);
    const [downgradePreview, setDowngradePreview] = useState<DowngradePreview | null>(null);
    const [showDowngradeModal, setShowDowngradeModal] = useState(false);

    const loading = plansLoading || usageLoading;

    // Removed useEffect for fetching plans since it's now handled by React Query
    // Removed fetchPlans function

    const getCurrentPlanDetails = () => {
        if (plans.length === 0) return null;

        // Priority 1: Use subscription prop if available
        if (subscription?.plan) {
            // Find plan by ID if possible, or name/polar_id
            const matchedPlan = plans.find(p =>
                String(p.id) === String(subscription.plan!.id) ||
                (p.polar_plan_id && subscription.plan!.polar_plan_id && p.polar_plan_id === subscription.plan!.polar_plan_id)
            );
            if (matchedPlan) return matchedPlan;
        }

        // Priority 2: Use usageData (fallback)
        if (!usageData) return null;

        let currentPlan = plans.find(p =>
            p.name.toLowerCase() === usageData.plan_name.toLowerCase()
        );
        if (!currentPlan) {
            currentPlan = plans.find(p =>
                p.plan_type === usageData.plan_type &&
                p.is_free === (usageData.plan_type === 'FREE')
            );
        }
        if (!currentPlan) {
            currentPlan = plans.find(p => p.is_free);
        }
        return currentPlan;
    };

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

    const getPlanPrice = (plan: LocalPlan) => {
        const priceObj = plan.prices.find(p => p.currency === 'USD');
        return priceObj ? priceObj.price : 0;
    };

    const getPlanActionType = (plan: LocalPlan): 'CURRENT' | 'UPGRADE' | 'DOWNGRADE' | 'SWITCH_CYCLE' | 'RENEW' => {
        const currentPlanDetails = getCurrentPlanDetails();
        if (!currentPlanDetails) return 'UPGRADE';

        if (currentPlanDetails.id === plan.id) {
            // If subscription is cancelling, show RENEW option
            if (subscription?.subscription?.cancel_at_period_end || subscription?.subscription?.status === 'canceled') {
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
        if (currentPlanDetails.billing_cycle !== plan.billing_cycle) {
            return 'SWITCH_CYCLE';
        }
        return 'CURRENT';
    };

    const proceedToCheckout = async (polarPlanId: string, userId: string) => {
        const redirectUrl = window.location.href;
        const response = await paymentAPI.createCheckoutSession(
            polarPlanId,
            userId,
            redirectUrl
        );
        const checkoutUrl = response?.data?.checkout_url || response?.checkout_url || response?.url;
        if (checkoutUrl) {
            window.location.href = checkoutUrl;
        } else {
            toast.error("Failed to start payment session");
        }
    };

    const handlePlanAction = async (planId: string | number) => {
        setIsProcessing(true);
        try {
            const plan = plans.find(p => String(p.id) === String(planId));
            if (!plan) {
                toast.error("Plan not found");
                return;
            }

            const actionType = getPlanActionType(plan);
            if (actionType === 'SWITCH_CYCLE') {
                toast.error("Please contact support to change your plan.");
                return;
            }

            if (!plan.polar_plan_id) {
                toast.error("This plan is not available for subscription");
                return;
            }

            const userId = userProfile?.id;
            if (!userId) {
                toast.error("Unable to identify user");
                return;
            }

            if (actionType === 'UPGRADE' && !currentPlanDetails?.is_free) {
                try {
                    const preview = await paymentAPI.getUpgradePreview(plan.polar_plan_id, userId);
                    setUpgradePreview(preview);
                    setShowUpgradeModal(true);
                    return;
                } catch (error) {
                    console.error("Failed to fetch upgrade preview:", error);
                    toast.error("Failed to calculate upgrade preview. Proceeding to checkout...");
                }
            }

            if (actionType === 'DOWNGRADE') {
                try {
                    const preview = await paymentAPI.getDowngradePreview(plan.polar_plan_id, userId);
                    setDowngradePreview(preview);
                    setShowDowngradeModal(true);
                    return;
                } catch (error) {
                    console.error("Failed to fetch downgrade preview:", error);
                    toast.error("Failed to calculate downgrade preview.");
                    return;
                }
            }

            await proceedToCheckout(plan.polar_plan_id, userId);
        } catch (error: any) {
            console.error("Subscription error:", error);
            if (error.response?.status === 401) {
                toast.error("Please log in to continue");
            } else if (error.response?.status === 400) {
                toast.error(error.response.data?.message || "Invalid request");
            } else {
                toast.error("Failed to process subscription request");
            }
        } finally {
            setIsProcessing(false);
        }
    };

    const handleConfirmUpgrade = async () => {
        if (!upgradePreview || !userProfile?.id) return;
        setIsProcessing(true);
        try {
            const targetPlan = plans.find(p => p.name === upgradePreview.new_plan);
            if (!targetPlan?.polar_plan_id) {
                toast.error("Target plan not found");
                return;
            }
            await paymentAPI.upgradeSubscription(userProfile.id, targetPlan.polar_plan_id);
            setShowUpgradeModal(false);
            toast.success(`Successfully upgraded to ${targetPlan.name}!`);
            if (onSuccess) {
                onSuccess();
            }
            onClose();
        } catch (error: any) {
            console.error("Upgrade confirmation error:", error);
            toast.error("Failed to upgrade subscription");
        } finally {
            setIsProcessing(false);
        }
    };

    const handleConfirmDowngrade = async () => {
        if (!downgradePreview || !userProfile?.id) return;
        setIsProcessing(true);
        try {
            const targetPlan = plans.find(p => p.name === downgradePreview.new_plan);
            if (!targetPlan?.polar_plan_id) {
                toast.error("Target plan not found");
                return;
            }
            await paymentAPI.downgradeSubscription(targetPlan.polar_plan_id, userProfile.id);
            setShowDowngradeModal(false);
            toast.success(`Successfully downgraded to ${targetPlan.name}!`);
            if (onSuccess) {
                onSuccess();
            }
            onClose();
        } catch (error: any) {
            console.error("Downgrade confirmation error:", error);
            toast.error("Failed to downgrade subscription");
        } finally {
            setIsProcessing(false);
        }
    };

    const currentPlanDetails = getCurrentPlanDetails();
    const { freePlan, paidPlans } = getFilteredPlans();
    const currencySymbol = '$';

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 bg-[#F5F0EC]">
            {/* Close button in top corner */}
            <div className="absolute top-4 right-4 z-10">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onClose}
                    className="rounded-full hover:bg-[#ECE5DF]"
                >
                    <X className="w-6 h-6 text-[#472b20]" />
                </Button>
            </div>

            {/* Back to chat link — top left */}
            <div className="absolute top-4 left-4 z-10">
                <button
                    onClick={onClose}
                    className="flex items-center gap-1 text-sm text-[#472b20]/60 hover:text-[#472b20] transition-colors"
                >
                    <X className="w-4 h-4" />
                    Back to chat
                </button>
            </div>

            {/* Content */}
            <div className="h-full overflow-y-auto p-6 pt-8">
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-full">
                        <Loader2 className="w-12 h-12 animate-spin text-orange-600 mb-4" />
                        <p className="text-gray-600">Loading plans...</p>
                    </div>
                ) : (
                    <div className="max-w-6xl mx-auto space-y-8 pb-12">
                        {/* Plans Header */}
                        <div className="text-center">
                            <h1 className="text-4xl font-heading font-bold text-[#472b20] mb-2">Plans & Pricing</h1>
                            <p className="text-[#472b20]/60 max-w-xl mx-auto font-light">
                                Subscriptions reset monthly. Prices are indicative.
                            </p>
                        </div>

                        {/* Billing Toggle (Pill) */}
                        <div className="flex justify-center mt-6">
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
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
                            {/* Free Plan */}
                            {freePlan && (
                                <div
                                    className={`p-8 rounded-xl border-2 flex flex-col bg-white ${currentPlanDetails?.id === freePlan.id
                                        ? 'border-[#D05E2D] '
                                        : 'border-transparent '
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
                                        <>
                                        </>
                                    )}
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
                                            ? 'border-[#D05E2D] '
                                            : 'border-transparent '
                                            } relative`}
                                    >
                                        <h2 className="text-2xl font-heading font-bold text-[#472b20] mb-2">{plan.name}</h2>
                                        <div className="my-2">
                                            <span className="text-5xl font-heading font-bold text-[#472b20]">
                                                {currencySymbol}{price.toLocaleString()}
                                            </span>
                                            <span className="text-[#472b20]/60 font-light">
                                                /{plan.billing_cycle.toLowerCase() === 'monthly' ? 'month' : 'year'}
                                            </span>
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
                                            onClick={() => handlePlanAction(plan.id)}
                                            disabled={isProcessing && !isCurrent}
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
                    </div>
                )}
            </div>

            {showUpgradeModal && upgradePreview && (
                <UpgradePreviewModal
                    preview={upgradePreview}
                    onConfirm={handleConfirmUpgrade}
                    onClose={() => setShowUpgradeModal(false)}
                    isProcessing={isProcessing}
                />
            )}

            {/* Downgrade Preview Modal */}
            {showDowngradeModal && downgradePreview && (
                <DowngradePreviewModal
                    preview={downgradePreview}
                    onConfirm={handleConfirmDowngrade}
                    onClose={() => setShowDowngradeModal(false)}
                    isProcessing={isProcessing}
                />
            )}
        </div>
    );
};
