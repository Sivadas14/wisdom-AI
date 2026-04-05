import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { KeyRound, ArrowLeft } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface ForgotPasswordModalProps {
    isOpen: boolean;
    onClose: () => void;
    initialEmail?: string;
}

type Step = 'email' | 'otp' | 'newPassword' | 'success';

const ForgotPasswordModal: React.FC<ForgotPasswordModalProps> = ({ isOpen, onClose, initialEmail = "" }) => {
    const { forgotPassword, resetPassword } = useAuth();
    const [step, setStep] = useState<Step>('email');
    const [email, setEmail] = useState(initialEmail);
    const [otp, setOtp] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const handleSendCode = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!email.trim()) {
            setError("Please enter your email address");
            return;
        }

        setIsLoading(true);

        try {
            const response = await forgotPassword(email.trim());
            setMessage(response.message);
            setStep('otp');
        } catch (err: any) {
            setError(err.message || "Failed to send reset code");
        } finally {
            setIsLoading(false);
        }
    };

    const handleVerifyOTP = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!otp.trim()) {
            setError("Please enter the verification code");
            return;
        }

        // Move to password step (we'll verify OTP + set password together)
        setStep('newPassword');
    };

    const handleResetPassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!newPassword) {
            setError("Please enter a new password");
            return;
        }

        if (newPassword.length < 8) {
            setError("Password must be at least 8 characters");
            return;
        }

        if (newPassword !== confirmPassword) {
            setError("Passwords do not match");
            return;
        }

        setIsLoading(true);

        try {
            const response = await resetPassword(email.trim(), otp.trim(), newPassword);
            setMessage(response.message);
            setStep('success');
        } catch (err: any) {
            setError(err.message || "Password reset failed");
            // If OTP is invalid, go back to OTP step
            if (err.message?.includes("expired") || err.message?.includes("Invalid")) {
                setStep('otp');
                setOtp("");
            }
        } finally {
            setIsLoading(false);
        }
    };

    const handleResendCode = async () => {
        setError("");
        setIsLoading(true);
        try {
            const response = await forgotPassword(email.trim());
            setMessage("A new code has been sent to your email.");
            setOtp("");
        } catch (err: any) {
            setError(err.message || "Failed to resend code");
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        setStep('email');
        setEmail(initialEmail);
        setOtp("");
        setNewPassword("");
        setConfirmPassword("");
        setError("");
        setMessage("");
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <div className="mx-auto mb-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                        <KeyRound className="w-8 h-8 text-brand-button" />
                    </div>
                    <DialogTitle className="text-center text-2xl font-heading text-brand-heading">
                        {step === 'success' ? 'Password Reset!' : 'Reset Password'}
                    </DialogTitle>
                    <DialogDescription className="text-center font-body text-brand-body">
                        {step === 'email' && "Enter your email and we'll send you a reset code"}
                        {step === 'otp' && "Enter the 6-digit code sent to your email"}
                        {step === 'newPassword' && "Choose a new password for your account"}
                        {step === 'success' && "Your password has been updated"}
                    </DialogDescription>
                </DialogHeader>

                {step === 'success' ? (
                    <div className="py-6 text-center">
                        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <p className="text-brand-body font-body mb-4">{message}</p>
                        <Button
                            onClick={handleClose}
                            className="w-full bg-brand-button hover:bg-brand-button/90 text-white font-body"
                        >
                            Back to Sign In
                        </Button>
                    </div>
                ) : step === 'email' ? (
                    <form onSubmit={handleSendCode} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="reset-email" className="font-body text-brand-heading">
                                Email Address
                            </Label>
                            <Input
                                id="reset-email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@example.com"
                                className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                disabled={isLoading}
                                autoComplete="email"
                                autoFocus
                            />
                        </div>

                        {error && <p className="text-red-600 text-sm font-body">{error}</p>}

                        <div className="flex gap-3 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleClose}
                                disabled={isLoading}
                                className="flex-1 border-2 border-gray-200 hover:bg-gray-50 font-body"
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={isLoading || !email.trim()}
                                className="flex-1 bg-brand-button hover:bg-brand-button/90 text-white font-body"
                            >
                                {isLoading ? "Sending..." : "Send Reset Code"}
                            </Button>
                        </div>
                    </form>
                ) : step === 'otp' ? (
                    <form onSubmit={handleVerifyOTP} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="reset-otp" className="font-body text-brand-heading">
                                Verification Code
                            </Label>
                            <Input
                                id="reset-otp"
                                type="text"
                                value={otp}
                                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                placeholder="Enter 6-digit code"
                                className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body text-center tracking-widest"
                                disabled={isLoading}
                                maxLength={6}
                                autoFocus
                            />
                            <p className="text-xs text-gray-500 font-body">
                                Code sent to {email}. Check your inbox and spam folder.
                            </p>
                        </div>

                        {error && <p className="text-red-600 text-sm font-body">{error}</p>}
                        {message && !error && <p className="text-green-600 text-sm font-body">{message}</p>}

                        <div className="flex gap-3 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => { setStep('email'); setError(''); setMessage(''); }}
                                disabled={isLoading}
                                className="border-2 border-gray-200 hover:bg-gray-50 font-body"
                            >
                                <ArrowLeft className="w-4 h-4 mr-1" /> Back
                            </Button>
                            <Button
                                type="submit"
                                disabled={isLoading || otp.length !== 6}
                                className="flex-1 bg-brand-button hover:bg-brand-button/90 text-white font-body"
                            >
                                {isLoading ? "Verifying..." : "Continue"}
                            </Button>
                        </div>

                        <button
                            type="button"
                            onClick={handleResendCode}
                            disabled={isLoading}
                            className="w-full text-sm text-brand-button hover:underline font-body disabled:opacity-50"
                        >
                            Didn't receive the code? Resend
                        </button>
                    </form>
                ) : (
                    <form onSubmit={handleResetPassword} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="new-password" className="font-body text-brand-heading">
                                New Password
                            </Label>
                            <Input
                                id="new-password"
                                type="password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                placeholder="At least 8 characters"
                                className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                disabled={isLoading}
                                autoComplete="new-password"
                                autoFocus
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="confirm-new-password" className="font-body text-brand-heading">
                                Confirm New Password
                            </Label>
                            <Input
                                id="confirm-new-password"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="Re-enter your new password"
                                className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-brand-button transition-all duration-300 font-body"
                                disabled={isLoading}
                                autoComplete="new-password"
                            />
                        </div>

                        {error && <p className="text-red-600 text-sm font-body">{error}</p>}

                        <div className="flex gap-3 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => { setStep('otp'); setError(''); }}
                                disabled={isLoading}
                                className="border-2 border-gray-200 hover:bg-gray-50 font-body"
                            >
                                <ArrowLeft className="w-4 h-4 mr-1" /> Back
                            </Button>
                            <Button
                                type="submit"
                                disabled={isLoading || !newPassword || !confirmPassword}
                                className="flex-1 bg-brand-button hover:bg-brand-button/90 text-white font-body"
                            >
                                {isLoading ? "Resetting..." : "Reset Password"}
                            </Button>
                        </div>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    );
};

export default ForgotPasswordModal;
