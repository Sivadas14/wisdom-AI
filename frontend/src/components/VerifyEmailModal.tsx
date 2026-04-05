import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Mail } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface VerifyEmailModalProps {
    isOpen: boolean;
    onClose: () => void;
    email: string;
    onVerified: () => void;
}

const VerifyEmailModal: React.FC<VerifyEmailModalProps> = ({ isOpen, onClose, email, onVerified }) => {
    const { verifyEmail, resendVerification } = useAuth();
    const [otp, setOtp] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");
    const [verified, setVerified] = useState(false);

    const handleVerify = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setMessage("");

        if (!otp.trim()) {
            setError("Please enter the verification code");
            return;
        }

        setIsLoading(true);

        try {
            const response = await verifyEmail(email, otp.trim());
            setVerified(true);
            setMessage(response.message);
            setTimeout(() => {
                onVerified();
                handleClose();
            }, 2000);
        } catch (err: any) {
            setError(err.message || "Verification failed");
        } finally {
            setIsLoading(false);
        }
    };

    const handleResend = async () => {
        setError("");
        setIsLoading(true);
        try {
            const response = await resendVerification(email);
            setMessage("A new verification code has been sent!");
            setOtp("");
        } catch (err: any) {
            setError(err.message || "Failed to resend code");
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        setOtp("");
        setError("");
        setMessage("");
        setVerified(false);
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <div className="mx-auto mb-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
                        <Mail className="w-8 h-8 text-brand-button" />
                    </div>
                    <DialogTitle className="text-center text-2xl font-heading text-brand-heading">
                        {verified ? 'Email Verified!' : 'Verify Your Email'}
                    </DialogTitle>
                    <DialogDescription className="text-center font-body text-brand-body">
                        {verified
                            ? 'Your email has been verified successfully'
                            : `We sent a 6-digit code to ${email}`
                        }
                    </DialogDescription>
                </DialogHeader>

                {verified ? (
                    <div className="py-6 text-center">
                        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <p className="text-brand-body font-body">
                            {message || "You can now sign in with your account."}
                        </p>
                    </div>
                ) : (
                    <form onSubmit={handleVerify} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="verify-otp" className="font-body text-brand-heading">
                                Verification Code
                            </Label>
                            <Input
                                id="verify-otp"
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
                                Check your inbox and spam folder for the code.
                            </p>
                        </div>

                        {error && <p className="text-red-600 text-sm font-body">{error}</p>}
                        {message && !error && <p className="text-green-600 text-sm font-body">{message}</p>}

                        <div className="flex gap-3 pt-4">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleClose}
                                disabled={isLoading}
                                className="flex-1 border-2 border-gray-200 hover:bg-gray-50 font-body"
                            >
                                Skip for Now
                            </Button>
                            <Button
                                type="submit"
                                disabled={isLoading || otp.length !== 6}
                                className="flex-1 bg-brand-button hover:bg-brand-button/90 text-white font-body"
                            >
                                {isLoading ? "Verifying..." : "Verify Email"}
                            </Button>
                        </div>

                        <button
                            type="button"
                            onClick={handleResend}
                            disabled={isLoading}
                            className="w-full text-sm text-brand-button hover:underline font-body disabled:opacity-50"
                        >
                            Didn't receive the code? Resend
                        </button>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    );
};

export default VerifyEmailModal;
