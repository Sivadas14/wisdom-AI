import React from 'react';
import { Navigate } from 'react-router-dom';
import { SubscriptionScreen } from "@/components/subscription/SubscriptionScreen";
import { useUsage } from "@/contexts/UsageContext";

const Subscription: React.FC = () => {
    const { usage, loading, creditsActive } = useUsage();

    // Under the credit model there are no subscriptions to browse. The page
    // is still deep-linkable and bookmarkable, so anyone arriving here — an
    // old bookmark, an old email, a search result — goes to Billing & Credits
    // rather than a Seeker/Devotee grid for plans no longer sold. Legacy paid
    // accounts keep the screen: their subscription is real and cancellable.
    if (!loading && creditsActive && usage?.plan_type === 'FREE') {
        return <Navigate to="/billing" replace />;
    }

    return (
        <SubscriptionScreen />
    );
};

export default Subscription;
