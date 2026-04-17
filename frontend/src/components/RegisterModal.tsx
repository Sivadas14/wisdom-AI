import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { UserPlus, Mail, Shield } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

interface RegisterModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const RegisterModal: React.FC<RegisterModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { supabaseRegister } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [countryCode, setCountryCode] = useState("1");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  const handleCountryCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '');
    setCountryCode(value);
  };

  const handlePhoneNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '');
    setPhoneNumber(value);
  };

  const formattedPhone = () => {
    if (!phoneNumber.trim()) return null;
    return `+${countryCode}${phoneNumber}`;
  };

  const sendOtp = async () => {
    setError("");

    if (!name.trim()) {
      setError("Please enter your name");
      return false;
    }

    if (!email.trim()) {
      setError("Please enter your email");
      return false;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address");
      return false;
    }

    setIsLoading(true);
    try {
      // Simulate OTP sending - replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // In a real app, you would call your backend to send OTP
      console.log(`OTP would be sent to: ${email}`);

      setIsOtpSent(true);
      setError("");
      return true;
    } catch (err: any) {
      setError("Failed to send verification code. Please try again.");
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const verifyOtpAndRegister = async () => {
    setError("");

    if (!otp.trim()) {
      setError("Please enter the verification code");
      return;
    }

    if (otp.length < 8) {
      setError("Verification code must be 8 digits");
      return;
    }

    setIsVerifying(true);

    try {
      // Simulate OTP verification - replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // In a real app, you would verify OTP first, then register
      // For demo purposes, we'll assume OTP is correct if it's "123456"
      if (otp !== "123456") {
        setError("Invalid verification code. Please try again.");
        return;
      }

      // OTP verified, now register the user
      const response = await supabaseRegister({
        name,
        email,
        phone: formattedPhone(),
      });

      if (response.success) {
        setSuccess(true);
        setTimeout(() => {
          onSuccess();
          handleClose();
        }, 2000);
      } else {
        setError(response.message || "Registration failed");
      }
    } catch (err: any) {
      setError(err.message || "Registration failed. Please try again.");
    } finally {
      setIsVerifying(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isOtpSent) {
      await sendOtp();
    } else {
      await verifyOtpAndRegister();
    }
  };

  const handleResendOtp = async () => {
    await sendOtp();
  };

  const handleClose = () => {
    setName("");
    setEmail("");
    setCountryCode("1");
    setPhoneNumber("");
    setOtp("");
    setError("");
    setSuccess(false);
    setIsOtpSent(false);
    onClose();
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    // Reset OTP state if email changes after OTP was sent
    if (isOtpSent) {
      setIsOtpSent(false);
      setOtp("");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <div className="mx-auto mb-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
            {isOtpSent ? (
              <Shield className="w-8 h-8 text-orange-600" />
            ) : (
              <UserPlus className="w-8 h-8 text-orange-600" />
            )}
          </div>
          <DialogTitle className="text-center text-2xl font-semibold text-gray-900">
            {isOtpSent ? "Verify Your Email" : "Create Account"}
          </DialogTitle>
          <DialogDescription className="text-center text-gray-600">
            {isOtpSent
              ? `Enter the 8-digit code sent to ${email}`
              : "Join our mindful community by creating your account"
            }
          </DialogDescription>
        </DialogHeader>

        {success ? (
          <div className="py-6 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Registration Successful!</h3>
            <p className="text-gray-600">
              Your account has been created. You can now sign in.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isOtpSent ? (
              <>
                {/* Registration Form */}
                <div className="space-y-2">
                  <Label htmlFor="register-name" className="text-gray-700">
                    Full Name
                  </Label>
                  <Input
                    id="register-name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="John Doe"
                    className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-orange-500 transition-all duration-300"
                    disabled={isLoading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="register-email" className="text-gray-700">
                    Email
                  </Label>
                  <Input
                    id="register-email"
                    type="email"
                    value={email}
                    onChange={handleEmailChange}
                    placeholder="john@example.com"
                    className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-orange-500 transition-all duration-300"
                    disabled={isLoading}
                  />
                </div>

                <div className="space-y-4">
                  <div className="flex gap-3">
                    <div className="flex-shrink-0 w-20">
                      <Label htmlFor="register-countryCode" className="text-gray-700">
                        Code
                      </Label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">+</span>
                        <Input
                          id="register-countryCode"
                          type="text"
                          value={countryCode}
                          onChange={handleCountryCodeChange}
                          className="text-lg py-3 pl-7 pr-3 border-2 border-gray-200 focus:border-orange-500 transition-all duration-300 text-center"
                          disabled={isLoading}
                          maxLength={4}
                        />
                      </div>
                    </div>

                    <div className="flex-1">
                      <Label htmlFor="register-phone" className="text-gray-700">
                        Mobile Number (optional)
                      </Label>
                      <Input
                        id="register-phone"
                        type="text"
                        value={phoneNumber}
                        onChange={handlePhoneNumberChange}
                        placeholder="5551234567"
                        className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-orange-500 transition-all duration-300"
                        disabled={isLoading}
                      />
                    </div>
                  </div>

                  {phoneNumber && (
                    <div className="text-sm text-gray-500">
                      Your number: +{countryCode}-{phoneNumber}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                {/* OTP Verification Form */}
                <div className="space-y-4">
                  <div className="text-center">
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                      <Mail className="w-6 h-6 text-blue-600" />
                    </div>
                    <p className="text-sm text-gray-600 mb-4">
                      We sent an 8-digit verification code to:<br />
                      <strong>{email}</strong>
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="register-otp" className="text-gray-700">
                      Verification Code
                    </Label>
                    <Input
                      id="register-otp"
                      type="text"
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 8))}
                      placeholder="Enter 8-digit code"
                      className="text-lg py-3 px-4 border-2 border-gray-200 focus:border-orange-500 transition-all duration-300 text-center tracking-widest text-lg font-mono"
                      disabled={isVerifying}
                      maxLength={8}
                    />
                    <div className="text-xs text-gray-500 text-center">
                      For demo purposes, use: <strong>123456</strong>
                    </div>
                  </div>

                  <div className="text-center">
                    <p> Didn't receive the code?</p>
                    <button
                      type="button"
                      onClick={handleResendOtp}
                      disabled={isLoading}
                      className="text-sm text-orange-600 hover:text-orange-500 disabled:text-gray-400"
                    >
                      Resend
                    </button>
                  </div>
                </div>
              </>
            )}

            {error && (
              <p className="text-red-600 text-sm text-center">{error}</p>
            )}

            <div className="flex gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isLoading || isVerifying}
                className="flex-1 border-2 border-gray-200 hover:bg-gray-50"
              >
                {isOtpSent ? "Back" : "Cancel"}
              </Button>

              <Button
                type="submit"
                disabled={
                  isLoading ||
                  isVerifying ||
                  !name.trim() ||
                  !email.trim() ||
                  (isOtpSent && otp.length !== 8)
                }
                className="flex-1 bg-orange-600 hover:bg-orange-700 text-white transition-all duration-300"
              >
                {isLoading ? (
                  "Sending Code..."
                ) : isVerifying ? (
                  "Verifying..."
                ) : isOtpSent ? (
                  "Verify & Create Account"
                ) : (
                  "Send Verification Code"
                )}
              </Button>
            </div>

            {isOtpSent && (
              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setIsOtpSent(false)}
                  className="text-sm text-gray-600 hover:text-gray-800"
                >
                  ← Change email
                </button>
              </div>
            )}
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default RegisterModal;