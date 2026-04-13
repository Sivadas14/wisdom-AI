import React, { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, MessageSquare, Image as ImageIcon, Heart, AlertTriangle, Volume2, Video } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { usageAPI, paymentAPI } from '@/apis/api';
import { useUsage } from '@/contexts/UsageContext';
import { toast } from 'sonner';
import { UsageMetric } from './UsageMetric';
import { PlanActionButtons } from './PlanActionButtons';
import { PlansModal } from './PlansModal';
import { AddonsModal } from './AddonsModal';
import { useUsageQuery, useAddonsQuery, usePlansQuery, UsageData } from '@/hooks/useBillingData';
import { SubscriptionResponse } from '@/apis/wire';
import { SubscriptionHistory } from '@/components/subscription/SubscriptionHistory';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Separator } from "@/components/ui/separator";


export const BillingPage: React.FC = () => {
    const { userProfile } = useAuth();
    const navigate = useNavigate();
    const {
        usage: usageData,
        loading: usageLoading,
        refreshUsage: refetchUsage,
        subscription: subscriptionDetails,
        setShowPlansModal,
        setShowAddonsModal,
        setAddonsModalMode,
        refreshSubscription
    } = useUsage();
    const location = useLocation();
    useAddonsQuery();
    usePlansQuery();


    useEffect(() => {
        const urlParams = new URLSearchParams(location.search);
        const checkoutSuccess = urlParams.get('checkout_success');
        const sessionId = urlParams.get('session_id');
        const customerSessionToken = urlParams.get('customer_session_token');

        if (checkoutSuccess === 'true' || sessionId || customerSessionToken) {
            console.log('🎉 [BillingPage] Checkout success detected, refreshing usage...');


            refetchUsage();

            toast.success("Purchase successful! Your quota has been updated.");

            navigate(location.pathname, { replace: true });
        }
    }, [location.search, location.pathname, navigate, refetchUsage]);


    const [isProcessing, setIsProcessing] = useState(false);
    const [showCancelDialog, setShowCancelDialog] = useState(false);
    const [currentView, setCurrentView] = useState<'billing' | 'history'>('billing');
    const [resetDays, setResetDays] = useState<number>(30);

    useEffect(() => {
        const today = new Date();
        let targetDate: Date;

        if (subscriptionDetails?.subscription?.current_period_end) {
            targetDate = new Date(subscriptionDetails.subscription.current_period_end);
        } else {
            targetDate = new Date(today.getFullYear(), today.getMonth() + 1, 1);
        }

        const diffTime = targetDate.getTime() - today.getTime();
        const daysUntilReset = Math.max(0, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
        setResetDays(daysUntilReset);
    }, [subscriptionDetails]);

    const handleCancelPlan = () => {
        setShowCancelDialog(true);
    };

    const confirmCancelSubscription = async () => {
        if (!usageData?.plan_type) return;
        setShowCancelDialog(false);
        setIsProcessing(true);
        try {
            const subId = subscriptionDetails?.subscription?.id || subscriptionDetails?.subscription?.polar_subscription_id;
            if (!subId) {
                toast.error("No active subscription found to cancel");
                return;
            }
            await paymentAPI.cancelSubscription(subscriptionDetails?.subscription?.user_id || "", subId);
            toast.success("Subscription cancelled successfully.");
            await refetchUsage();

            await refreshSubscription();
        } catch (error: any) {
            console.error('Cancellation error:', error);
            if (error.response?.status === 401) {
                toast.error('Please log in to continue');
            } else if (error.response?.status === 400) {
                toast.error(error.response.data?.message || 'Invalid request');
            } else {
                toast.error('Failed to cancel subscription');
            }
        } finally {
            setIsProcessing(false);
        }
    };

    const handleManage = () => {
        toast.info('Redirecting to payment management...');
        toast.error('Payment management portal URL not configured. Please contact support.');
    };

    const handleViewPlans = () => {
        setShowPlansModal(true);
    };

    const handleSyncRazorpay = async () => {
        setIsProcessing(true);
        try {
            const res = await paymentAPI.syncRazorpaySubscription();
            const subId = res?.data?.subscription_id || res?.subscription_id || '';
            toast.success(
                `Subscription activated${subId ? ` (${subId})` : ''}. Refreshing your plan...`,
            );
            await Promise.all([refetchUsage(), refreshSubscription()]);
        } catch (error: any) {
            console.error('Razorpay sync failed:', error);
            const detail =
                error?.response?.data?.detail ||
                error?.response?.data?.message ||
                error?.message ||
                'Unknown error';
            toast.error(`Could not sync subscription: ${detail}`);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleBack = () => {
        if (currentView === 'history') {
            setCurrentView('billing');
        } else {
            navigate(-1);
        }
    };

    const isFree = usageData?.plan_type === 'FREE' || !usageData;
    const hasAddons = usageData ? ((usageData.addon_cards?.limit > 0 || usageData.addon_cards?.used > 0) ||
        (usageData.addon_minutes?.limit > 0 || usageData.addon_minutes?.used > 0)) : false;

    return (
        <div className="min-h-full h-full overflow-y-auto bg-[#F5F0EC] p-4 sm:p-6 lg:p-8">

            <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to cancel your subscription? You'll continue to have access until the end of your current billing period.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={confirmCancelSubscription}
                            className="bg-red-600 hover:bg-red-700"
                        >
                            Cancel Subscription
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* Header */}
            <header className="max-w-4xl mx-auto flex items-center justify-between w-full mb-8">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleBack}
                    className="rounded-full hover:bg-[#ECE5DF]"
                >
                    <ArrowLeft className="w-6 h-6 text-[#472b20]" />
                </Button>
                <h1 className="text-2xl font-bold text-[#472b20]">
                    {currentView === 'billing' ? 'Billing' : 'Payment History'}
                </h1>
                {currentView === 'billing' ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentView('history')}
                        className="text-[#472b20] border-[#ECE5DF] hover:bg-[#ECE5DF] font-medium"
                    >
                        View Payment History
                    </Button>
                ) : (
                    <div className="w-10" />
                )}
            </header>

            <main className="max-w-4xl mx-auto space-y-6">
                {currentView === 'billing' ? (
                    <>
                        {isFree && (
                            <div className="bg-white/60 backdrop-blur-sm rounded-lg shadow-sm border border-[#ECE5DF] p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                                <div className="text-sm text-[#472b20]">
                                    <span className="font-semibold">Paid via Razorpay but still on Free?</span>
                                    <span className="text-[#472b20]/70"> Click sync to activate your plan instantly.</span>
                                </div>
                                <Button
                                    onClick={handleSyncRazorpay}
                                    disabled={isProcessing}
                                    variant="outline"
                                    size="sm"
                                    className="text-[#472b20] border-[#d05e2d] hover:bg-[#ECE5DF] font-medium shrink-0"
                                >
                                    {isProcessing ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                            Syncing...
                                        </>
                                    ) : (
                                        'Sync with Razorpay'
                                    )}
                                </Button>
                            </div>
                        )}

                        {/* {subscriptionDetails?.subscription?.cancel_at_period_end && (
                            <div className="bg-[#FEFCE8] border border-[#FEF08A] shadow-sm rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4 mb-6 animate-in fade-in slide-in-from-top-4 duration-500">
                                <div className="flex items-center gap-4">
                                    <div className="bg-[#FEF08A] p-2.5 rounded-full shrink-0">
                                        <AlertTriangle className="w-5 h-5 text-yellow-700" />
                                    </div>
                                    <div className="space-y-1">
                                        <h3 className="font-bold text-yellow-900 leading-none">Plan cancellation</h3>
                                        <p className="text-yellow-800 text-sm">
                                            Your <span className="font-semibold capitalize">{usageData?.plan_name?.toLowerCase()}</span> plan is cancelled and will remain active until <span className="font-semibold">{new Date(subscriptionDetails.subscription.current_period_end).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}</span>. After that, your account will switch to limited access, and you won't be charged any further.
                                        </p>
                                    </div>
                                </div>
                                <Button
                                    onClick={() => setShowPlansModal(true)}
                                    className="bg-[#059669] hover:bg-[#047857] text-white font-semibold transition-all shadow-sm px-6 hover:scale-105 active:scale-95 shrink-0"
                                >
                                    Reactivate now
                                </Button>
                            </div>
                        )} */}

                        {/* Current Plan Section */}

                        <section>
                            <div className="bg-white/60 backdrop-blur-sm rounded-lg shadow-sm border border-[#ECE5DF] p-6">


                                <h2 className="text-lg font-semibold text-[#472b20] mb-4">Current Plan</h2>
                                <div className="flex items-start justify-between mb-4">

                                    <div className="flex items-start justify-between ">
                                        <div className="flex items-center gap-3">
                                            {/* {usageLoading ? (
                                            <div className="w-3 h-3 rounded-full bg-gray-200 animate-pulse" />
                                        ) : (
                                            <div className={`w-3 h-3 rounded-full ${isFree ? 'bg-green-500' : 'bg-orange-500'}`} />
                                        )} */}
                                            <div>
                                                {usageLoading ? (
                                                    <div className="w-32 h-6 bg-gray-200 rounded animate-pulse" />
                                                ) : (
                                                    <>
                                                        <div className="flex items-center gap-2">
                                                            <p className="text-xl font-bold text-[#472b20] capitalize">
                                                                {usageData?.plan_name}
                                                            </p>
                                                            {/* {subscriptionDetails?.subscription?.status && !(subscriptionDetails?.subscription?.status === 'canceled' && new Date() < new Date(subscriptionDetails.subscription.current_period_end)) && (
                                                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${subscriptionDetails.subscription.status === 'active'
                                                                    ? 'bg-green-100 text-green-700'
                                                                    : 'bg-red-100 text-red-700'
                                                                    }`}>
                                                                    {subscriptionDetails.subscription.status}
                                                                </span>
                                                            )} */}
                                                        </div>
                                                        <div className="text-sm text-[#472b20]/60 mt-1">
                                                            {usageLoading ? (
                                                                <div className="w-48 h-4 bg-[#ECE5DF] rounded mt-2 animate-pulse" />
                                                            ) : (
                                                                isFree
                                                                    ? 'Limited features with basic access'
                                                                    : `Premium access to all ${usageData?.plan_name} features`
                                                            )}
                                                        </div>
                                                        {subscriptionDetails?.subscription && !isFree && (
                                                            <p className="text-xs text-[#472b20]/40 mt-1">
                                                                {subscriptionDetails.subscription.status === 'canceled' || subscriptionDetails.subscription.cancel_at_period_end
                                                                    ? `Ends on ${new Date(subscriptionDetails.subscription.current_period_end).toLocaleDateString()}`
                                                                    : `Renews on ${new Date(subscriptionDetails.subscription.current_period_end).toLocaleDateString()}`
                                                                }
                                                            </p>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {!(subscriptionDetails?.subscription?.status === 'canceled' && new Date() < new Date(subscriptionDetails.subscription.current_period_end)) && (
                                        <PlanActionButtons
                                            planType={usageData?.plan_type || 'FREE'}
                                            isFree={isFree}
                                            onCancelPlan={handleCancelPlan}
                                            onManage={handleManage}
                                            onViewPlans={handleViewPlans}
                                            isProcessing={isProcessing}
                                            // Only show cancel if active and not already scheduled for cancellation
                                            showCancel={subscriptionDetails?.subscription?.status === 'active' && !subscriptionDetails?.subscription?.cancel_at_period_end}
                                        />
                                    )}
                                </div>
                            </div>
                            {subscriptionDetails?.subscription?.cancel_at_period_end && (

                                <div className="bg-white/60 rounded-b-lg mt-[-16px]  border border-[#ECE5DF] p-6 pt-8">
                                    <div className='flex items-center gap-2'>
                                        <div className="bg-[#FEF08A] p-2.5 rounded-full shrink-0">
                                            <AlertTriangle className="w-5 h-5 text-yellow-700" />
                                        </div>
                                        <p className="text-yellow-800 text-sm">
                                            Your <span className="font-semibold capitalize">{usageData?.plan_name?.toLowerCase()}</span> plan is cancelled and will remain active until <span className="font-semibold">{new Date(subscriptionDetails.subscription.current_period_end).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}</span>. After that, your account will switch to Free Plan, and you won't be charged any further.
                                        </p>
                                    </div>
                                </div>

                            )}
                        </section>


                        {/* Usage Section */}
                        <section className="bg-white/60 backdrop-blur-sm rounded-lg shadow-sm border border-[#ECE5DF] p-6">
                            <div className="flex items-start justify-between mb-6">
                                <div>
                                    <h2 className="text-lg font-semibold text-[#472b20]">Usage</h2>
                                    <p className="text-sm text-[#472b20]/60 mt-1">
                                        {isFree ? "Your current usage and limits" : "Your current usage and limits for this billing period"}
                                    </p>
                                </div>
                                <Button
                                    onClick={() => setShowAddonsModal(true)}
                                    className="bg-[#472b20] hover:bg-[#5d3a2c] text-white font-medium  transition-all rounded-md"
                                >
                                    Buy Credits
                                </Button>
                            </div>

                            <div className="space-y-6">
                                {/* Chats/Conversations - No reset message */}
                                <div>
                                    <h3 className="text-sm font-semibold text-[#472b20] mb-3 uppercase tracking-wider">Chats</h3>
                                    <UsageMetric
                                        icon={<MessageSquare className="w-4 h-4 text-[#d05e2d]" />}
                                        label="Conversations"
                                        used={usageData?.conversations.used || 0}
                                        limit={usageData?.conversations.limit || 0}
                                        colorClass="bg-purple-500"
                                        showResetMessage={false}
                                        isLoading={usageLoading}
                                    />
                                </div>
                                <Separator className="bg-[#ECE5DF]" />
                                {/* Monthly Quota Items - With reset message */}
                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <h3 className="text-sm font-semibold text-[#472b20] uppercase tracking-wider">
                                            {isFree ? "Quota" : "Monthly Quota"}
                                        </h3>
                                        {subscriptionDetails?.subscription?.status !== 'canceled' && !isFree && (
                                            <p className="text-xs text-[#472b20]/40">
                                                Resets in {resetDays} {resetDays === 1 ? 'day' : 'days'}
                                            </p>
                                        )}
                                    </div>

                                    <div className="space-y-4">
                                        <UsageMetric
                                            icon={<ImageIcon className="w-4 h-4 text-[#d05e2d]" />}
                                            label="Contemplation Cards"
                                            used={usageData?.image_cards.used || 0}
                                            limit={usageData?.image_cards.limit || 0}
                                            colorClass="bg-orange-500"
                                            isLoading={usageLoading}
                                        />

                                        <UsageMetric
                                            icon={
                                                <span className="flex items-center gap-0.5">
                                                    <Volume2 className="w-4 h-4 text-[#d05e2d]" />
                                                    <Video className="w-3.5 h-3.5 text-[#d05e2d]" />
                                                </span>
                                            }
                                            label="Audio & Video (minutes)"
                                            used={usageData?.meditation_duration.used || 0}
                                            limit={usageData?.meditation_duration.limit || 0}
                                            colorClass="bg-green-500"
                                            isLoading={usageLoading}
                                        />
                                    </div>
                                </div>
                            </div>
                        </section>

                        {/* Purchased Addons Section - Only show if user has add-ons */}
                        {hasAddons && (
                            <section className="bg-white/60 backdrop-blur-sm rounded-lg shadow-sm border border-[#ECE5DF] p-6">
                                <div className="mb-6">
                                    <h2 className="text-lg font-semibold text-[#472b20]">Purchased Addons</h2>
                                    <p className="text-sm text-[#472b20]/60 mt-1">
                                        Additional credits purchased as add-ons
                                    </p>
                                </div>

                                <div className="space-y-4">
                                    {(usageData.addon_cards?.limit > 0 || usageData.addon_cards?.used > 0) && (
                                        <div className="flex items-center justify-between p-4 bg-[#F5F0EC]/50 rounded-xl border border-[#ECE5DF]/50">
                                            <div className="flex items-center gap-3">
                                                <ImageIcon className="w-5 h-5 text-orange-500" />
                                                <div>
                                                    <p className="text-sm font-medium text-[#472b20]">Contemplation Cards</p>
                                                    <p className="text-sm text-[#472b20]/60">Add-on credits</p>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-lg font-bold text-[#472b20]">
                                                    {usageData.addon_cards.remaining}
                                                </p>
                                                <p className="text-xs text-[#472b20]/40">
                                                    of {usageData.addon_cards.limit} remaining
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    {(usageData.addon_minutes?.limit > 0 || usageData.addon_minutes?.used > 0) && (
                                        <div className="flex items-center justify-between p-4 bg-[#F5F0EC]/50 rounded-xl border border-[#ECE5DF]/50">
                                            <div className="flex items-center gap-3">
                                                <Heart className="w-5 h-5 text-green-500" />
                                                <div>
                                                    <p className="text-sm font-medium text-[#472b20]">Guided Meditation</p>
                                                    <p className="text-sm text-[#472b20]/60">Add-on minutes</p>
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <p className="text-lg font-bold text-[#472b20]">
                                                    {usageData.addon_minutes.remaining}
                                                </p>
                                                <p className="text-xs text-[#472b20]/40">
                                                    of {usageData.addon_minutes.limit} minutes remaining
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </section>
                        )}
                    </>
                ) : (
                    <SubscriptionHistory onBack={() => setCurrentView('billing')} />
                )}
            </main>
        </div >
    );
};
