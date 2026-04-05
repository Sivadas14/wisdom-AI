import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Mail } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import RegisterModal from "@/components/RegisterModal";
import ForgotPasswordModal from "@/components/ForgotPasswordModal";

const SignIn = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { login, isAuthenticated, isLoading: isAuthLoading } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [showRegisterModal, setShowRegisterModal] = useState(false);
    const [showForgotPasswordModal, setShowForgotPasswordModal] = useState(false);

    // Get the page user was trying to access before being redirected to sign in
    const from = location.state?.from?.pathname || "/";

    // Redirect if user is already authenticated
    useEffect(() => {
        if (isAuthenticated && !isAuthLoading) {
            navigate(from, { replace: true });
        }
    }, [isAuthenticated, isAuthLoading, navigate, from]);

    const handleSignIn = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!email.trim()) {
            setError("Please enter your email address");
            return;
        }

        if (!password) {
            setError("Please enter your password");
            return;
        }

        setIsSubmitting(true);

        try {
            await login(email.trim(), password);
            navigate(from, { replace: true });
        } catch (err: any) {
            setError(err.message || "Invalid email or password. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleRegisterSuccess = () => {
        setError("");
    };

    if (isAuthLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-button mx-auto mb-4"></div>
                    <p className="text-brand-body font-body">Loading...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: 'rgb(236, 229, 223)' }}>
            <div className="w-full max-w-md">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-heading text-brand-heading mb-4">
                        Welcome Back
                    </h1>
                    <p className="text-brand-body font-body">
                        Sign in to continue your mindful journey
                    </p>
                </div>

                {/* Sign In Card */}
                <Card className="shadow-xl border-0">
                    <CardHeader className="text-center pb-4">
                        <div className="mx-auto mb-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                            <Mail className="w-8 h-8 text-brand-button" />
                        </div>
                        <CardTitle className="text-2xl font-heading text-brand-heading">
                            Sign In
                        </CardTitle>
                        <CardDescription className="font-body text-brand-body">
                            Enter your email and password to continue
                        </CardDescription>
                    </CardHeader>

                    <CardContent className="space-y-6">
                        <form onSubmit={handleSignIn} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="email" className="font-body text-brand-heading">
                                    Email Address
                                </Label>
                                <Input
                                    id="email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                    disabled={isSubmitting}
                                    autoComplete="email"
                                />
                            </div>

                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="password" className="font-body text-brand-heading">
                                        Password
                                    </Label>
                                    <button
                                        type="button"
                                        onClick={() => setShowForgotPasswordModal(true)}
                                        className="text-sm text-brand-button hover:underline font-body"
                                    >
                                        Forgot password?
                                    </button>
                                </div>
                                <Input
                                    id="password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                    disabled={isSubmitting}
                                    autoComplete="current-password"
                                />
                            </div>

                            {error && (
                                <p className="text-red-600 text-sm font-body">{error}</p>
                            )}

                            <Button
                                type="submit"
                                disabled={isSubmitting}
                                className="w-full py-3 text-lg bg-brand-button hover:bg-brand-button/90 text-white font-body rounded-lg transition-all duration-300"
                            >
                                {isSubmitting ? "Signing In..." : "Sign In"}
                            </Button>
                        </form>

                        {/* Register Section */}
                        <div className="pt-6 border-t border-gray-200">
                            <div className="text-center space-y-3">
                                <p className="text-sm text-brand-body font-body">
                                    Don't have an account?
                                </p>
                                <Button
                                    onClick={() => setShowRegisterModal(true)}
                                    variant="outline"
                                    className="w-full border-2 border-brand-button text-brand-button hover:bg-brand-button hover:text-white transition-all duration-300 font-body"
                                >
                                    Create Account
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Registration Modal */}
                <RegisterModal
                    isOpen={showRegisterModal}
                    onClose={() => setShowRegisterModal(false)}
                    onSuccess={handleRegisterSuccess}
                />

                {/* Forgot Password Modal */}
                <ForgotPasswordModal
                    isOpen={showForgotPasswordModal}
                    onClose={() => setShowForgotPasswordModal(false)}
                    initialEmail={email}
                />
            </div>
        </div>
    );
};

export default SignIn;
