import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Mail, Key, ShieldCheck } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const AdminLogin: React.FC = () => {
    const {
        signInWithEmailPassword,
        signInWithOtp,
        verifyOtp,
        resendOtp
    } = useAuth();
    const navigate = useNavigate();

    const [authMethod, setAuthMethod] = useState<'password' | 'otp'>('password');
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [otp, setOtp] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [isOtpSent, setIsOtpSent] = useState(false);

    const handleEmailPasswordSignIn = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setSuccess("");

        if (!email.trim()) {
            setError("Please enter your email");
            return;
        }

        if (!password) {
            setError("Please enter your password");
            return;
        }

        setIsLoading(true);

        try {
            // The hardcoded "admin" / "admin" bypass that used to sit here has
            // been removed. It forged a session in localStorage with a fake
            // access token, and the login screen advertised the credentials in
            // plain sight. Backend admin routes always verified a real Supabase
            // JWT and an ADMIN role, so the bypass only ever produced a shell
            // that could not call the API, but publishing default credentials on
            // a production login page invites probing. Authentication now goes
            // through Supabase for everyone.
            const response = await signInWithEmailPassword(email, password);

            if (response.success) {
                setSuccess("Admin verification successful! Redirecting...");
                setTimeout(() => {
                    navigate('/admin');
                }, 1000);
            } else {
                setError(response.message);
            }
        } catch (err: any) {
            setError(err.message || "Sign in failed. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleSendOtp = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setSuccess("");

        if (!email.trim()) {
            setError("Please enter your email");
            return;
        }

        setIsLoading(true);

        try {
            const response = await signInWithOtp(email);

            if (response.success) {
                setIsOtpSent(true);
                setSuccess(response.message);
            } else {
                setError(response.message);
            }
        } catch (err: any) {
            setError(err.message || "Failed to send verification code.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleVerifyOtp = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!otp.trim()) {
            setError("Please enter the verification code");
            return;
        }

        setIsLoading(true);

        try {
            const response = await verifyOtp(email, otp);

            if (response.success) {
                setSuccess("Verification successful! Redirecting...");
                setTimeout(() => {
                    navigate('/admin');
                }, 2000);
            } else {
                setError(response.message);
            }
        } catch (err: any) {
            setError(err.message || "Verification failed. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleResendOtp = async () => {
        setError("");
        setIsLoading(true);

        try {
            const response = await resendOtp(email);

            if (response.success) {
                setSuccess(response.message);
            } else {
                setError(response.message);
            }
        } catch (err: any) {
            setError(err.message || "Failed to resend code. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    const switchToPasswordAuth = () => {
        setAuthMethod('password');
        setError("");
        setSuccess("");
        setIsOtpSent(false);
    };

    const switchToOtpAuth = () => {
        setAuthMethod('otp');
        setError("");
        setSuccess("");
        setIsOtpSent(false);
    };

    return (
        <div className="h-full overflow-y-auto flex justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gray-900">
            <div className="max-w-md w-full space-y-8">
                <Card className="border-gray-800 bg-gray-950 text-white">
                    <div className="mx-auto mb-4 mt-8 w-16 h-16 bg-orange-900/20 rounded-full flex items-center justify-center border border-orange-900/50">
                        <ShieldCheck className="w-8 h-8 text-orange-500" />
                    </div>

                    <CardHeader>
                        <CardTitle className="text-2xl text-center text-white">Admin Portal</CardTitle>
                        <CardDescription className="text-center text-gray-400">
                            {authMethod === 'password'
                                ? "Enter your admin credentials to continue"
                                : !isOtpSent
                                    ? "We'll send a verification code to your email"
                                    : `Verification code sent to: ${email}`
                            }
                        </CardDescription>
                    </CardHeader>

                    <CardContent>
                        {/* Password Authentication */}
                        {authMethod === 'password' && (
                            <form onSubmit={handleEmailPasswordSignIn} className="space-y-4">
                                <div>
                                    <Label htmlFor="email-password" className="text-gray-300">
                                        Email
                                    </Label>
                                    <Input
                                        id="email-password"
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="you@example.com"
                                        className="mt-1 bg-gray-900 border-gray-800 text-white placeholder:text-gray-600 focus:border-orange-500"
                                        disabled={isLoading}
                                        required
                                    />
                                </div>

                                <div>
                                    <Label htmlFor="password" className="text-gray-300">
                                        Password
                                    </Label>
                                    <Input
                                        id="password"
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="Your password"
                                        className="mt-1 bg-gray-900 border-gray-800 text-white placeholder:text-gray-600 focus:border-orange-500"
                                        disabled={isLoading}
                                        required
                                    />
                                </div>

                                {error && <p className="text-red-500 text-sm bg-red-950/20 p-2 rounded border border-red-900/50">{error}</p>}
                                {success && <p className="text-green-500 text-sm bg-green-950/20 p-2 rounded border border-green-900/50">{success}</p>}

                                <Button
                                    type="submit"
                                    disabled={isLoading}
                                    className="w-full bg-orange-600 hover:bg-orange-700 text-white border-none"
                                >
                                    {isLoading ? "Verifying..." : "Access Dashboard"}
                                </Button>
                            </form>
                        )}

                        {/* OTP Authentication */}
                        {authMethod === 'otp' && (
                            <div>
                                {!isOtpSent ? (
                                    <form onSubmit={handleSendOtp} className="space-y-4">
                                        <div>
                                            <Label htmlFor="email-otp" className="text-gray-300">
                                                Email
                                            </Label>
                                            <Input
                                                id="email-otp"
                                                type="email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                placeholder="admin@example.com"
                                                className="mt-1 bg-gray-900 border-gray-800 text-white placeholder:text-gray-600 focus:border-orange-500"
                                                disabled={isLoading}
                                                required
                                            />
                                        </div>

                                        {error && <p className="text-red-500 text-sm bg-red-950/20 p-2 rounded border border-red-900/50">{error}</p>}
                                        {success && <p className="text-green-500 text-sm bg-green-950/20 p-2 rounded border border-green-900/50">{success}</p>}

                                        <Button
                                            type="submit"
                                            disabled={isLoading}
                                            className="w-full bg-orange-600 hover:bg-orange-700 text-white border-none"
                                        >
                                            {isLoading ? "Sending Code..." : "Send Verification Code"}
                                        </Button>
                                    </form>
                                ) : (
                                    <form onSubmit={handleVerifyOtp} className="space-y-4">
                                        <div>
                                            <Label htmlFor="otp" className="text-gray-300">
                                                Verification Code
                                            </Label>
                                            <Input
                                                id="otp"
                                                type="text"
                                                value={otp}
                                                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 8))}
                                                placeholder="Enter 8-digit code"
                                                className="mt-1 text-center tracking-widest text-lg font-mono bg-gray-900 border-gray-800 text-white focus:border-orange-500"
                                                disabled={isLoading}
                                                maxLength={8}
                                                required
                                            />
                                        </div>

                                        <div className="text-center">
                                            <button
                                                type="button"
                                                onClick={handleResendOtp}
                                                disabled={isLoading}
                                                className="text-sm text-orange-500 hover:text-orange-400 disabled:text-gray-600"
                                            >
                                                Didn't receive the code? Resend
                                            </button>
                                        </div>

                                        {error && <p className="text-red-500 text-sm text-center bg-red-950/20 p-2 rounded border border-red-900/50">{error}</p>}
                                        {success && <p className="text-green-500 text-sm text-center bg-green-950/20 p-2 rounded border border-green-900/50">{success}</p>}

                                        <div className="flex gap-3">
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => setIsOtpSent(false)}
                                                disabled={isLoading}
                                                className="flex-1 border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white"
                                            >
                                                Back
                                            </Button>
                                            <Button
                                                type="submit"
                                                disabled={isLoading || otp.length !== 8}
                                                className="flex-1 bg-orange-600 hover:bg-orange-700 text-white border-none"
                                            >
                                                {isLoading ? "Verifying..." : "Verify & Access"}
                                            </Button>
                                        </div>
                                    </form>
                                )}
                            </div>
                        )}

                        {/* Method Switcher */}
                        <div className="mt-6 flex flex-col gap-3">
                            {authMethod === 'otp' && (
                                <Button
                                    type="button"
                                    variant="ghost"
                                    onClick={switchToPasswordAuth}
                                    className="flex items-center gap-2 text-gray-400 hover:text-white hover:bg-gray-800"
                                >
                                    <Key className="w-4 h-4" />
                                    Sign in with Password
                                </Button>
                            )}

                            {authMethod === 'password' && (
                                <Button
                                    type="button"
                                    variant="ghost"
                                    onClick={switchToOtpAuth}
                                    className="flex items-center gap-2 text-gray-400 hover:text-white hover:bg-gray-800"
                                >
                                    <Mail className="w-4 h-4" />
                                    Sign in with Email OTP
                                </Button>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default AdminLogin;
