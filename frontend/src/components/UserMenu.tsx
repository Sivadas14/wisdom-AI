import React, { useState } from 'react';
import { useUsage } from "@/contexts/UsageContext";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { User, LogOut, CreditCard, Loader2 } from "lucide-react";

const UserMenu: React.FC = () => {
    const { user, userProfile, logout } = useAuth();
    const { usage, loading: loadingUsage, creditsActive } = useUsage();
    const navigate = useNavigate();
    const [isOpen, setIsOpen] = useState(false);

    const handleLogout = async () => {
        try {
            await logout();
            setIsOpen(false);
            navigate('/signin');
        } catch (error) {
            console.error('Logout failed:', error);
        }
    };

    const handleManageSubscription = () => {
        // Navigate to subscription management page
        navigate('/billing');
        setIsOpen(false);
    };

    if (!user) return null;

    const displayName = userProfile?.name || user.email?.split('@')[0] || 'User';
    // const displayPhone = userProfile?.phone || user.user_metadata?.phone || ''; // Unused

    const planName = usage?.plan_name || 'Free';
    const isFree = usage?.plan_type === 'FREE';

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                onBlur={() => setTimeout(() => setIsOpen(false), 200)}
                className="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center hover:bg-orange-200 transition-colors"
            >
                <User className="w-5 h-5 text-orange-600" />
            </button>

            {isOpen && (
                <div className="absolute right-0 mt-2 w-72 bg-white rounded-xl shadow-lg ring-1 ring-black ring-opacity-5 py-1 z-10">
                  
                    <div className="px-4 py-3 border-b border-gray-200">
                        <p className="text-sm text-gray-600">Signed in as</p>
                        <p className="text-sm font-medium text-gray-900 truncate">{displayName}</p>
                        <p className="text-xs text-orange-600 font-semibold capitalize mt-1">{creditsActive ? `${usage?.credits_balance ?? 0} credits` : planName}</p>
                    </div>

                    <div className="px-4 py-3 border-b border-gray-200 text-xs">
                        <p className="font-semibold text-gray-900 mb-2">{creditsActive ? "Your Credits" : "Usage This Month"}</p>
                        {loadingUsage ? (
                            <div className="flex items-center gap-2 text-gray-400">
                                <Loader2 className="w-3 h-3 animate-spin" />
                                <span>Loading usage...</span>
                            </div>
                        ) : usage && creditsActive ? (
                            // No quota meters under credits: conversations and
                            // cards are unlimited and a 0/0 meditation meter
                            // would read as a bug. The balance is the only
                            // number that means anything here.
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <span className="text-gray-600">Media credits</span>
                                    <span className="font-medium">{usage.credits_balance ?? 0}</span>
                                </div>
                                <p className="text-gray-400">Conversations and cards are free.</p>
                            </div>
                        ) : usage ? (
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <span className="text-gray-600">Conversations</span>
                                    <span className="font-medium">{usage.conversations.used} / {usage.conversations.limit}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-gray-600">Cards</span>
                                    <span className="font-medium">{usage.image_cards.used} / {usage.image_cards.limit}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-gray-600">Meditation</span>
                                    <span className="font-medium">{usage.meditation_duration.used} / {usage.meditation_duration.limit} min</span>
                                </div>
                            </div>
                        ) : (
                            <p className="text-red-500">Failed to load usage.</p>
                        )}
                    </div>

                    {/* Actions Section */}
                    <div className="py-1">
                        <button
                            onMouseDown={handleManageSubscription}
                            className="w-full text-left flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                        >
                            <CreditCard className="w-4 h-4" />
                            <span>{creditsActive ? 'Billing & Credits' : 'Manage Subscription'}</span>
                        </button>

                        <button
                            onMouseDown={handleLogout}
                            className="w-full text-left flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                        >
                            <LogOut className="w-4 h-4" />
                            <span>Log Out</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UserMenu;