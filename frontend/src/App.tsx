import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useEffect } from "react";
import OnboardingModal from "@/components/OnboardingModal";
import { useAuth } from "@/contexts/AuthContext";

import Chat from "./pages/Chat";
import ChatsPage from "./pages/ChatsPage";
import SignIn from "./pages/SignIn";
import NotFound from "./pages/NotFound";
import { apiClient } from "@/apis";
import { AuthProvider } from "@/contexts/AuthContext";
import { UsageProvider } from "@/contexts/UsageContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AdminRoute from "@/components/AdminRoute";
import PublicRoute from "@/components/PublicRoute";

import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import ProfileCompletion from "./pages/ProfileCompletion";
import AuthCallback from "./pages/AuthCallback";
import Subscription from "./pages/Subscription";
import Library from "./pages/Library";
import Privacy from "./pages/Privacy";
import Terms from "./pages/Terms";
import { BillingPage } from "@/components/billing";

// Admin Components
import MainLayout from "@/layouts/MainLayout";
import AdminLayout from "@/layouts/AdminLayout";
import Dashboard from "@/pages/admin/Dashboard";
import UserManagement from "@/pages/admin/UserManagement";
import PlanManagement from "@/pages/admin/PlanManagement";
import PaymentHistory from "@/pages/admin/PaymentHistory";
import AdminLogin from "@/pages/admin/AdminLogin";
import AnnouncementBanner from "@/components/AnnouncementBanner";
import NotificationManagement from "./pages/admin/NotificationManagement";
import ImageLibrary from "./pages/admin/ImageLibrary";

const queryClient = new QueryClient();

/**
 * Shows the one-time onboarding modal to first-time authenticated users.
 * Must be rendered inside AuthProvider so it can read userProfile.
 */
const OnboardingGate = () => {
    const { userProfile, isAuthenticated, markOnboardingSeen } = useAuth();
    const shouldShow = isAuthenticated && userProfile !== null && userProfile.onboarding_seen === false;
    if (!shouldShow) return null;
    return <OnboardingModal onClose={markOnboardingSeen} />;
};

const App = () => {
    // Initialize API client
    useEffect(() => {
        // Set up any global API configurations here
        console.log('API Client initialized with base URL:', apiClient.defaults.baseURL);
    }, []);

    return (
        <QueryClientProvider client={queryClient}>
            <AuthProvider>
                <UsageProvider>
                    <TooltipProvider>
                        <Toaster />
                        <Sonner />
                        <BrowserRouter>
                            <OnboardingGate />
                            <div className="h-full flex flex-col overflow-hidden">
                                <AnnouncementBanner />
                                <div className="flex-1 min-h-0 overflow-hidden">
                                    <Routes>
                                        <Route path="/signin" element={<PublicRoute element={<SignIn />} />} />
                                        <Route path="/register" element={<PublicRoute element={<Register />} />} />
                                        <Route path="/forgot-password" element={<PublicRoute element={<ForgotPassword />} />} />
                                        <Route path="/reset-password" element={<ResetPassword />} />
                                        <Route path="/privacy" element={<PublicRoute element={<Privacy />} />} />
                                        <Route path="/terms" element={<PublicRoute element={<Terms />} />} />
                                        <Route path="/profile-completion" element={<ProfileCompletion />} />
                                        <Route path="/callback" element={<AuthCallback />} />
                                        <Route path="/admin/login" element={<AdminLogin />} />


                                        {/* Main App Routes - Wrapped in MainLayout */}
                                        <Route path="/" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <Chat />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        <Route path="/chats" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <ChatsPage />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        <Route path="/chat" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <Chat />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        <Route path="/chat/:conversationId" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <Chat />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        {/* Admin Routes - Protected */}
                                        <Route path="/admin" element={
                                            <AdminRoute element={<AdminLayout />} />
                                        }>
                                            <Route index element={<Dashboard />} />
                                            <Route path="users" element={<UserManagement />} />
                                            <Route path="plans" element={<PlanManagement />} />
                                            <Route path="banners" element={<NotificationManagement />} />
                                            <Route path="images" element={<ImageLibrary />} />
                                            <Route path="payments" element={<PaymentHistory />} />
                                        </Route>

                                        <Route path="/subscription" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <Subscription />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        <Route path="/billing" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <BillingPage />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        <Route path="/library" element={
                                            <ProtectedRoute>
                                                <MainLayout>
                                                    <Library />
                                                </MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        <Route path="*" element={<ProtectedRoute><NotFound /></ProtectedRoute>} />
                                    </Routes>
                                </div>
                            </div>
                        </BrowserRouter>
                    </TooltipProvider>
                </UsageProvider>
            </AuthProvider>
        </QueryClientProvider>
    );
};

export default App;
