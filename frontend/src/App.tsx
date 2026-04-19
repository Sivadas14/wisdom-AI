import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
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
import Landing from "./pages/Landing";

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
import KnowledgeBase from "./pages/admin/KnowledgeBase";

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

/**
 * Layout wrapper for all authenticated / inner-app routes.
 * Keeps the fixed-height, overflow-hidden shell needed by the chat UI.
 * The public Landing page renders outside this wrapper via a sibling Route.
 */
const AppShell = () => (
    <div className="h-screen flex flex-col overflow-hidden">
        <AnnouncementBanner />
        <div className="flex-1 min-h-0 overflow-y-auto">
            <Outlet />
        </div>
    </div>
);

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
                            <Routes>
                                {/*
                                 * Root layout route — all app paths live under "/".
                                 *
                                 * WHY: React Router v6 scores path="*" (splat, score≈2) HIGHER
                                 * than path="/" (root, score≈0), so a bare sibling
                                 * <Route path="/" element={<Landing/>}/> would be beaten by the
                                 * catch-all and redirect unauthenticated visitors to /signin.
                                 *
                                 * The index route pattern fixes this: an <index> route is
                                 * GUARANTEED to win over any splat for the exact parent path.
                                 */}
                                <Route path="/">

                                    {/* ── Landing page: index = renders ONLY for exactly "/" ── */}
                                    <Route index element={<Landing />} />

                                    {/* ── All other routes: wrapped in AppShell ── */}
                                    <Route element={<AppShell />}>
                                        {/* Public routes */}
                                        <Route path="signin"           element={<PublicRoute element={<SignIn />} />} />
                                        <Route path="register"         element={<PublicRoute element={<Register />} />} />
                                        <Route path="forgot-password"  element={<PublicRoute element={<ForgotPassword />} />} />
                                        <Route path="reset-password"   element={<ResetPassword />} />
                                        <Route path="privacy"          element={<PublicRoute element={<Privacy />} />} />
                                        <Route path="terms"            element={<PublicRoute element={<Terms />} />} />
                                        <Route path="profile-completion" element={<ProfileCompletion />} />
                                        <Route path="callback"         element={<AuthCallback />} />
                                        <Route path="admin/login"      element={<AdminLogin />} />

                                        {/* Authenticated portal routes */}
                                        <Route path="home" element={
                                            <ProtectedRoute>
                                                <MainLayout><Chat /></MainLayout>
                                            </ProtectedRoute>
                                        } />
                                        <Route path="chats" element={
                                            <ProtectedRoute>
                                                <MainLayout><ChatsPage /></MainLayout>
                                            </ProtectedRoute>
                                        } />
                                        <Route path="chat" element={
                                            <ProtectedRoute>
                                                <MainLayout><Chat /></MainLayout>
                                            </ProtectedRoute>
                                        } />
                                        <Route path="chat/:conversationId" element={
                                            <ProtectedRoute>
                                                <MainLayout><Chat /></MainLayout>
                                            </ProtectedRoute>
                                        } />
                                        <Route path="subscription" element={
                                            <ProtectedRoute>
                                                <MainLayout><Subscription /></MainLayout>
                                            </ProtectedRoute>
                                        } />
                                        <Route path="billing" element={
                                            <ProtectedRoute>
                                                <MainLayout><BillingPage /></MainLayout>
                                            </ProtectedRoute>
                                        } />
                                        <Route path="library" element={
                                            <ProtectedRoute>
                                                <MainLayout><Library /></MainLayout>
                                            </ProtectedRoute>
                                        } />

                                        {/* Admin routes */}
                                        <Route path="admin" element={<AdminRoute element={<AdminLayout />} />}>
                                            <Route index           element={<Dashboard />} />
                                            <Route path="users"        element={<UserManagement />} />
                                            <Route path="plans"        element={<PlanManagement />} />
                                            <Route path="banners"      element={<NotificationManagement />} />
                                            <Route path="images"       element={<ImageLibrary />} />
                                            <Route path="payments"     element={<PaymentHistory />} />
                                            <Route path="knowledge-base" element={<KnowledgeBase />} />
                                        </Route>

                                        {/* Unknown paths → back to landing */}
                                        <Route path="*" element={<NotFound />} />
                                    </Route>

                                </Route>
                            </Routes>
                        </BrowserRouter>
                    </TooltipProvider>
                </UsageProvider>
            </AuthProvider>
        </QueryClientProvider>
    );
};

export default App;
