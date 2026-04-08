import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Mail, Smartphone } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const Register: React.FC = () => {
  const { register, signInWithGoogle, verifyOtp, resendOtp } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState<'form' | 'otp'>('form');
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [countryCode, setCountryCode] = useState("+1");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pendingUser, setPendingUser] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    // Validation
    if (!name.trim()) {
      setError("Please enter your name");
      return;
    }

    if (!email.trim()) {
      setError("Please enter your email");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address");
      return;
    }

    if (!phone.trim()) {
      setError("Please enter your phone number");
      return;
    }

    if (!password) {
      setError("Please enter a password");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setIsLoading(true);

    try {
      const response = await register({
        name,
        email,
        phone,
        password,
        country_code: countryCode,
      });

      if (response.success) {
        if (response.requiresEmailConfirmation) {
          // Email confirmation required - show OTP step
          setPendingUser(response.user);
          setStep('otp');
          setSuccess("Registration successful! Please check your email for the verification code. Your profile has been created.");
        } else {
          // No email confirmation required - redirect to home
          setSuccess("Registration successful! Redirecting...");
          setTimeout(() => {
            navigate('/');
          }, 2000);
        }
      } else {
        setError(response.message);
      }
    } catch (err: any) {
      setError(err.message || "Registration failed. Please try again.");
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

    if (otp.length !== 6) {
      setError("Please enter the 6-digit verification code from your email");
      return;
    }

    setIsLoading(true);

    try {
      const response = await verifyOtp(email, otp, 'signup');

      if (response.success) {
        setSuccess("Email verified successfully! Redirecting...");

        // Small delay to ensure auth state is fully updated
        setTimeout(() => {
          navigate('/');
        }, 500);
      } else {
        setError(response.message || "Invalid verification code. Please try again.");
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
      const response = await resendOtp(email, 'signup');

      if (response.success) {
        setSuccess("Verification code sent! Please check your email.");
      } else {
        setError(response.message || "Failed to resend code. Please try again.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to resend code. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError("");
    try {
      await signInWithGoogle();
    } catch (err: any) {
      setError(err.message || "Google sign in failed");
    }
  };

  return (
    <div className="h-full overflow-y-auto flex justify-center py-12 px-4 sm:px-6 lg:px-8" style={{ backgroundColor: '#503b5d' }}>
      <div className="max-w-md w-full space-y-8">
        <Card>
          {/* <div className="mx-auto mb-4 mt-4 w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center">
            <Smartphone className="w-8 h-8 text-orange-600" />
          </div> */}

          <CardHeader>
            <CardTitle className="text-2xl">
              {step === 'form' ? 'Create an account' : 'Verify Your Email'}
            </CardTitle>
            <CardDescription>
              {step === 'form'
                ? ''
                : <>We have sent a 6-digit verification code to {email}</>
              }
            </CardDescription>
          </CardHeader>

          <CardContent>
            {step === 'form' ? (
              <>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="name" className="text-gray-700">
                        Full Name *
                      </Label>
                      <Input
                        id="name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="John Doe"
                        className="mt-1"
                        disabled={isLoading}
                        required
                      />
                    </div>

                    <div>
                      <Label htmlFor="email" className="text-gray-700">
                        Email *
                      </Label>
                      <Input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="john@example.com"
                        className="mt-1"
                        disabled={isLoading}
                        required
                      />
                    </div>

                    <div>
                      <Label htmlFor="phone" className="text-gray-700">
                        Phone Number *
                      </Label>
                      <div className="flex gap-2 mt-1">
                        <Select value={countryCode} onValueChange={setCountryCode}>
                          <SelectTrigger className="w-[120px]">
                            <SelectValue placeholder="Code" />
                          </SelectTrigger>
                          <SelectContent className="max-h-[200px] overflow-y-auto">
                            <SelectItem value="+1">+1 (US)</SelectItem>
                            <SelectItem value="+44">+44 (UK)</SelectItem>
                            <SelectItem value="+91">+91 (IN)</SelectItem>
                            <SelectItem value="+86">+86 (CN)</SelectItem>
                            <SelectItem value="+81">+81 (JP)</SelectItem>
                            <SelectItem value="+49">+49 (DE)</SelectItem>
                            <SelectItem value="+33">+33 (FR)</SelectItem>
                            <SelectItem value="+61">+61 (AU)</SelectItem>
                            <SelectItem value="+971">+971 (AE)</SelectItem>
                            <SelectItem value="+65">+65 (SG)</SelectItem>
                          </SelectContent>
                        </Select>
                        <Input
                          id="phone"
                          type="tel"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          placeholder="555 123 4567"
                          className="flex-1"
                          disabled={isLoading}
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="password" className="text-gray-700">
                        Password *
                      </Label>
                      <Input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Enter your password (min. 6 characters)"
                        className="mt-1"
                        disabled={isLoading}
                        required
                      />
                    </div>

                    <div>
                      <Label htmlFor="confirmPassword" className="text-gray-700">
                        Confirm Password *
                      </Label>
                      <Input
                        id="confirmPassword"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Confirm your password"
                        className="mt-1"
                        disabled={isLoading}
                        required
                      />
                    </div>
                  </div>

                  {error && (
                    <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                      <p className="text-red-600 text-sm">{error}</p>
                      {error.includes("already exists") && (
                        <p className="text-red-600 text-sm mt-1">
                          <Link
                            to="/signin"
                            className="font-medium underline hover:text-red-700"
                          >
                            Click here to sign in instead
                          </Link>
                        </p>
                      )}
                    </div>
                  )}
                  {success && <p className="text-green-600 text-sm">{success}</p>}

                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-orange-600 hover:bg-orange-700 text-white"
                  >
                    {isLoading ? "Creating Account..." : "Create Account"}
                  </Button>
                </form>

                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-300" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-white text-gray-500">Or continue with</span>
                  </div>
                </div>

                <div className="mb-6">
                  <Button
                    onClick={handleGoogleSignIn}
                    className="w-full flex justify-center items-center gap-3 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                    variant="outline"
                    disabled={isLoading}
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    Continue with Google
                  </Button>
                </div>

                <div className="pt-6 border-t border-gray-200">
                  <div className="text-center">
                    <p className="text-sm text-gray-600">
                      Already have an account?{" "}
                      <Link
                        to="/signin"
                        className="font-medium text-orange-600 hover:text-orange-500"
                      >
                        Sign in here
                      </Link>
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <form onSubmit={handleVerifyOtp} className="space-y-6">
                {/* <div className="text-center">
                  <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-3">
                    <Mail className="w-6 h-6 text-orange-600" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Check Your Email</h3>
                  <p className="text-sm text-gray-600 mb-4">
                    We sent a 6-digit verification code to:<br />
                    <strong className="text-gray-800">{email}</strong>
                  </p>
                </div> */}

                <div className="space-y-2">
                  {/* <Label htmlFor="otp" className="text-gray-700 text-sm font-medium">
                    Verification Code
                  </Label> */}
                  <Input
                    id="otp"
                    type="text"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="Enter 6-digit code"
                    className="text-center tracking-widest text-lg font-mono h-12 text-base"
                    disabled={isLoading}
                    maxLength={6}
                    required
                  />
                  {/* <p className="text-xs text-gray-500 text-center">
                    Enter the 6-digit code from your email
                  </p> */}
                </div>

                <div className="text-center">
                  Didn't receive the code?
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    disabled={isLoading}
                    className="text-sm ml-2 text-orange-600 hover:text-orange-500 disabled:text-gray-400 underline"
                  >
                    Click to resend
                  </button>
                </div>

                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                    <p className="text-red-600 text-sm text-center">{error}</p>
                  </div>
                )}
                {/* {success && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-md">
                    <p className="text-green-600 text-sm text-center">{success}</p>
                  </div>
                )} */}

                <div className="flex gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setStep('form');
                      setOtp('');
                      setError('');
                      setSuccess('');
                    }}
                    disabled={isLoading}
                    className="flex-1"
                  >
                    Back
                  </Button>
                  <Button
                    type="submit"
                    disabled={isLoading || otp.length !== 6}
                    className="flex-1 bg-orange-600 hover:bg-orange-700 text-white"
                  >
                    {isLoading ? "Verifying..." : "Verify Email"}
                  </Button>
                </div>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Register;
